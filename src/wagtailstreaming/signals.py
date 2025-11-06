from django.db.models.signals import pre_delete, pre_save
from django.utils.module_loading import import_string
from django.db import transaction

import logging
import typing
import shutil

from .models import VideoStream, get_stream_model
from .settings import stream_settings

LOGGER = logging.getLogger(__name__)


def clear_files(instance: VideoStream):
    if instance.hls_ready and instance.hls.root:
        shutil.rmtree(instance.hls.root)
    
    if instance.dash_ready and instance.dash.root:
        shutil.rmtree(instance.dash.root)

    if instance.file:
        instance.file.delete(save = False)

    if instance.thumbnail:
        instance.thumbnail.delete(save = False)


def get_cleanup() -> typing.Callable[[VideoStream], None]:
    action = clear_files
    path = stream_settings.FILE_CLEANUP
    if isinstance(path, str) and path:
        try:
            action = import_string(path)
        except Exception as e:
            LOGGER.error(f'Could not import FILE_CLEANUP callable: {e}')
    return action


def deletion_cleanup(
        instance: VideoStream, 
        **kwargs
    ):
    action = get_cleanup()
    transaction.on_commit(lambda: action(instance))


def change_cleanup(
        sender: typing.Type[VideoStream], 
        instance: VideoStream, 
        **kwargs
    ):
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk = instance.pk)

    except sender.DoesNotExist:
        return

    old_name = old.raw.name or ''
    new_name = instance.raw.name or ''

    if old_name != new_name and old_name:
        action = get_cleanup()
        transaction.on_commit(lambda: action(old))


def register_signals():
    model = get_stream_model()
    pre_delete.connect(deletion_cleanup, sender = model)
    pre_save.connect(change_cleanup, sender = model)