from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django.views.decorators.vary import vary_on_headers

from wagtail.admin.admin_url_finder import AdminURLFinder
from wagtail.admin.auth import PermissionPolicyChecker, permission_denied
from wagtail.admin.forms.search import SearchForm
from wagtail.admin.models import popular_tags_for_model
from wagtail.models import Page

import logging

from ..models import get_stream_model
from ..permissions import perm_policy
from ..signals import deletion_cleanup
from . import utils


LOGGER = logging.getLogger(__name__)
perm_checker = PermissionPolicyChecker(perm_policy)
VideoStream = get_stream_model()


@perm_checker.require_any('add', 'change', 'delete')
@vary_on_headers('X-Requested-With')
def index(request):
    ordering = utils.get_ordering(request)
    video_files = utils.get_video_queryset(request, ordering, False)
    video_files, collection = utils.filter_collection(request, video_files)
    
    query_str = request.GET.get('q', '').strip()
    form = SearchForm(
        request.GET or None, 
        placeholder = _('Search videos')
    )
    if query_str and form.is_valid():
        video_files = video_files.search(query_str)

    video_files, tag = utils.filter_tag(request, video_files)
    paginator, video_files = utils.paginate(request, video_files)

    collections = utils.acceptable_collections_or_none(
        perm_policy.collections_user_has_any_permission_for(
            request.user, ['add', 'change']
        )
    )

    context = {
        'ordering': ordering, 
        'video_files': video_files, 
        'query_str': query_str, 
        'is_searching': bool(query_str), 
        'collections': collections, 
        'search_form': form, 
        'pop_tags': popular_tags_for_model(VideoStream), 
        'current_tag': tag, 
        'user_has_perm': perm_policy.user_has_permission(
            request.user, 'add'
        ), 
        'current_collection': collection, 
    }

    template = 'wagtailstreaming_templates/instances/index.html'
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        template = 'wagtailstreaming_templates/instances/results.html'

    return render(request, template, context)


@perm_checker.require('add')
def add(request):
    instance = VideoStream(uploaded_by = request.user)
    form = utils.init_form(request, instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        utils.reindex(instance)
        utils.send_message(
            request, _('Video file "{}" added.').format(instance.title), 
            reverse('wagtailstreaming:edit', args = (instance.id, )), 
            _('Edit')
        )

        return redirect('wagtailstreaming:index')
    
    elif request.method == 'POST':
        utils.send_message(
            request, _('An error occurred while saving the video.'), 
            success = False
        )

    return render(
        request, 
        'wagtailstreaming_templates/instances/add.html', 
        { 'form': form }
    )


@perm_checker.require('change')
def edit(request, pk):
    instance = get_object_or_404(VideoStream, id = pk)
    form = utils.init_form(request, instance)
    if not perm_policy.user_has_permission_for_instance(
        request.user, 
        'change', 
        instance
    ):
        return permission_denied(request)
    
    if request.method == 'POST' and form.is_valid():
        if {'file', 'file_url'} & set(form.changed_data):
            deletion_cleanup(instance)
        instance = form.save()
        utils.reindex(instance)
        utils.send_message(
            request, _('Video file "{}" updated').format(instance.title), 
            reverse('wagtailstreaming:edit', args = (instance.id, )), 
            _('Edit')
        )

        return redirect('wagtailstreaming:index')

    elif request.method == 'POST':
        utils.send_message(
            request, _('An error occurred while saving the changes.'), 
            success = False
        )

    file_size = utils.get_file_size(instance.file)
    if not file_size:
        utils.send_message(
            request, _('Video file could not be found.'), 
            reverse('wagtailstreaming:delete', args = (instance.id, )), 
            _('Delete'), success = False
        )

    context = {
        'instance': instance, 
        'size': file_size, 
        'form': form, 
        'user_can_delete': perm_policy.user_has_permission_for_instance(
            request.user, 
            'delete', 
            instance
        ),
    }

    return render(
        request, 
        'wagtailstreaming_templates/instances/edit.html', 
        context
    )


@perm_checker.require('delete')
def delete(request, pk):
    instance = get_object_or_404(VideoStream, id = pk)

    if not perm_policy.user_has_any_permission_for_instance(
        request.user, 
        'delete', 
        instance
    ):
        return permission_denied(request)
    
    if request.method == 'POST':
        instance.delete()
        utils.send_message(
            request, _('Video file "{}" deleted.').format(instance.title)
        )

        return redirect('wagtailstreaming:index')
    
    return render(
        request, 
        'wagtailstreaming_templates/instances/delete.html', 
        { 'instance': instance }, 
    )


@perm_checker.require_any('add', 'change', 'delete')
def usage(request, pk):
    instance = get_object_or_404(VideoStream, id = pk)
    paginator = Paginator(instance.get_usage(), per_page = 20)
    page = paginator.get_page(request.GET.get('p'))

    admin_urls = AdminURLFinder(request.user)
    results = []
    for ent, ref in page:
        edit_url = admin_urls.get_edit_url(ent)
        verbose_meta = ent._meta.verbose_name

        label = _('(Private {})').format(verbose_meta)
        link_title = None

        if edit_url is not None:
            label = str(ent)
            link_title = _('Edit this {}'.format(verbose_meta))

        verbose_name = capfirst(
            ent.specific_class._meta.verbose_name if isinstance(ent, Page) else verbose_meta
        )

        results.append((
            label, 
            edit_url, 
            link_title, 
            verbose_name, 
            ref
        ))

    context = {
        'instance': instance, 
        'results': results, 
        'page': page
    }

    return render(
        request, 
        'wagtailstreaming_templates/instances/usage.html', 
        context
    )