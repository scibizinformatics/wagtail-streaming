from django.contrib import admin

from .settings import stream_settings

if stream_settings.VIDEO_STREAM_MODEL in ['wagtailstreaming.VideoStream', '']:
    from .models import VideoStream

    class VideoStreamAdmin(admin.ModelAdmin):
        list_display = ['title', 'raw_ready', 'hls_ready', 'dash_ready', 'transcript_ready', 'uploaded_by']
        list_filter = ['hls_ready', 'dash_ready', 'transcript_ready']

        def raw_ready(self, obj):
            return bool(obj.file)
        raw_ready.boolean = True

    admin.site.register(VideoStream, VideoStreamAdmin)


from .models import Transcript

class TranscriptAdmin(admin.ModelAdmin):
    list_display = ['video', 'language', 'text_rep']
    list_filter = ['language'],

    def text_rep(self, obj):
        return str(obj)

admin.site.register(Transcript, TranscriptAdmin)