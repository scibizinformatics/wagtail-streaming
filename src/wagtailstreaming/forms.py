from django.utils.translation import gettext_lazy as _
from django.utils.module_loading import import_string
from django.forms.models import modelform_factory
from django.db import models
from django import forms

from wagtail.admin.forms.collections import (
    collection_member_permission_formset_factory, 
    BaseCollectionMemberForm, 
    CollectionChoiceField, 
)
from wagtail.models import Collection
from wagtail.admin import widgets

from typing import Type
import logging
 
from .settings import stream_settings
from .permissions import perm_policy
from .models import VideoStream
from .utils import get_list_fields_or_default

LOGGER = logging.getLogger(__name__)


class BaseStreamForm(BaseCollectionMemberForm):
    permission_policy = perm_policy

    class Meta:
        widgets = {
            'file': forms.ClearableFileInput(attrs = {
                'accept': 'video/*', 
                'class': 'file-input'
            }), 
            'file_url': forms.URLInput(attrs = {
                'placeholder': 'https://drive.google.com/uc/?id=1234567890', 
                'class': 'url-input'
            }), 
            'thumbnail': forms.ClearableFileInput(attrs = {
                'accept': 'image/*', 
                'class': 'file-input'
            }), 
            'tags': widgets.AdminTagWidget(attrs = {
                'placeholder': 'Add some tags', 
                'class': 'tag-input',
            }), 
        }


def formfield_callback(
        db_field: models.Field, 
        **kwargs
    ) -> forms.Field:
    if db_field.name == 'collection':
        return CollectionChoiceField(
            label = _('collection'), 
            queryset = Collection.objects.all(), 
            empty_label = None, 
            **kwargs, 
        )
    return db_field.formfield(**kwargs)


def get_base_form() -> Type[BaseStreamForm]:
    base_form_str = stream_settings.BASE_FORM
    base_form = BaseStreamForm

    if isinstance(base_form_str, str) and base_form_str:
        try:
            base_form = import_string(base_form_str)
        except ImportError as e:
            LOGGER.error(f'Could not import {base_form_str}: {e}')
    return base_form


def get_stream_form(model: Type[VideoStream]) -> Type[BaseStreamForm]:
    fields = get_list_fields_or_default(model, 'form_fields', VideoStream.form_fields)
    if 'collection' not in fields:
        fields.append('collection')

    form = get_base_form()
    return modelform_factory(
        model = model, form = form, fields = fields, 
        formfield_callback = formfield_callback
    )


GroupPermissionFormSet = collection_member_permission_formset_factory(
    VideoStream, [
        ('add_stream', _('add'), _('add or edit a stream')), 
        ('change_stream', _('edit'), _('edit any stream')),
    ], 
    'wagtailstreaming_templates/permissions/stream_perm_formset.html', 
)