from django.apps import AppConfig
from django.db import models


class WagtailstreamingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wagtailstreaming'
    
    def ready(self):
        from wagtail.admin.compare import register_comparison_class
        from .panels import VideoStreamFieldComparison
        from .signals import register_signals
        from .models import get_stream_model

        register_signals()
        stream_model = get_stream_model()
        register_comparison_class(
            models.ForeignKey, 
            to = stream_model, 
            comparison_class = VideoStreamFieldComparison
        )