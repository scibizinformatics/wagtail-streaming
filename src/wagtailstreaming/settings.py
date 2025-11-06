from typing import Dict, Any
from django.conf import settings as user_settings
from django.test.signals import setting_changed
import warnings
import os

DEFAULTS = {
    # enablers
    'ALLOW_DASH': True, 
    'ALLOW_HLS': True, 
    'DISABLE_AUTO_CONVERSION': False, 

    # dirs and serving
    'DASH_ROOT': os.path.join(user_settings.BASE_DIR, 'dash'), 
    'HLS_ROOT': os.path.join(user_settings.BASE_DIR, 'hls'), 
    'DOWNLOAD_ROOT': os.path.join(user_settings.BASE_DIR, 'downloads'), 
    'DASH_URL': '/dash/', 
    'HLS_URL': '/hls/', 

    # meta and segmentation
    'RESOLUTIONS': [
        ("1920x1080", "5000k"), 
        ("1280x720", "2800k"), 
        ("842x480", "1400k"), 
        ("640x360", "800k"), 
        ("426x240", "400k"), 
    ], 
    'VIDEO_EXTENSIONS': [
        'mp4', 'm4v', 
    ], 
    'THUMBNAIL_EXTENSIONS': [
        'gif', 'jpg', 'jpeg', 'png', 'webp', 
    ], 

    # objects and functions
    'COLLECTION_PERMISSION_POLICY': '', 
    'VIDEO_STREAM_MODEL': '', 
    'FILE_CLEANUP': '', 
    'BASE_FORM': '', 
}
PREFIX = 'WAGTAILSTREAMING'


class StreamSettings:
    def __init__(self, defaults: Dict[str, Any] = None):
        self.defaults = defaults or DEFAULTS
        self._settings = {}
        self._errors = {}
        self.parse()

    def refresh(self):
        self._settings = {}
        self._errors = {}
        self.parse()

    def parse(self):
        self._settings = dict(self.defaults)

        overrides = getattr(user_settings, PREFIX, {})
        self._settings.update(overrides)

        for key in self.defaults.keys():
            flat = f'{PREFIX}_{key}'

            if hasattr(user_settings, flat):
                value = getattr(user_settings, flat)
                if self.acceptable(key, value):
                    self._settings[key] = value

                else:
                    self._errors[key] = (
                        f'Invalid type: expected {type(self.defaults[key]).__name__}, '
                        f'got {type(value).__name__} ({value!r})'
                    )

        if self._errors:
            for key, err in self._errors.items():
                warnings.warn(f'[{PREFIX}] Configuration error on {key} field, {err}')

    def acceptable(self, key: str, value: Any) -> bool:
        expected_type = type(self.defaults.get(key, None))
        if expected_type == list and isinstance(value, (tuple, list)):
            if key.lower() == 'resolutions':
                return self._acceptable_resolution_list(value)
            return self._acceptable_str_list(value)
        return isinstance(value, expected_type)
    
    def _acceptable_resolution_list(self, iter) -> bool:
        return all(
            isinstance(r, (tuple, list)) and
            len(r) == 2 and
            self._acceptable_str_list(r)
            for r in iter
        )
    
    def _acceptable_str_list(self, iter) -> bool:
        return all(isinstance(i, str) for i in iter)

    def __getattr__(self, attr):
        if attr in self._settings:
            return self._settings[attr]
        raise AttributeError(f'Invalid app setting: "{attr}"')

    def __getitem__(self, key):
        return self._settings[key]
    

stream_settings = StreamSettings(DEFAULTS)


def refresh_settings(*args, **kwargs):
    settings = kwargs['settings']
    if hasattr(settings, 'WAGTAILSTREAMING'):
        stream_settings.refresh()
        return

    for key in dir(settings):
        if key.startswith("WAGTAILSTREAMING_"):
            stream_settings.refresh()
            break


setting_changed.connect(refresh_settings)