from django.utils.translation import gettext_lazy as _
from django.core.files import File
from django.urls import reverse
from django.db import models
from django.apps import apps
from django.core.exceptions import (
    ImproperlyConfigured, 
    ValidationError, 
)

from wagtail.search.queryset import SearchableQuerySetMixin
from wagtail.admin.panels import FieldPanel
from wagtail.search import index
from wagtail.models import (
    CollectionMember, 
    ReferenceIndex, 
)

from taggit.managers import TaggableManager

import logging
import typing
import os

from .conversion_utils import (
    _res_str_to_values, 
    check_attributes, 
    create_thumbnail, 
)
from .dataclasses import (
    VideoAttribute, 
    Duration, 
    Progress, 
    DASH, 
    RAW, 
    HLS, 
)
from .validators import (
    VideoFileValidator, 
    PhotoFileValidator
)
from .settings import (
    stream_settings, 
    user_settings
)
from .utils import (
    format_statement, 
    get_seconds_done, 
    get_txt_files,
    create_dir, 
    hash_this, 
)

LOGGER = logging.getLogger(__name__)


class VideoStreamQuerySet(
        models.QuerySet, 
        SearchableQuerySetMixin
    ):
    ...


class VideoStream(
        CollectionMember, 
        index.Indexed, 
        models.Model
    ):
    """Model for auto-generating streaming formats (HLS, MPEG-DASH)"""

    title = models.CharField(
        max_length = 255, 
        unique = True, 
        verbose_name = _('title'), 
        help_text = _('the title of the video')
    )

    file = models.FileField(
        upload_to = 'videos', 
        null = True, blank = True, 
        verbose_name = _('file'), 
        help_text = _('the video that is going to be processed or that has been processed, video must be lower or equal to 100MB')
    )

    file_url = models.URLField(
        max_length = 255, 
        null = True, blank = True, 
        verbose_name = _('file URL'), 
        help_text = _('the link that contains the video when video is greater than 100MB')
    )

    thumbnail = models.FileField(
        upload_to = 'media_thumbnails', 
        null = True, blank = True, 
        verbose_name = _('thumbnail'),
        help_text = _('the thumbail of the video')
    )

    process_id = models.IntegerField(
        blank = True, null = True, 
        verbose_name = _('process ID'), 
        help_text = _('the process id where the video is being processed')
    )

    hls_ready = models.BooleanField(
        default = False,
        verbose_name = _('has HLS format'), 
        help_text = _('marked if the raw video has been converted to HLS format')
    )

    dash_ready = models.BooleanField(
        default = False,
        verbose_name = _('has MPEG-DASH format'),
        help_text = _('marked if the raw video has been converted to MPEG-DASH format')
    )

    uploaded_by = models.ForeignKey(
        user_settings.AUTH_USER_MODEL, 
        on_delete = models.SET_NULL, 
        null = True, blank = True, editable = False, 
        verbose_name = _('uploaded by user'), 
        help_text = _('the user that uploaded the video')
    )

    tags = TaggableManager(
        blank = True, 
        verbose_name = _('tags'),
        help_text = _('tags that relates to the video, separate each tag via commas')
    )

    created_at = models.DateTimeField(
        auto_now_add = True, 
        verbose_name = _('created at'), 
        help_text = _('the date in which the video has been uploaded')
    )

    date_processed = models.DateTimeField(
        null = True, blank = True, 
        verbose_name = _('start of conversion'), 
        help_text = _('the date in which the video has started its conversion to HLS or DASH format')
    )
    
    date_finished = models.DateTimeField(
        null = True, blank = True,
        verbose_name = _('conversion finished at'),
        help_text = _('the date in which the video was done converting')
    )

    remarks = models.TextField(
        null = True, blank = True,
        verbose_name = _('remarks'), 
        help_text = _('message logs or audit logs related to the video')
    )

    objects = VideoStreamQuerySet.as_manager()

    panels = [
        FieldPanel('title'),
        FieldPanel('file'), 
        FieldPanel('file_url'), 
        FieldPanel('thumbnail'), 
        FieldPanel('tags'), 
    ]

    search_fields = CollectionMember.search_fields + [
        index.SearchField('title', boost = 5),
        index.AutocompleteField('title', boost = 5),
        index.FilterField('title'),
        index.FilterField('uploaded_by'),
        index.RelatedFields(
            'tags', [
                index.SearchField('name', boost = 5),
                index.AutocompleteField('name', boost = 5),
            ]
        ),
    ]

    form_fields = [
        'title', 
        'file', 
        'file_url', 
        'thumbnail', 
        'tags', 
    ]

    body_fields = [
        'title', 
        'collection',
    ]

    meta_fields = [
        'tags', 
        'modes', 
        'stream_urls', 
        'thumbnail_url', 
        'embed_url', 
    ]

    listing_default_fields = [
        'title', 
        'modes', 
        'tags', 
        'thumbnail_url', 
    ]

    nested_default_fields = [
        'title', 
        'thumbnail_url', 
    ]

    detail_only_fields = []

    def __str__(self) -> str:
        return self.title

    @property
    def hashed_id(self) -> str:
        return hash_this(self.id) if self.id else ''

    @property
    def download_root(self) -> str:
        if any((
            self.file, 
            not self.file_url, 
            not self.id
        )):
            return ''
        
        path = os.path.join(stream_settings.DOWNLOAD_ROOT, self.hashed_id)
        return create_dir(path)

    @property
    def attrs(self) -> VideoAttribute:
        if not self.file:
            return VideoAttribute()
        return VideoAttribute(raw = check_attributes(self.file.path) or {})

    @property
    def raw(self) -> RAW:
        if not all([
            self.file, 
            self.id
        ]):
            return RAW()

        return RAW(
            _file = self.file, 
            path = self.file.path, 
            url = self.file.url
        )

    @property
    def hls(self) -> HLS:
        if not all((
            stream_settings.ALLOW_HLS, 
            self.raw.file_root, 
            self.id
        )):
            return HLS()
        
        path = os.path.join(stream_settings.HLS_ROOT, self.hashed_id)
        return HLS(root = create_dir(path))

    @property
    def dash(self) -> DASH:
        if not all((
            stream_settings.ALLOW_DASH, 
            self.raw.file_root, 
            self.id
        )):
            return DASH()

        path = os.path.join(stream_settings.DASH_ROOT, self.hashed_id)
        return DASH(root = create_dir(path))

    @property
    def duration(self) -> Duration:
        if not self.file:
            return Duration()
        return Duration(duration = self.attrs.format.duration or 0.0)

    @property
    def supported_resolutions(self) -> typing.List[typing.Tuple[str, str]]:
        resolutions = []
        if len(self.attrs.streams) <= 0:
            return resolutions
        
        height = self.attrs.streams[0].height
        if not height:
            return resolutions
        
        for r in stream_settings.RESOLUTIONS:
            res, _ = r
            _, h = _res_str_to_values(res)

            if h <= height:
                resolutions.append(r)
        return resolutions
    
    @property
    def supported_streams(self) -> typing.List[str]:
        modes = []
        if self.file:
            modes.append('raw')
        
        if self.hls_ready:
            modes.append('hls')

        if self.dash_ready:
            modes.appand('dash')
        return modes

    @property
    def progress(self) -> Progress:
        if not self.date_processed:
            return Progress()

        return Progress(
            hls_ready = self.hls_ready, 
            dash_ready = self.dash_ready, 
            hls_root = self.hls.root, 
            dash_root = self.dash.root, 
            total_duration = self.duration.duration, 
            resolutions = self.supported_resolutions
        )

    @property
    def usage(self):
        return reverse('wagtailstreaming:stream_usage', args = (self.id,))
    
    @property
    def usage_count(self) -> int:
        refs = ReferenceIndex.get_references_to(self)
        return refs.count()

    def can_be_edited_by(self, user) -> bool:
        from .permissions import perm_policy
        return perm_policy.user_has_permission_for_instance(user, 'change', self)

    def get_usage(self):
        return ReferenceIndex.get_references_to(self).group_by_source_object()

    def _populate_thumbnail(self) -> bool:
        if self.thumbnail:
            return True
        
        thumbnail_dir = create_dir(os.path.join(user_settings.MEDIA_ROOT, 'temp_thumbnails'))
        root = self.raw.file_root
        if not root:
            return False
            
        thumbnail_path = os.path.join(thumbnail_dir, f'thumbnail_{root}.png')
        if create_thumbnail(self.raw.path, thumbnail_path):
            with open(thumbnail_path, 'rb') as f:
                self.thumbnail.save(os.path.basename(thumbnail_path), File(f), save = False)

            self.save(update_fields = ['thumbnail'])
            os.remove(thumbnail_path)
            return True
        return False

    def add_remark(self, statement: str):
        if self.remarks:
            self.remarks = f'{self.remarks}, "{format_statement(statement)}"'
        else:
            self.remarks = f'"{format_statement(statement)}"'
        self.save(update_fields = ['remarks'])

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        if not self.file and not self.file_url:
            raise ValidationError('Either a video or a google drive link of the video must be provided!')
        
        if self.thumbnail:
            validate = PhotoFileValidator(stream_settings.THUMBNAIL_EXTENSIONS)
            validate(self.thumbnail)
        
        if self.file:
            validate = VideoFileValidator(stream_settings.VIDEO_EXTENSIONS)
            validate(self.file)

    class Meta:
        verbose_name = _('video stream')
        ordering = ['title']


def get_stream_model() -> typing.Type[VideoStream]:
    cust_model = stream_settings.VIDEO_STREAM_MODEL
    if isinstance(cust_model, str) and cust_model:
        try:
            a, m = cust_model.split('.')
            s_model = apps.get_model(a, m)

            if not s_model:
                raise ImproperlyConfigured(f'WAGTAILSTREAMING VIDEO_STREAM_MODEL setting contains a model that has not been installed yet which is {cust_model}')
            return s_model
        
        except ValueError as e:
            raise ImproperlyConfigured(f'WAGTAILSTREAMING VIDEO_STREAM_MODEL setting must be written as "your_app.you_model_name": {e}')
    return VideoStream