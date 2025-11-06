from django.db.models import QuerySet, Q
from django.utils import timezone
from django.apps import apps

from abc import ABC, abstractmethod
from datetime import timedelta
import logging
import typing
import json

from .models import VideoStream, get_stream_model
from .settings import stream_settings

LOGGER = logging.getLogger(__name__)


stream_class = get_stream_model()


def celery_beat_installed() -> bool:
    """Checks if `django_celery_beat` is enlisted into `INSTALLED_APPS` in settings"""
    return apps.is_installed('django_celery_beat')


def schedule(min: int = 5):
    """Creates a ClockedScedule instance"""
    if not celery_beat_installed():
        LOGGER.warning('Skipping schedule(): django_celery_beat is not installed')
        return None
    
    from django_celery_beat.models import ClockedSchedule
    when = timezone.now() + timedelta(minutes = min)
    return ClockedSchedule.objects.create(clocked_time = when)


def create_task(
        name: str, 
        task: str, 
        min: int, 
        args: typing.List[typing.Any] = []
    ):
    """Creates a clocked PeriodicTask in `django-celery-beat`"""
    if not celery_beat_installed():
        LOGGER.warning('Skipping create_task(): django_celery_beat is not installed')
        return None
    
    from django_celery_beat.models import PeriodicTask
    return PeriodicTask.objects.create(
        clocked = schedule(min),
        name = name,
        task = task,
        args = json.dumps(args),
        one_off = True,
    )


def cancel_task(name: str) -> bool:
    if celery_beat_installed():
        from django_celery_beat.models import PeriodicTask

        PeriodicTask.objects.filter(name = name).delete()
        return True
    return False


def _create_sched(
        task_name: str, 
        stream_instance: VideoStream
    ):
    """Creates a scheduled task for a certain instance"""
    label = f'{task_name} {stream_instance.title} {stream_instance.id}'

    try:
        create_task(label, task_name, 1, args = [stream_instance.id])
    
    except Exception as e:
        LOGGER.error(f'Failed to create task {label}: {e}')


def sched_conversion(stream_instance: VideoStream) -> bool:
    """Schedules a conversion task"""
    if not celery_beat_installed():
        LOGGER.warning('Skipping sched_conversion(): django_celery_beat is not installed')
        return False
    _create_sched('wagtailstreaming_convert_video', stream_instance)
    return True


def sched_thumbnail(stream_instance: VideoStream) -> bool:
    """Schedules a thumbnail creation task"""
    if not celery_beat_installed():
        LOGGER.warning('Skipping sched_thumbnail(): django_celery_beat is not installed')
        return False
    _create_sched('wagtailstreaming_create_thumbnail', stream_instance)
    return True


def sched_download(stream_instance: VideoStream) -> bool:
    """Schedules a download task"""
    if not celery_beat_installed():
        LOGGER.warning('Skipping sched_download(): django_celery_beat is not installed')
        return False
    _create_sched('wagtailstreaming_download_video', stream_instance)
    return True


class QueueManager(ABC):
    @property
    def stream_instances(self) -> QuerySet[VideoStream]:
        """Provides the ordered version of the video stream instances"""
        return self.get_stream_instances().order_by('created_at', 'id')

    @abstractmethod
    def get_stream_instances(self) -> QuerySet[VideoStream]:
        """Provices the queryset video stream instances"""
        return stream_class.objects.all()

    @property
    def front(self) -> typing.Optional[VideoStream]:
        """Provides the earliest instance"""
        return self.stream_instances.first()
    
    def next(self, instance: VideoStream) -> typing.Optional[VideoStream]:
        """Provides the next instance"""
        next_instance = self.stream_instances.filter(
            Q(created_at__gt = instance.created_at) |
            Q(created_at = instance.created_at, id__gt = instance.id)
        ).order_by('created_at', 'id').first()

        if not next_instance: # circles back
            next_instance = self.front
        return next_instance


class DownloadQueueManager(QueueManager):
    def get_stream_instances(self):
        return super().get_stream_instances().filter(
            file__isnull = True, 
            file_url__isnull = False
        )

    @property
    def ongoing(self) -> typing.Optional[VideoStream]:
        return self.stream_instances.filter(file_url__icontains = '[DOWNLOADING]').first()


class UploadQueueManager(QueueManager):
    def get_stream_instances(self):
        qset = super().get_stream_instances()

        if stream_settings.ALLOW_HLS and stream_settings.ALLOW_DASH:
            qset = qset.filter(Q(hls_ready = False) | Q(dash_ready = False))

        elif stream_settings.ALLOW_HLS:
            qset = qset.filter(hls_ready = False)

        elif stream_settings.ALLOW_DASH:
            qset = qset.filter(dash_ready = False)

        else: # invalid
            return stream_class.objects.none()
        return qset
    
    @property
    def ongoing(self) -> typing.Optional[VideoStream]:
        return self.stream_instances.filter(process_id__isnull = False).first()


download_queue = DownloadQueueManager()
upload_queue = UploadQueueManager()


def go_next(queue: QueueManager, instance: VideoStream, scheduler: typing.Callable[[VideoStream], None]):
    next = queue.next(instance)
    if next:
        scheduler(instance)
    else:
        LOGGER.info('There are no more videos left to be processed')