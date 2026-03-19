from django.utils import timezone
from celery import shared_task
import logging 

LOGGER = logging.getLogger(__name__)


@shared_task(name = 'wagtailstreaming_check_queue')
def check_queue():
    from . import task_utils

    if not task_utils.celery_beat_installed():
        LOGGER.warning('Skipping check_queue(): django_celery_beat is not installed')
        return

    ongoing = task_utils.upload_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return

    on_queue = task_utils.upload_queue.front
    if not on_queue:
        LOGGER.info('All uploads have been processed')
        return
    task_utils.sched_conversion(on_queue)


@shared_task(name = 'wagtailstreaming_check_downloads')
def check_downloads():
    from . import task_utils

    if not task_utils.celery_beat_installed():
        LOGGER.warning('Skipping check_downloads(): django_celery_beat is not installed')
        return
    
    ongoing = task_utils.download_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return
    
    on_queue = task_utils.download_queue.front
    if not on_queue:
        LOGGER.info('All downloads have been processed')
        return
    task_utils.sched_download(on_queue)


@shared_task(name = 'wagtailstreaming_check_audios')
def check_audios():
    from . import task_utils

    if not task_utils.celery_beat_installed():
        LOGGER.warning('Skipping check_audios(): django_celery_beat is not installed')
        return
    
    ongoing = task_utils.audio_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return
    
    on_queue = task_utils.audio_queue.front
    if not on_queue:
        LOGGER.info('All audios have been processed')
        return
    task_utils.sched_audio(on_queue)


@shared_task(name = 'wagtailstreaming_check_transcripts')
def check_transcripts():
    from . import task_utils

    if not task_utils.celery_beat_installed():
        LOGGER.warning('Skipping check_transcripts(): django_celery_beat is not installed')
        return
    
    ongoing = task_utils.transcribe_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return
    
    on_queue = task_utils.transcribe_queue.front
    if not on_queue:
        LOGGER.info('All transcriptions have been processed')
        return
    task_utils.sched_transcribe(on_queue)


@shared_task(name = 'wagtailstreaming_convert_video')
def convert_video(stream_id):
    from . import task_utils

    ongoing = task_utils.upload_queue.ongoing
    if getattr(ongoing, 'id', stream_id) != stream_id:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return
    
    from .models import get_stream_model
    from .conversion_utils import get_segmenter
    stream_class = get_stream_model()

    video = stream_class.objects.filter(id = stream_id).first()
    if not video:
        LOGGER.warning(f'There is no Stream instance with the id {stream_id}!')
        task_utils.go_next(task_utils.upload_queue, video, task_utils.sched_conversion)
        return
    
    if not (video.file or video.file_url):
        LOGGER.warning(f'Stream instance {video} does not have a raw video nor a video link!')
        task_utils.go_next(task_utils.upload_queue, video, task_utils.sched_conversion)
        return

    if video.file_url and not video.file:
        task_utils.sched_download(video)
        task_utils.go_next(task_utils.upload_queue, video, task_utils.sched_conversion)
        return
    
    w = video.attrs.streams[0].width or 0 if video.attrs.streams else 0
    h = video.attrs.streams[0].height or 0 if video.attrs.streams else 0
    segment = get_segmenter(w, h, video.supported_resolutions)

    if segment is None:
        reason = 'Lack of memory in machine'
        if 0 in [w, h]:
            reason = 'Resolution of unprocessed video can not be determined'

        err_message = f'Could not determine ideal segmenter for Stream instance {video}: {reason}'
        video.add_remark(err_message)
        LOGGER.warning(err_message)
        task_utils.go_next(task_utils.upload_queue, video, task_utils.sched_conversion)
        return

    video.date_processed = timezone.now()
    video.save()

    hls_okay, dash_okay = segment(video)

    if any([hls_okay, dash_okay]):
        video.hls_ready = hls_okay
        video.dash_ready = dash_okay
        video.date_finished = timezone.now()
        video.save()

        if not video.thumbnail:
            if video._populate_thumbnail():
                LOGGER.info(f'Successfully created thumbnail for stream instance {video}')
        LOGGER.info(f'Successfully converted stream instance {video}')

    else:
        LOGGER.warning(f'Could not convert stream instance {video}')
    task_utils.go_next(task_utils.upload_queue, video, task_utils.sched_conversion)


@shared_task(name = 'wagtailstreaming_extract_audio')
def extract_audio(stream_id):
    from . import conversion_utils, task_utils

    ongoing = task_utils.audio_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a video instance whose audio is getting transcribed! id: {ongoing.id}')
        return
    
    from .models import get_stream_model

    stream_class = get_stream_model()
    video = stream_class.objects.filter(id = stream_id).first()
    if not video:
        LOGGER.warning(f'There is no Video instance with the id {stream_id}!')
        task_utils.go_next(task_utils.audio_queue, video, task_utils.sched_audio)
        return
    
    if video.audio_ready:
        task_utils.go_next(task_utils.audio_queue, video, task_utils.sched_audio)
        return
    
    if not video.raw.audio_file:
        LOGGER.warning(f'Stream instance does not have a raw file yet, skipping...')
        task_utils.sched_download(video)
        return
    
    def clean_audio_extraction_process(success = False):
        if video.remarks:
            video.remarks = video.remarks.replace('[AUDIO EXTRACTION ONGOING]', 'AUDIO EXTRACTED' if success else 'AUDIO EXTRACTION FAILED')
        video.audio_ready = success
        video.save(update_fields = ['remarks', 'audio_ready'])

    def start_audio_extraction_process():
        video.add_remark('[AUDIO EXTRACTION ONGOING]')

    start_audio_extraction_process()
    success = conversion_utils.extract_audio(video.raw.path, video.raw.audio_file)
    if not success:
        LOGGER.error(f'Failed to extract audio file of stream instance {stream_id}! Skipping...')

    clean_audio_extraction_process(success)
    task_utils.go_next(task_utils.audio_queue, video, task_utils.sched_audio)


@shared_task(name = 'wagtailstreaming_transcribe_video')
def transcribe_video(stream_id):
    from . import task_utils, transcription_utils

    ongoing = task_utils.transcribe_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a video instance getting transcribed! id: {ongoing.id}')
        return
    
    from .models import get_stream_model, Transcript, TranscriptCue

    stream_class = get_stream_model()
    video = stream_class.objects.filter(id = stream_id).first()
    if not video:
        LOGGER.warning(f'There is no Video instance with the id {stream_id}!')
        task_utils.go_next(task_utils.transcribe_queue, video, task_utils.sched_transcribe)
        return
    
    if not video.raw.audio_file:
        LOGGER.warning(f'Stream instance does not have a raw file yet, skipping...')
        task_utils.sched_audio(video)
        return

    transcript_process_kwargs = {
        'video': video, 'language': 'default', 
        'name': '[TRANSCRIPTION ONGOING]'
    }

    def clean_transcription_process():
        Transcript.objects.filter(**transcript_process_kwargs).delete()
        
    def start_transcription_process():
        Transcript.objects.get_or_create(**transcript_process_kwargs)

    start_transcription_process()
    default = Transcript.objects.filter(video = video, default = True).first()
    if not default:
        transcription_utils.update_vtt(video)

    unsynced = TranscriptCue.objects.filter(transcript__video = video, synced = False).values_list('transcript__id', flat = True)
    for un in unsynced:
        transcription_utils.update_vtt(video, un)

    clean_transcription_process()
    task_utils.go_next(task_utils.transcribe_queue, video, task_utils.sched_transcribe)


@shared_task(name = 'wagtailstreaming_download_video')
def download_video(stream_id):
    from . import task_utils, download_utils

    ongoing = task_utils.download_queue.ongoing
    if ongoing:
        LOGGER.info(f'There is currently a stream instance getting processed! id: {ongoing.id}')
        return

    from .models import get_stream_model
    stream_class = get_stream_model()

    video = stream_class.objects.filter(id = stream_id).first()
    if not video:
        LOGGER.warning(f'There is no Strean instance with the id {stream_id}!')
        task_utils.go_next(task_utils.download_queue, video, task_utils.sched_download)
        return

    if video.file:
        task_utils.go_next(task_utils.download_queue, video, task_utils.sched_download)
        return

    if not video.file_url:
        LOGGER.error(f'The stream instance {video} has not given a valid google drive link!')
        task_utils.go_next(task_utils.download_queue, video, task_utils.sched_download)
        return

    if download_utils.download(video):
        task_utils.sched_conversion(video)

    video.raw_link = video.file_url.replace('DOWNLOADING ', '')
    video.save()
    task_utils.go_next(task_utils.download_queue, video, task_utils.sched_download)