from django.urls import path
from ..views import embed


app_name = 'wagtailstreaming_public'

urlpatterns = [
    path('embed/<int:pk>/', embed.embed, name = 'embed'),
]