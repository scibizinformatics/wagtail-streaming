from django.contrib import admin

from .settings import stream_settings

if stream_settings.VIDEO_STREAM_MODEL in ['wagtailstreaming.VideoStream', '']:
    from .models import VideoStream

    class VideoStreamAdmin(admin.ModelAdmin):
        list_display = ['title', 'raw_ready', 'hls_ready', 'dash_ready', 'audio_ready', 'transcript_ready', 'uploaded_by']
        list_filter = ['hls_ready', 'dash_ready', 'audio_ready']

        def raw_ready(self, obj):
            return bool(obj.file)
        raw_ready.boolean = True
        
        def transcript_ready(self, obj):
            return obj.transcripts.exists()
        transcript_ready.boolean = True

    admin.site.register(VideoStream, VideoStreamAdmin)


from .models import Transcript, TranscriptCue

class TranscriptAdmin(admin.ModelAdmin):
    list_display = ['video', 'name', 'language', 'slug', 'default']
    list_filter = ['default', 'language']

admin.site.register(Transcript, TranscriptAdmin)


class TranscriptCueAdmin(admin.ModelAdmin):
    list_display = ['transcript', 'text_rep', 'synced']
    list_filter = ['synced', 'transcript']

    def text_rep(self, obj):
        return str(obj)

admin.site.register(TranscriptCue, TranscriptCueAdmin)