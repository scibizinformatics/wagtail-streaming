from wagtail.admin.panels import FieldPanel
from .widgets import AdminVideoStreamChooser


class StreamChooserPanel(FieldPanel):
    object_type_name = 'videostream'

    def __init__(self, field_name, **kwargs):
        kwargs.setdefault('widget', AdminVideoStreamChooser)
        return super().__init__(field_name, **kwargs)