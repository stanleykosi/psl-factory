"""Select an existing private PDF for an exact recorded deployment."""

from io import BytesIO

from django.core.exceptions import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from adapters import case_uploads
from apps.agents.models import CaseUpload
from apps.identity.services import require


def own_pdfs(actor, case):
    return CaseUpload.objects.filter(case=case, actor=actor, name__iendswith='.pdf',
                                     size__gt=0, size__lte=case_uploads.LIMIT)


def capture(actor, case, upload_id, *, purpose='deployment log'):
    require(actor, case, 'evidence.add')
    upload = own_pdfs(actor, case).filter(pk=upload_id).first()
    if upload is None:
        raise ValidationError(f'Choose a private PDF {purpose} you uploaded to this project.')
    try:
        data = case_uploads.read(upload)
    except OSError as exc:
        raise ValidationError(f'The private {purpose} is temporarily unavailable.') from exc
    if not data.startswith(b'%PDF-'):
        raise ValidationError(f'Choose a readable PDF {purpose}.')
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted or pdf.trailer.get('/Root') is None:
            raise ValueError
    except (PdfReadError, ValueError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        raise ValidationError(f'Choose a readable, unencrypted PDF {purpose}.') from exc
    return {'upload': upload.pk, 'sha256': upload.sha256, 'size': upload.size}


def accessible_logs(case, rows, actor):
    """Resolve current scope and pointers in one bounded metadata read; never read file bodies here."""
    return accessible_pdfs(case, actor, {row['dossier_id']: row['data__private_log'] for row in rows})


def accessible_pdfs(case, actor, pins):
    pins = {subject: pin for subject, pin in pins.items()
            if isinstance(pin, dict) and type(pin.get('upload')) is int}
    if not pins:
        return {}
    uploads = own_pdfs(actor, case).filter(pk__in={pin['upload'] for pin in pins.values()}).only(
        'case_id', 'actor_id', 'name', 'size', 'sha256').in_bulk()
    return {dossier: upload for dossier, pin in pins.items() if (upload := uploads.get(pin['upload']))
            and (upload.sha256, upload.size) == (pin.get('sha256'), pin.get('size'))}
