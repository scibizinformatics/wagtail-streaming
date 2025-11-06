from django.core.exceptions import ObjectDoesNotExist

import subprocess
import logging
import typing
import shutil
import psutil
import json
import time
import os

from .settings import stream_settings

LOGGER = logging.getLogger(__name__)

LOOKAHEAD_FRAMES = 40
OVERHEAD_MB = 256


# dependency checker
def ffmpeg_installed() -> bool:
    """Checks if ffmpeg is installed"""
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path is None:
        LOGGER.warning('ffmpeg is not installed! Video conversions and processes are disabled')
        return False

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout = subprocess.DEVNULL,
            stderr = subprocess.DEVNULL,
            check = True
        )
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        LOGGER.error(f'Failed to check the availability of ffmpeg: {e}')
        return False


# mem guard utils
def _res_str_to_values(res_str: str) -> typing.Tuple[int, int]:
    w_str, h_str = res_str.lower().strip().split('x')
    try:
        return int(w_str), int(h_str)

    except Exception as e:
        LOGGER.warning(f'Could not parse {res_str} to int values: {e}')
        return 0, 0


def _estimate_memory_per_frame(res_str: str) -> int:
    w, h = _res_str_to_values(res_str)
    if not (w and h):
        LOGGER.warning(f'Could not parse {res_str} to int values, result: {w} {h}')
        return 0
    return w * h * 3


def _compute_mbpfr(mem_per_frame: int) -> float:
    return round((mem_per_frame * LOOKAHEAD_FRAMES) / (1024 ** 2) , 2)


def _per_resolution_mb(
        resolutions: typing.List[typing.Tuple[str, str]]
    ) -> typing.List[float]:
    return [_compute_mbpfr(_estimate_memory_per_frame(res)) for res, _ in resolutions]


def _estimate_memory_mb(
        raw_mbpfr: float, 
        resolutions: typing.List[typing.Tuple[str, str]]
    ) -> typing.Tuple[float, float]:
    if raw_mbpfr <= 0:
        return 0.0, 0.0

    mbpfr = _per_resolution_mb(resolutions)
    if not mbpfr or 0.0 in mbpfr: # an error occurred
        return 0.0, 0.0

    return (
        max(mbpfr) + raw_mbpfr + OVERHEAD_MB, # sequential
        sum(mbpfr) + raw_mbpfr + OVERHEAD_MB # bulk
    )


# ffmpeg invokations 
def create_thumbnail(
        source_path: str, 
        output_path: str
    ) -> bool:
    """Captures the frame on 00:00:05 and produces a thumbnail file."""
    if not ffmpeg_installed():
        return False

    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", source_path,
            "-ss", "00:00:05", "-vframes", "1",
            "-vf", "scale=640:-1", 
            output_path
        ], check = True)

        if os.path.exists(output_path):
            isfile = os.path.isfile(output_path)
            if not isfile:
                LOGGER.error(f'Failed to generate thumbnail for video {source_path}: output path {output_path} is not a file!')
            return isfile

        LOGGER.error(f'Failed to generate thumbnail for video {source_path}: output path {output_path} does not exist!')
        return False

    except Exception as e:
        LOGGER.error(f'Failed to generate thumbnail for video {source_path}: {e}')
        return False
    

def check_attributes(source_path: str) -> typing.Optional[typing.Dict[str, typing.Any]]:
    """Checks the attributes of a video."""
    if not ffmpeg_installed():
        return None
    
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_format', '-show_streams',
                '-of', 'json', source_path
            ],
            capture_output = True,
            text = True
        )

        return json.loads(result.stdout)

    except Exception as e:
        LOGGER.error(f'Failed to determine the attributes of the video {source_path}: {e}')
        return None


def _listen_to_process(command: typing.List[str]) -> typing.Optional[subprocess.Popen]:
    try:
        process = subprocess.Popen(command, text = True)
        return process

    except Exception as e:
        LOGGER.error(f'Could not start a segmentation process: {e}, command: {command}')
        return None
    

def _watch_segmentation(
        stream_instance, 
        process: subprocess.Popen
    ) -> str:
    """
    Function assumes that the process have been started already,
    Task is to watch any changes in the stream_instance
    """
    while True:
        try:
            stream_instance.refresh_from_db()

        except ObjectDoesNotExist:
            process.terminate()
            return f'Deleted'

        if not stream_instance.file:
            process.terminate()
            return f'The video for instance {stream_instance} have been set to blank or null while video is being segmented!'
        
        if not os.path.exists(stream_instance.raw.path):
            process.terminate()
            return f'The video file {stream_instance.raw.path} seem to have been deleted or moved to another directory while video is being segmented!'
        
        ret_code = process.poll()
        if ret_code is not None:
            if ret_code == 0:
                return ''
            return f'Segmentation process exited with error code {ret_code}'
        
        time.sleep(3)

def _start_process(
        stream_instance, 
        resolution: str, 
        command: typing.List[str]
    ) -> typing.Optional[bool]:
    """
    Returns True if the process was successful, 
    Returns False if something went wrong, 
    Returns None if instance was deleted
    """
    process = _listen_to_process(command)
    if not process:
        stream_instance.add_remark(f'Segmentation process could not be started for this instance, command: {command}')
        return False

    stream_instance.process_id = process.pid
    stream_instance.save(update_fields = ['process_id'])

    err_message = _watch_segmentation(stream_instance, process)
    if err_message:
        if err_message == 'Deleted':
            return None

        stream_instance.add_remark(f'Error upon segmenting video at resolution {resolution}, error: {err_message}')
        return False
    return True


def _stop_segmentation(
        stream_instance, 
        err_message: str = None
    ) -> bool:
    try:
        if err_message:
            stream_instance.add_remark(err_message)
            LOGGER.error(err_message)
        return not err_message
    
    except Exception as e:
        LOGGER.error(e)
        return False


def _seq_hls(stream_instance) -> bool:
    rawfile_path = stream_instance.raw.path
    hls_dir = stream_instance.hls.root
    resolutions = stream_instance.supported_resolutions
    if not hls_dir:
        return _stop_segmentation(
            stream_instance, 
            f'Sequential HLS segmentation error: Could not resolve hls dir "{hls_dir}"'
        )

    try:
        master_playlist = os.path.join(hls_dir, 'master.m3u8')
        variants = []

        for res, bitrate in resolutions:
            res_subdir = os.path.join(hls_dir, res)
            os.makedirs(res_subdir, exist_ok = True)

            playlist_path = os.path.join(res_subdir, f'{res}.m3u8')
            command = [
                'ffmpeg', '-y', '-i', rawfile_path,
                '-vf', f'scale={res}',
                '-c:a', 'aac', '-ar', '48000', '-c:v', 'h264',
                '-profile:v', 'main', '-crf', '20', '-sc_threshold', '0',
                '-g', '48', '-keyint_min', '48',
                '-hls_time', '4',
                '-hls_playlist_type', 'event',
                '-b:v', bitrate, '-maxrate', bitrate,
                '-bufsize', f'{int(int(bitrate[:-1]) * 2)}k',
                '-b:a', '128k',
                '-hls_segment_filename', os.path.join(res_subdir, 'seg_%03d.ts'),
                '-progress', os.path.join(hls_dir, f'{res}.txt'),
                playlist_path
            ]

            success = _start_process(stream_instance, res, command)
            if success is None:
                return False

            if success:
                variants.append((playlist_path, bitrate, res))

        with open(master_playlist, 'w') as f:
            f.write('#EXTM3U\n')
            for playlist, bitrate, res in variants:
                relative_playlist = os.path.relpath(playlist, hls_dir)
                f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bitrate[:-1]}000,RESOLUTION={res}\n')
                f.write(f'{relative_playlist}\n')
        return True

    except Exception as e:
        return _stop_segmentation(
            stream_instance, 
            f'Sequential HLS segmentation error: {e}'
        )


def create_segments_seq(stream_instance) -> typing.Tuple[bool, bool]:
    """Main segmenter for sequential segmentation. Only HLS segmentation is being performed here due to MPEG-DASH having syncing issues when segmented sequentially"""
    hls_success = False
    dash_success = False

    if ffmpeg_installed():
        if stream_settings.ALLOW_HLS:
            hls_success = _seq_hls(stream_instance)

    return hls_success, dash_success


def _bulk_hls(stream_instance) -> bool:
    """Bulk segmenter for HLS format"""
    if not stream_instance.file:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk HLS segmentation error: Raw File field of instance {stream_instance.title} is not yet populated!'
        )

    rawfile_path = stream_instance.raw.path
    hls_dir = stream_instance.hls.root
    resolutions = stream_instance.supported_resolutions

    if not hls_dir:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk HLS segmentation error: Could not resolve hls root "{hls_dir}"'
        )

    split_count = len(resolutions)
    if split_count <= 0:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk HLS segmentation error: Instance {stream_instance.title} does not have a list of supported resolutions'
        )

    try:
        split_labels = [f"[v{i+1}]" for i in range(split_count)]
        filter_parts = [f"[v:0]split={split_count}{''.join(split_labels)}"]

        scale_labels = []
        for i, (res, _) in enumerate(resolutions):
            label = f"[v{i+1}]scale={res}[v{i+1}out]"
            filter_parts.append(label)
            scale_labels.append(f"[v{i+1}out]")

        filter_complex = "; ".join(filter_parts)
        command = [
            "ffmpeg", "-y", "-i", rawfile_path, 
            "-filter_complex", filter_complex, 
            "-progress", os.path.join(hls_dir, 'all.txt')
        ]

        hls_variants = []
        for i, ((res, bitrate), scale_label) in enumerate(zip(resolutions, scale_labels)):
            res_hls_subdir = os.path.join(hls_dir, res)
            os.makedirs(res_hls_subdir, exist_ok=True)
            hls_playlist = os.path.join(res_hls_subdir, f"{res}.m3u8")
            hls_seg = os.path.join(res_hls_subdir, "seg_%03d.ts")
            hls_variants.append((hls_playlist, bitrate, res))

            command += [
                "-map", scale_label,
                f"-c:v:{i}", "h264", "-profile:v", "main", "-crf", "20",
                f"-b:v:{i}", bitrate,
                f"-maxrate:v:{i}", bitrate,
                f"-bufsize:v:{i}", f"{int(int(bitrate[:-1])*2)}k",
                "-g", "48", "-keyint_min", "48",
                "-map", "a:0?", f"-c:a:{i}", "aac", "-b:a", "128k", "-ar", "48000",
                "-hls_time", "4", "-hls_playlist_type", "event",
                "-hls_segment_filename", hls_seg,
                hls_playlist
            ]

        success = bool(_start_process(stream_instance, 'HLS Bulk', command))
        if not success:
            return _stop_segmentation(
                stream_instance, 
                f'Bulk HLS segmentation error: Process resulted to failure!'
            )

        master_playlist = os.path.join(hls_dir, "master.m3u8")
        with open(master_playlist, "w") as f:
            f.write("#EXTM3U\n")
            for playlist, bitrate, res in hls_variants:
                relative_playlist = os.path.relpath(playlist, hls_dir)
                f.write(f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate[:-1]}000,RESOLUTION={res}\n")
                f.write(f"{relative_playlist}\n")

        return _stop_segmentation(stream_instance)
    
    except Exception as e:
        return _stop_segmentation(
            stream_instance, 
            f"Bulk HLS segmentation error: {e}"
        )
    

def _bulk_dash(stream_instance) -> bool:
    """Bulk segmenter for MPEG-DASH format"""
    if not stream_instance.file:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk MPEG-DASH segmentation error: Raw File field of instance {stream_instance.title} is not yet populated!'
        )

    rawfile_path = stream_instance.raw.path
    dash_dir = stream_instance.dash.root
    resolutions = stream_instance.supported_resolutions

    if not dash_dir:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk MPEG-DASH segmentation error: Could not resolve dash root "{dash_dir}"'
        )

    split_count = len(resolutions)
    if split_count <= 0:
        return _stop_segmentation(
            stream_instance, 
            f'Bulk MPEG-DASH segmentation error: Instance {stream_instance.title} does not have a list of supported resolutions'
        )

    try:
        split_labels = [f"[v{i+1}]" for i in range(split_count)]
        filter_parts = [f"[v:0]split={split_count}{''.join(split_labels)}"]

        scale_labels = []
        for i, (res, _) in enumerate(resolutions):
            label = f"[v{i+1}]scale={res}[v{i+1}out]"
            filter_parts.append(label)
            scale_labels.append(f"[v{i+1}out]")

        filter_complex = "; ".join(filter_parts)
        command = [
            "ffmpeg", "-y", "-i", rawfile_path, 
            "-filter_complex", filter_complex, 
            "-progress", os.path.join(dash_dir, 'all.txt')
        ]

        for i, ((res, bitrate), scale_label) in enumerate(zip(resolutions, scale_labels)):
            command += [
                "-map", scale_label,
                f"-c:v:{i}", "h264", "-profile:v", "main", "-crf", "20",
                f"-b:v:{i}", bitrate,
                f"-maxrate:v:{i}", bitrate,
                f"-bufsize:v:{i}", f"{int(int(bitrate[:-1])*2)}k",
            ]

        command += [
            "-map", "a:0?", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-f", "dash",
            "-use_template", "1",
            "-use_timeline", "1",
            "-seg_duration", "4",
            "-init_seg_name", "init_$RepresentationID$.m4s",
            "-media_seg_name", "chunk_$RepresentationID$_$Number$.m4s",
            os.path.join(dash_dir, "manifest.mpd")
        ]

        return bool(_start_process(stream_instance, 'MPEG-DASH Bulk', command))

    except Exception as e:
        return _stop_segmentation(
            stream_instance, 
            f"Bulk MPEG-DASH segmentation error: {e}"
        )


def create_segments_bulk(stream_instance) -> typing.Tuple[bool, bool]:
    """Main segmenter for bulk segmentation. Both HLS and MPEG-DASH is performed here."""
    hls_success = False
    dash_success = False

    if ffmpeg_installed():
        if stream_settings.ALLOW_HLS:
            hls_success = _bulk_hls(stream_instance)

        if stream_settings.ALLOW_DASH:
            dash_success = _bulk_dash(stream_instance)
    return hls_success, dash_success


# utils
def get_segmenter(
        w: int, h: int, 
        resolutions: typing.List[typing.Tuple[str, str]]
    ) -> typing.Optional[typing.Callable[[typing.Any], typing.Tuple[bool, bool]]]:
    """
    Util function to determine if segmenter should be sequential mode or bulk mode. 
    Sequential mode takes less memory but more time to encode. 
    Bulk mode takes more memory but less time to encode. 
    """
    if not ffmpeg_installed():
        return None

    raw_mbpfr = _compute_mbpfr(w * h * 3)
    seq_mem, bulk_mem = _estimate_memory_mb(raw_mbpfr, resolutions)
    if 0.0 in [seq_mem, bulk_mem]:
        LOGGER.error(f'Error estimating required mem: Seq {seq_mem} MB, Bulk {bulk_mem} MB')
        return None

    mem = psutil.virtual_memory()
    available = round(mem.available / (1024 ** 2), 2)
    if available >= bulk_mem:
        return create_segments_bulk

    if available >= seq_mem:
        return create_segments_seq
    LOGGER.error(f'Not enough memory ({available} MB): requires at least {seq_mem} MB')
    return None