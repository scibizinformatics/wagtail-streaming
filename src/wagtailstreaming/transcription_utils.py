from django.utils.module_loading import import_string
from .settings import stream_settings

from pathlib import Path
import logging
import typing
import os
import re

from .models import Transcript, TranscriptCue, VideoStream
from .dataclasses import VTTSnippet, StreamSubtitle

LOGGER = logging.getLogger(__name__)
LANGUAGE_RE = re.compile(r'Language:\s*([a-zA-Z-]+)', re.IGNORECASE)

def nanogpt_transcribe(source_path: str, language: str = None) -> str:
    try:
        from openai import OpenAI
    except Exception as e:
        LOGGER.error(f'Module openai not installed, please install using pip or add to requirements: {e}')
        return ''

    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f'Source audio file with path {source_path} is not accessible!')
    
    client = OpenAI(
        api_key = stream_settings.NANOGPT_API_KEY, 
        base_url = stream_settings.NANOGPT_BASE_URL
    )

    try:
        with open(path, 'rb') as file:
            kwargs = {
                'model': 'whisper-1', 
                'file': file, 
                'response_format': 'vtt',
            }
            if language:
                kwargs['language'] = language

            transcript = client.audio.transcriptions.create(**kwargs)
        return transcript
    
    except Exception as e:
        LOGGER.error(f'Transcription request failed: {e}')
        return ''


def get_transcriber() -> typing.Callable[[str, typing.Optional[str]], str]:
    """Returns the transcriber function that has two args (source_path: str, language: str = None) and has a return value with str data type"""
    if not stream_settings.VIDEO_TRANSCRIBER:
        return nanogpt_transcribe
    
    try:
        transcriber = import_string(stream_settings.VIDEO_TRANSCRIBER)
        return transcriber
    
    except (ImportError, AttributeError) as e:
        LOGGER.error(f'Configuration error: VIDEO_TRANSCRIBER {stream_settings.VIDEO_TRANSCRIBER} could not be imported!')
        return nanogpt_transcribe


def push_transcript(stream_instance: VideoStream, transcription: str) -> str:
    """Creates transcript instances from transcription"""
    language = 'en'
    transcription = (transcription or '').strip()
    if not transcription:
        return f'Transcription is blank! Transcription for stream_instance {stream_instance.id} is unregistered'

    if transcription.lower().startswith('webvtt'):
        match = LANGUAGE_RE.search(transcription)
        if match:
            language = match.group(1)
    elif transcription != '':
        transcription = 'WEBVTT\n\n' + transcription

    transcript_instance, created = Transcript.objects.get_or_create(
        video = stream_instance, language = language, 
        name = 'Default', default = True, slug = f'default-{language}'
    )

    blocks = re.split(r'\n\s*\n', transcription)
    if len(blocks) <= 0:
        return f'Transcription is blank! Transcription for stream_instance {stream_instance.id} is unregistered'

    count = 0
    for t in blocks:
        if t.lower().startswith('webvtt'):
            continue

        snippet = VTTSnippet()
        try:
            snippet.init_from_snippet(t)

        except Exception as e:
            LOGGER.error(f'Failed to recognize line as transcription cue: {e}')
            continue

        if not snippet.is_valid:
            continue

        _, created = TranscriptCue.objects.get_or_create(
            transcript = transcript_instance, 
            start = snippet.start, end = snippet.end, 
            defaults = { 'text': snippet.text }
        )

        if created:
            count += 1

    vtt_path = os.path.join(stream_instance.transcription.root, transcript_instance.file_name)
    with open(vtt_path, 'w', encoding = 'utf-8') as vtt:
        vtt.write(transcription)

    subtitle_instance = transcript_instance.as_dataclass
    if not subtitle_instance.uri:
        subtitle_instance.uri = transcript_instance.url

    error = ''
    if not stream_instance.register_vtt(subtitle_instance):
        error = f'Failed to add vtt file {subtitle_instance.uri} to manifest files of {stream_instance.title}'
    
    transcript_instance.cues.all().update(synced = True)
    return error


def update_vtt(stream_instance: VideoStream, transcription_id: typing.Optional[int] = None) -> bool:
    """Updates a transcription instance if provided, creates a transcription if not"""
    if not transcription_id:
        transcriber = get_transcriber()
        transcription = transcriber(stream_instance.raw.audio_file, None)
        if not transcription:
            return False
        
        error = push_transcript(stream_instance, transcription)
        if error:
            LOGGER.warning(error)
        return not error
    
    transcript_instance = Transcript.objects.filter(id = transcription_id).first()
    if not transcript_instance:
        return False
    
    header = ['WebVTT', f'Language: {transcript_instance.language}', '']
    cues = [cue.as_block for cue in transcript_instance.cues.order_by(f'start')]
    
    vtt_content = '\n'.join([*header, *cues])
    vtt_path = os.path.join(stream_instance.transcription.root, transcript_instance.file_name)
    with open(vtt_path, 'w', encoding = 'utf-8') as vtt:
        vtt.write(vtt_content)

    transcript_instance.cues.all().update(synced = True)
    return True