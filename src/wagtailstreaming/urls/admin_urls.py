from django.urls import path
from ..views import chooser, stream


urlpatterns = [
    path('', stream.index, name = 'index'), 
    path('add/', stream.add, name = 'add'), 
    path('edit/<int:pk>/', stream.edit, name = 'edit'), 
    path('delete/<int:pk>/', stream.delete, name = 'delete'), 
    path('chooser/', chooser.chooser, name = 'chooser'), 
    path('chooser/<int:pk>/', chooser.stream_selected, name = 'stream_chosen'), 
    path('chooser/upload/', chooser.upload, name = 'chooser_upload'), 
    path('usage/<int:pk>/', stream.usage, name = 'stream_usage'), 
]