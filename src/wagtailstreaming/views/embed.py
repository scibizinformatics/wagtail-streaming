from django.views.decorators.clickjacking import xframe_options_exempt
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse, NoReverseMatch
from django.http import Http404

from typing import Tuple
import logging

from ..models import VideoStream, get_stream_model

LOGGER = logging.getLogger(__name__)
stream_model = get_stream_model()


def render_stream(request, instance: VideoStream) -> Tuple[str, str]:
    if not instance:
        return '', ''
    
    url = ''
    mode = 'raw'

    try:
        url = reverse(
            'wagtailstreaming_public:embed', 
            args = (instance.pk,)
        )

    except NoReverseMatch as e:
        LOGGER.error(f'Embed url is not included! Error: {e}')

    if request:
        params = getattr(request, 'query_params', getattr(request, 'GET', {}))
        url = request.build_absolute_uri(request.path)
        mode = params.get('mode', 'raw').lower()

    mirrors_html = ''
    if url:
        mirrors_html = render_to_string(
            'wagtailstreaming_templates/widgets/stream_mirrors.html',
            context = { 'mode': mode, 'url': url, 'streams': instance.supported_streams } 
        )

    embed_html = ''
    try:
        embed_html = render_to_string(
            f'wagtailstreaming_templates/widgets/{mode}_stream.html', 
            context = { 'instance': instance }
        )

    except Exception as e:
        LOGGER.error(f'Failed to render video stream widget: {e}')
        embed_html = "<p>Stream unavailable</p>"
    return embed_html, mirrors_html


def render_player(request, instance: VideoStream, exclude_mirrors: bool = False) -> str:
    if not instance:
        return ''

    embed_html, mirrors_html = render_stream(request, instance)
    if exclude_mirrors:
        mirrors_html = ''

    context = {
        'embed_html': embed_html, 
        'mirrors_html': mirrors_html
    }

    return render_to_string(
        'wagtailstreaming_templates/widgets/player.html', 
        context = context
    )


@xframe_options_exempt
def embed(request, pk = None):
    if not pk:
        raise Http404(f'Video Stream does not exist!')
    
    instance = get_object_or_404(stream_model, pk = pk)
    player_html = render_player(request, instance)

    context = {
        'instance': instance, 
        'player_html': player_html
    }

    return render(
        request, 
        'wagtailstreaming_templates/widgets/embed.html', 
        context = context
    )