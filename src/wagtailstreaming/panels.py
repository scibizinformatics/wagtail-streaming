from django.template.loader import render_to_string
from wagtail.admin.compare import ForeignObjectComparison
from wagtail.admin.panels import FieldPanel

from typing import Dict, Any

from .widgets import AdminVideoStreamChooser
from .views.embed import render_player


class VideoStreamChooserPanel(FieldPanel):
    object_type_name = 'stream'

    def get_form_options(self) -> Dict[str, Any]:
        options = super().get_form_options()
        if 'widgets' not in options:
            options['widgets'] = {}

        options['widgets'][self.field_name] = AdminVideoStreamChooser
        return options
    

class VideoStreamFieldComparison(ForeignObjectComparison):
    def htmldiff(self):
        obj_a, obj_b = self.get_objects()
        if not all([obj_a, obj_b]):
            return ''

        context = {
            'obj_a': render_player(None, obj_a),
            'obj_b': render_player(None, obj_b),
        }

        return render_to_string('wagtailstreaming_templates/widgets/compare.html', context)