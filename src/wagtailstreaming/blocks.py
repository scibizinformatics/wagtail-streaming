from django.template.loader import render_to_string
from django.forms import ModelChoiceField

from wagtail.admin.compare import BlockComparison
from wagtail.blocks import ChooserBlock

from .views.embed import render_player
from .models import get_stream_model
from .widgets import AdminVideoStreamChooser


class VideoStreamChooserBlockComparison(BlockComparison):
    def _render_comparison(self, obj_a, obj_b) -> str:
        return render_to_string(
            'wagtailstreaming_templates/widgets/compare.html', 
            {
                'obj_a': self.block.render_basic(obj_a),
                'obj_b': self.block.render_basic(obj_b)
            }
        )

    def htmlvalue(self, val):
        return self._render_comparison(val, val)

    def htmldiff(self):
        return self._render_comparison(self.val_a, self.val_b)


class VideoStreamChooserBlock(ChooserBlock):
    target_model = get_stream_model()
    widget = AdminVideoStreamChooser()

    def render_basic(self, value, context = None) -> str:
        if not value:
            return ''
        return render_player(None, value)

    def get_comparison_class(self):
        return VideoStreamChooserBlockComparison

    class Meta:
        icon = 'media'