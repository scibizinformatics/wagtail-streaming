from django.core.files import File

import subprocess
import logging
import typing
import shutil
import os
import re

from .validators import VideoFileValidator
from .settings import stream_settings
from .models import VideoStream

LOGGER = logging.getLogger(__name__)


def extract_file_id(gdrive_link: str) -> typing.Optional[str]:
    """
    Extracts the GDrive file ID from a given link
    Returns the file ID if found else None
    """
    gdrive_patterns = [
        re.compile(r"https://drive\.google\.com/file/d/([^/]+)"), 
        re.compile(r"https://drive\.google\.com/open\?id=([^&]+)"), 
        re.compile(r"https://drive\.google\.com/uc\?id=([^&]+)"), 
    ]

    for pattern in gdrive_patterns:
        match = pattern.match(gdrive_link)
        if match:
            return match.group(1)
    return None


def _start_download(
        command: typing.List[str], 
        target_dir: str
    ) -> typing.Optional[str]:
    try:
        subprocess.run(
            command, cwd = target_dir,
            capture_output = True, 
            text = True, check = True, 
        )
        return None
    
    except subprocess.CalledProcessError as e:
        return str(e)


def _stop_download(
        stream_instance: VideoStream, 
        err_message: str = ''
    ) -> bool:
    if err_message:
        stream_instance.add_remark(err_message)
        LOGGER.error(err_message)

    stream_instance.file_url = stream_instance.file_url.replace('[DOWNLOADING] ', '')
    stream_instance.save()
    return not err_message


def download(stream_instance: VideoStream) -> bool:
    """
    Assumes that stream_instance fields has been validated
    """
    target_dir = stream_instance.download_root
    if not target_dir:
        if not stream_instance.file_url:
            return _stop_download(
                stream_instance, 
                'Instance does not have a Google Drive Link'
            )
        return False

    command = ['gdown', stream_instance.file_url]
    stream_instance.file_url = f'[DOWNLOADING] {stream_instance.file_url}'
    stream_instance.save()

    err_message = _start_download(command, target_dir)
    if err_message:
        return _stop_download(stream_instance, err_message)

    files = os.listdir(target_dir)
    if len(files) != 1:
        shutil.rmtree(target_dir)
        return _stop_download(
            stream_instance, 
            f'Expected 1 file, found {len(files)} files in download directory {target_dir}'
        )

    file = os.path.join(target_dir, files[0])
    if os.path.getsize(file) <= 0:
        shutil.rmtree(target_dir)
        return _stop_download(
            stream_instance, 
            f'File has been downloaded but file has no contents!'
        )

    try:
        with open(file, 'rb') as f:
            file_instance = File(f)
            validate = VideoFileValidator(stream_settings.VIDEO_EXTENSIONS)
            validate(file_instance)
            stream_instance.file.save(os.path.basename(file), file_instance, save = True)

        shutil.rmtree(target_dir)
        return _stop_download(stream_instance)

    except Exception as e:
        return _stop_download(
            stream_instance, 
            f"Failed to save file {file} as raw file: {e}"
        )