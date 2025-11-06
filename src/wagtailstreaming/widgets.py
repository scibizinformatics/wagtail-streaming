from django import forms
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from wagtail.admin.widgets import BaseChooser, BaseChooserAdapter
from wagtail.telepath import register
from wagtail.admin.staticfiles import versioned_static

import json

from .models import get_stream_model


class AdminVideoStreamChooser(BaseChooser):
    choose_one_text = _('choose a video')
    choose_another_text = _('choose another video')
    chooser_modal_url_name = 'wagtailstreaming:chooser'
    link_to_chosen_text = _('edit this video')
    icon = 'media'
    classname = 'video-stream-chooser'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = get_stream_model()

    def get_value_data(self, value = None):
        if not value:
            return None

        if hasattr(value, "pk"):
            return {
                "id": value.pk,
                "title": value.title,
                "edit_url": f"/admin/videos/{value.pk}/edit/",
            }

        from .models import get_stream_model
        stream_model = get_stream_model()
        instance = stream_model.objects.filter(pk = value).first()
        if instance:
            return {
                'id': instance.pk, 
                'title': instance.title, 
                'edit_url': reverse('wagtailstreaming:edit', args = (value, ))
            }
        return None
    
    def get_chooser_modal_url(self):
        return reverse('wagtailstreaming:chooser')

    def render_js_init(self, id_, name, value_data):
        return f'createStreamChooser({json.dumps(id_)});'
    
    @property
    def media(self):
        return forms.Media(
            js = [
                "wagtailstreaming/js/modal.js",
                "wagtailstreaming/js/chooser.js",
            ]
        )


class VideoStreamChooserAdapter(BaseChooserAdapter):
    js_constructor = 'wagtailstreaming.StreamChooser'

    @property
    def media(self):
        return forms.Media(
            js = [
                versioned_static('wagtailstreaming/js/telepath.js')
            ]
        )

register(VideoStreamChooserAdapter(), AdminVideoStreamChooser)