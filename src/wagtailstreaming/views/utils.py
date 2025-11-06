from django.db.models.fields.files import FieldFile
from django.core.paginator import Paginator, Page
from django.db.models import QuerySet
from django.urls import reverse, NoReverseMatch

from wagtail.search.backends import get_search_backends
from wagtail.models import Collection
from wagtail.admin import messages
from wagtail import hooks

import typing

from ..models import get_stream_model, VideoStream
from ..forms import get_stream_form, BaseStreamForm
from ..permissions import perm_policy


def get_stream_json(instance):
    return {
        'id': instance.id, 
        'title': instance.title, 
        'edit_url': reverse('wagtailstreaming:edit', args = (instance.id, )), 
    }


def get_ordering(request) -> str:
    ordering = request.GET.get('ordering', '-created_at')
    if ordering in ['title', '-title', 'created_at', '-created_at']:
        return ordering
    return '-created_at'


def paginate(request, items, key = 'p', n = 20):
    paginator = Paginator(items, n)
    page = paginator.get_page(request.GET.get(key, 1))
    return paginator, page


def get_video_queryset(request, ordering: typing.Optional[str] = None, enable_hooks: bool = True) -> QuerySet[VideoStream]:
    queryset = perm_policy.instances_user_has_any_permission_for(
        request.user, ['change', 'delete']
    )

    if enable_hooks:
        queryset = apply_hooks(request, queryset)

    if ordering:
        queryset = queryset.order_by(ordering)
    return queryset


def init_form(request, instance: typing.Optional[VideoStream] = None, **kwargs) -> BaseStreamForm:
    stream_model = instance.__class__ if instance else get_stream_model()
    StreamForm = get_stream_form(stream_model)
    if request.method == 'POST':
        return StreamForm(
            data = request.POST,
            files = request.FILES,
            user = request.user,
            instance = instance,
            **kwargs
        )
    return StreamForm(
        user = request.user,
        instance = instance,
        **kwargs
    )


def reindex(instance: VideoStream):
    for backend in get_search_backends():
        backend.add(instance)


def send_message(
        request, 
        message: str, 
        button_url: str = '', 
        button_txt: str = '', 
        success: bool = True
    ):
        buttons = None
        if button_url and button_txt:
            buttons = [
                messages.button(button_url, button_txt)
            ]

        method = messages.success if success else messages.error
        method(
            request, message, 
            buttons = buttons
        )


def get_file_size(file: FieldFile) -> typing.Optional[int]:
    if not file:
        return None
    
    try:
        return file.size
    except OSError:
        return None


def apply_hooks(
        request, stream_qset: QuerySet[VideoStream]
    ) -> QuerySet[VideoStream]:
    videos = stream_qset
    for hook in hooks.get_hooks('stream_chooser_queryset'):
        videos = hook(videos, request)
    return videos


def filter_collection(
        request, stream_qset: QuerySet[VideoStream]
    ) -> typing.Tuple[QuerySet[VideoStream], typing.Optional[Collection]]:

    collection = None
    collection_id = request.GET.get('collection_id')
    if collection_id:
        try:
            collection = Collection.objects.get(id = collection_id)
            return stream_qset.filter(collection = collection), collection

        except (TypeError, ValueError, Collection.DoesNotExist):
            pass
    return stream_qset, collection


def filter_tag(
        request, 
        stream_qset: QuerySet[VideoStream]
    ) -> typing.Tuple[QuerySet[VideoStream], typing.Optional[str]]:

    tag = request.GET.get('tag')
    if tag:
        return stream_qset.filter(tags__name = tag), tag
    return stream_qset, tag


def acceptable_collections_or_none(
        collections: QuerySet[Collection]
    ) -> typing.Optional[QuerySet[Collection]]:
    if collections.count() < 2:
        return None
    return collections