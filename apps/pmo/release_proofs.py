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


def capture(actor, case, upload_id):
    require(actor, case, 'evidence.add')
    upload = own_pdfs(actor, case).filter(pk=upload_id).first()
    if upload is None:
        raise ValidationError('Choose a private PDF deployment log you uploaded to this project.')
    try:
        data = case_uploads.read(upload)
    except OSError as exc:
        raise ValidationError('The private deployment log is temporarily unavailable.') from exc
    if not data.startswith(b'%PDF-'):
        raise ValidationError('Choose a readable PDF deployment log.')
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted or pdf.trailer.get('/Root') is None:
            raise ValueError
    except (PdfReadError, ValueError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        raise ValidationError('Choose a readable, unencrypted PDF deployment log.') from exc
    return {'upload': upload.pk, 'sha256': upload.sha256, 'size': upload.size}


def accessible_logs(case, rows, actor):
    """Resolve current scope and pointers in one bounded metadata read; never read file bodies here."""
    pins = {row['dossier_id']: row['data__private_log'] for row in rows
            if isinstance(row['data__private_log'], dict) and type(row['data__private_log'].get('upload')) is int}
    if not pins:
        return {}
    uploads = own_pdfs(actor, case).filter(pk__in={pin['upload'] for pin in pins.values()}).in_bulk()
    return {dossier: upload for dossier, pin in pins.items() if (upload := uploads.get(pin['upload']))
            and (upload.sha256, upload.size) == (pin.get('sha256'), pin.get('size'))}
