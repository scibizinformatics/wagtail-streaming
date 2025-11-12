from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _ 

from wagtail.admin.auth import PermissionPolicyChecker
from wagtail.admin.forms.search import SearchForm
from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.admin.models import popular_tags_for_model
from wagtail.models import Collection

from ..models import get_stream_model
from ..permissions import perm_policy
from . import utils


perm_checker = PermissionPolicyChecker(perm_policy)
VideoStream = get_stream_model()


def chooser(request):
    ordering = utils.get_ordering(request)
    video_files = utils.get_video_queryset(request)

    form = {}
    if perm_policy.user_has_permission(request.user, 'add'):
        instance = VideoStream(uploaded_by = request.user)
        form = utils.init_form(request, instance, prefix = 'stream-chooser-upload')

    if {'q', 'p', 'tag', 'collection_id'} & set(request.GET.keys()):
        video_files, c = utils.filter_collection(request, video_files)
        searchform = SearchForm(request.GET)

        q = None
        searching = searchform.is_valid() and searchform.cleaned_data.get('q')
        if searching:
            video_files = video_files.search(q)
            q = searchform.cleaned_data.get('q')

        else:
            video_files = video_files.order_by(ordering)
            video_files, c = utils.filter_tag(request, video_files)

        paginator, video_files = utils.paginate(request, video_files)
        return render(
            request,
            'wagtailstreaming_templates/chooser/results.html',
            {
                'video_files': video_files,
                'query_str': q,
                'is_searching': searching, 
                'ordering': ordering,
            },
        )

    searchform = SearchForm()
    collections = utils.acceptable_collections_or_none(Collection.objects.all())
    video_files = video_files.order_by(ordering)
    paginator, video_files = utils.paginate(request, video_files)

    title = _('Choose video')

    return render_modal_workflow(
        request,
        'wagtailstreaming_templates/chooser/chooser.html',
        None,
        {
            'video_files': video_files, 
            'searchform': searchform, 
            'collections': collections, 
            'form': form, 
            'is_searching': False, 
            'popular_tags': popular_tags_for_model(VideoStream),
            'ordering': ordering,
            'title': title,
            'icon': 'media',
        },
        json_data = {
            'step': 'chooser',
            'error_label': 'Server Error',
            'error_message': _(
                'Report this error to the server owner with the following:'
            ),
            'tag_autocomplete_url': reverse('wagtailadmin_tag_autocomplete'),
        },
    )


def stream_selected(request, pk):
    stream = get_object_or_404(VideoStream, id = pk)
    return render_modal_workflow(
        request, None, None, None,
        json_data = {
            'step': 'video_chosen', 
            'result': utils.get_stream_json(stream)
        }
    )


@perm_checker.require('add')
def upload(request):
    form = None
    instance = VideoStream(uploaded_by_user = request.user)
    form = utils.init_form(request, instance, prefix = 'stream-chooser-upload')

    if all([
        request.method == 'POST', 
        perm_policy.user_has_permission(request.user, 'add'), 
        form.is_valid()
    ]):
        form.save()
        utils.reindex()

        return render_modal_workflow(
            request, None, None, None, 
            json_data = {
                'step': 'video_chosen', 
                'result': utils.get_stream_json(instance),
            }
        )

    ordering = utils.get_ordering(request)
    video_files = utils.get_video_queryset(request, ordering)
    searchform = SearchForm()
    collections = utils.acceptable_collections_or_none(Collection.objects.all())

    context = {
        'video_files': video_files, 
        'searchform': searchform, 
        'collections': collections, 
        'form': form, 
        'is_searching': False, 
        'ordering': ordering, 
    }

    return render_modal_workflow(
        request, 
        'wagtailstreaming_templates/chooser/chooser.html', 
        None, 
        context, 
        json_data = {
            'step': 'chooser'
        }
    )