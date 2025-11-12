from rest_framework.decorators import action
from rest_framework.response import Response
from django.urls import path

from wagtail.api.v2.filters import FieldsFilter, OrderingFilter, SearchFilter
from wagtail.api.v2.views import BaseAPIViewSet

import logging

from .serializers import VideoStreamSerializer, StreamHTMLSerializer, VideoAttributeSerializer
from ..models import VideoStream, get_stream_model
from ..utils import get_list_fields_or_default


LOGGER = logging.getLogger(__name__)
stream_model = get_stream_model()
    

class VideoStreamAPIViewSet(BaseAPIViewSet):
    name = 'videos'
    model = stream_model
    base_serializer_class = VideoStreamSerializer

    filter_backends = [
        FieldsFilter, 
        OrderingFilter, 
        SearchFilter
    ]

    body_fields = BaseAPIViewSet.body_fields + get_list_fields_or_default(stream_model, 'body_fields', VideoStream.body_fields)
    meta_fields = BaseAPIViewSet.meta_fields + get_list_fields_or_default(stream_model, 'meta_fields', VideoStream.meta_fields)
    listing_default_fields = BaseAPIViewSet.listing_default_fields + get_list_fields_or_default(stream_model, 'listing_default_fields', VideoStream.listing_default_fields)
    nested_default_fields = BaseAPIViewSet.nested_default_fields + get_list_fields_or_default(stream_model, 'nested_default_fields', VideoStream.nested_default_fields)
    detail_only_fields = BaseAPIViewSet.detail_only_fields + get_list_fields_or_default(stream_model, 'detail_only_fields', VideoStream.detail_only_fields)

    @action(detail = True, methods = ['get'])
    def streams(self, request, pk = None):
        instance = self.get_object()
        serializer = StreamHTMLSerializer(
            instance, context = {'request': request}
        )
        return Response(serializer.data)

    @action(detail = True, methods = ['get'])
    def attributes(self, request, pk = None):
        instance = self.get_object()
        serializer = VideoAttributeSerializer(instance.attrs)
        return Response(serializer.data)

    @classmethod
    def get_urlpatterns(cls):
        urlpatterns = super().get_urlpatterns()
        urlpatterns += [
            path('<int:pk>/streams/', cls.as_view({'get': 'streams'}), name = 'streams'),
            path('<int:pk>/attributes/', cls.as_view({'get': 'attributes'}), name = 'attributes'),
        ]

        return urlpatterns