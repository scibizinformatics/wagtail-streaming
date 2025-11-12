from django.urls import reverse, NoReverseMatch

from wagtail.api.v2.serializers import BaseSerializer
from wagtail.api.v2.utils import get_full_url

from rest_framework.fields import ReadOnlyField
from rest_framework import serializers

from rest_framework_dataclasses.serializers import DataclassSerializer

import logging

from ..dataclasses import StreamInfo, FormatInfo, VideoAttribute
from ..models import VideoStream, get_stream_model
from ..views.embed import render_stream


LOGGER = logging.getLogger(__name__)
stream_model = get_stream_model()


class EmbedURLField(ReadOnlyField):
    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        try:
            return reverse(
                'wagtailstreaming_public:embed', 
                args = (instance.pk, )
            )

        except NoReverseMatch as e:
            LOGGER.error(f'Embed urls is in included! Error: {e}')
            return ''


class ThumbnailURLField(ReadOnlyField):
    def get_attribute(self, instance):
        return instance
    
    def to_representation(self, instance):
        if instance.thumbnail:
            return get_full_url(self.context['request'], instance.thumbnail.url)
        return None
    

class StreamURLField(ReadOnlyField):
    def get_attribute(self, instance):
        return instance
    
    def to_representation(self, instance):
        urls = {}
        if instance.file:
            urls['raw'] = get_full_url(self.context['request'], instance.raw.url)

            if instance.hls_ready:
                urls['hls'] = get_full_url(self.context['request'], instance.hls.url)
            
            if instance.dash_ready:
                urls['dash'] = get_full_url(self.context['request'], instance.dash.url)

        return urls


class StreamModesField(ReadOnlyField):
    def get_attribute(self, instance):
        return instance
    
    def to_representation(self, instance):
        return instance.supported_streams
    

class VideoStreamSerializer(BaseSerializer):
    thumbnail_url = ThumbnailURLField()
    stream_urls = StreamURLField()
    embed_url = EmbedURLField()
    modes = StreamModesField()


class StreamHTMLSerializer(serializers.ModelSerializer):
    embed_html = serializers.SerializerMethodField()
    mirrors_html = serializers.SerializerMethodField()

    class Meta:
        model = VideoStream
        fields = ['embed_html', 'mirrors_html']

    def _get_rendered_stream(self, obj):
        if not hasattr(obj, '_rendered_stream'):
            request = self.context.get('request')
            obj._rendered_stream = render_stream(request, obj, True)
        return obj._rendered_stream

    def get_embed_html(self, obj):
        embed_html, _ = self._get_rendered_stream(obj)
        return embed_html

    def get_mirrors_html(self, obj):
        _, mirrors_html = self._get_rendered_stream(obj)
        return mirrors_html


class StreamInfoSerializer(DataclassSerializer):
    class Meta:
        dataclass = StreamInfo
        read_only_fields = [f.name for f in StreamInfo.__dataclass_fields__.values() if f.init is False]


class FormatInfoSerializer(DataclassSerializer):
    class Meta:
        dataclass = FormatInfo
        read_only_fields = [f.name for f in FormatInfo.__dataclass_fields__.values() if f.init is False]


class VideoAttributeSerializer(DataclassSerializer):
    streams = StreamInfoSerializer(many = True, read_only = True)
    format = FormatInfoSerializer(read_only = True)

    class Meta:
        dataclass = VideoAttribute
        read_only_fields = [
            f.name for f in VideoAttribute.__dataclass_fields__.values()
            if f.init is False and f.name not in ('streams', 'format')
        ]