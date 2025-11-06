from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import magic


class VideoFileValidator(FileExtensionValidator):
    def __call__(self, value):
        super().__call__(value)
        mime = magic.Magic(mime = True).from_buffer(value.read(2048))
        value.seek(0)

        if not mime.startswith("video/"):
            raise ValidationError(f"Unsupported file type: {mime}. Only video are allowed.")


class PhotoFileValidator(FileExtensionValidator):
    def __call__(self, value):
        super().__call__(value)
        mime = magic.Magic(mime = True).from_buffer(value.read(2048))
        value.seek(0)

        if not mime.startswith("image/"):
            raise ValidationError(f"Unsupported file type: {mime}. Only photos are allowed.")