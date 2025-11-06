from django.template.loader import render_to_string

from .models import VideoStream


def format_raw(instance: VideoStream) -> str:
    return render_to_string(
        'wagtailstreaming_templates/widgets/raw_stream.html', 
        context = { 'instance': instance }
    )


def format_hls(instance: VideoStream) -> str:
    return render_to_string(
        'wagtailstreaming_templates/widgets/hls_stream.html', 
        context = { 'instance': instance }
    )


def format_dash(instance: VideoStream) -> str:
    return render_to_string(
        'wagtailstreaming_templates/widgets/dash_stream.html', 
        context = { 'instance': instance }
    )