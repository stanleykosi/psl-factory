"""Private input images scoped to the uploader and the selected conversation."""
import base64

from django.core.exceptions import ValidationError
from django.urls import reverse

from adapters import case_uploads
from apps.identity.services import require

from .models import CaseUpload


MAX_IMAGES = 3
IMAGE_SOURCE = 'assistant_image'


def selected(conversation, ids):
    if not ids:
        return []
    if (not isinstance(ids, list) or len(ids) > MAX_IMAGES or
            any(type(item) is not int or item <= 0 for item in ids) or len(set(ids)) != len(ids)):
        raise ValidationError('Choose up to three distinct uploaded images.')
    require(conversation.actor, conversation.case, 'evidence.add')
    uploads = CaseUpload.objects.filter(case_id=conversation.case_id, actor_id=conversation.actor_id).in_bulk(ids)
    if set(uploads) != set(ids):
        raise ValidationError('Choose images you uploaded in this workspace.')
    return [uploads[pk] for pk in ids]


def source(upload):
    return {'label': f'Attached image · {upload.name}',
            'fact': 'Image supplied by the person asking this question. Treat its contents as unverified evidence.',
            'url': reverse('case_upload_download', args=[upload.case_id, upload.pk]),
            'record': {'field': IMAGE_SOURCE, 'pk': upload.pk}, 'sha256': upload.sha256}


def image_data(upload):
    data = case_uploads.read(upload)
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif data.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValidationError('Attach a PNG, JPEG or WebP image.')
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')
