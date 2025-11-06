from django.urls import include, path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from wagtail import hooks
from wagtail.admin.admin_url_finder import (
    ModelAdminURLFinder,
    register_admin_url_finder,
)
from wagtail.admin.menu import MenuItem
from wagtail.admin.navigation import get_site_for_user
from wagtail.admin.search import SearchArea
from wagtail.admin.site_summary import SummaryItem
from wagtail.admin.staticfiles import versioned_static

from .urls import admin_urls
from .forms import GroupPermissionFormSet
from .models import get_stream_model
from .permissions import perm_policy



stream_model = get_stream_model()


class StreamMenuItem(MenuItem):
    def is_shown(self, request):
        return perm_policy.user_has_any_permission(
            request.user, ["add", "change", "delete"]
        )


class StreamSummaryItem(SummaryItem):
    order = 300
    template_name = "wagtailstreaming_templates/homepage/summary.html"

    def get_context_data(self, parent_context):
        site_name = get_site_for_user(self.request.user)["site_name"]
        total_instances = perm_policy.instances_user_has_any_permission_for(
            self.request.user, 
            ["add", "change", "delete", "choose"]
        ).count()

        return {
            "total_instances": total_instances,
            "site_name": site_name,
        }

    def is_shown(self):
        return perm_policy.user_has_any_permission(
            self.request.user, 
            ["add", "change", "delete"]
        )


class StreamSearchArea(SearchArea):
    def is_shown(self, request):
        return perm_policy.user_has_any_permission(
            request.user, 
            ["add", "change", "delete"]
        )


class StreamAdminURLFinder(ModelAdminURLFinder):
    permission_policy = perm_policy
    edit_url_name = "wagtailstreaming:edit"


@hooks.register("register_admin_urls")
def register_urls():
    return [
        path(
            "videos/", 
            include(
                (admin_urls, "wagtailstreaming"), 
                namespace = "wagtailstreaming"
            )
        ),
    ]


@hooks.register("register_admin_menu_item")
def register_menu_item():
    return StreamMenuItem(
        _("Videos"),
        reverse("wagtailstreaming:index"),
        name = "videos",
        icon_name = "media",
        order = 300,
    )


@hooks.register("construct_homepage_summary_items")
def add_summary_item(request, items):
    items.append(StreamSummaryItem(request))


@hooks.register("register_admin_search_area")
def register_search_area():
    return StreamSearchArea(
        _("Videos"),
        reverse("wagtailstreaming:index"),
        name = "videos",
        icon_name = "media",
        order = 400,
    )


@hooks.register("register_group_permission_panel")
def register_perm_panel():
    return GroupPermissionFormSet


@hooks.register("describe_collection_contents")
def describe_collection(collection):
    count = stream_model.objects.filter(collection = collection).count()
    if count:
        url = f"{reverse('wagtailstreaming:index')}?collection_id={collection.id}"
        return {
            "count": count,
            "count_text": ngettext(
                f"{count} video stream", 
                f"{count} video streams", 
                count
            ),
            "url": url,
        }


@hooks.register("insert_global_admin_css")
def add_compare_styles():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        versioned_static("wagtailstreaming/css/compare.css"),
    )


register_admin_url_finder(stream_model, StreamAdminURLFinder)