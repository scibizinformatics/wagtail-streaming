from django.urls import include


def include_public_urlpatterns():
    return include(
        'wagtailstreaming.urls._public_urls', 
        namespace = 'wagtailstreaming_public'
    )