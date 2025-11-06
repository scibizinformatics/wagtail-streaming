import os
import mimetypes

from django.core.files import File

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from wagtail.models import Collection

from ...models import get_stream_model


class Command(BaseCommand):
    help = "Create VideoStream instances from a directory of video files."

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            type = str,
            help = "Absolute path to the directory containing video files."
        )
        parser.add_argument(
            "--user",
            type = str,
            default = None,
            help = "Username or email of the user who will be set as 'uploaded_by'."
        )
        parser.add_argument(
            "--collection",
            type = str,
            default = None,
            help = "Optional name of the collection to assign to these videos."
        )

    def handle(self, *args, **options):
        directory = options["directory"]
        user_identifier = options["user"]
        collection_name = options["collection"]

        if not os.path.isdir(directory):
            raise CommandError(f"Directory does not exist: {directory}")

        user = None
        if user_identifier:
            User = get_user_model()
            try:
                user = User.objects.filter(username = user_identifier).first() or User.objects.filter(email = user_identifier).first()
                if not user:
                    self.stdout.write(self.style.WARNING(f"User '{user_identifier}' not found. Skipping 'uploaded_by'."))

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error finding user: {e}"))

        collection = Collection.get_first_root_node()
        if collection_name:
            collection, _ = Collection.objects.get_or_create(name = collection_name)

        stream_model = get_stream_model()

        created_count = 0
        skipped_count = 0

        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if not os.path.isfile(file_path):
                continue

            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type or not mime_type.startswith("video/"):
                skipped_count += 1
                continue

            title = os.path.splitext(filename)[0]
            if stream_model.objects.filter(title = title).exists():
                self.stdout.write(self.style.WARNING(f"Skipped duplicate: {title}"))
                skipped_count += 1
                continue

            with open(file_path, "rb") as f:
                django_file = File(f)
                video = stream_model.objects.create(
                    title = title,
                    file = django_file,
                    uploaded_by = user,
                    collection = collection,
                )

            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"Created stream: {video.title}"))

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_count} videos, skipped {skipped_count}."
        ))
