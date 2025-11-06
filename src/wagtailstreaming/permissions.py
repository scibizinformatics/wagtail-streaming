from wagtail.permission_policies.collections import CollectionOwnershipPermissionPolicy
from django.utils.module_loading import import_string

from typing import Type
import warnings

from .models import VideoStream, get_stream_model
from .settings import stream_settings


def get_policy_or_default() -> Type[CollectionOwnershipPermissionPolicy]:
    path = stream_settings.COLLECTION_PERMISSION_POLICY
    if isinstance(path, str) and path:
        try:
            return import_string(path)
        
        except ImportError as e:
            warnings.warn(f'[WAGTAILSTREAMING] Could not import COLLECTION_PERMISSION_POLICY class: {e}')
    return CollectionOwnershipPermissionPolicy

POLICY_CLASS = get_policy_or_default()
STREAM_CLASS = get_stream_model()


perm_policy = POLICY_CLASS(
    STREAM_CLASS, 
    auth_model = VideoStream, 
    owner_field_name = 'uploaded_by'
)