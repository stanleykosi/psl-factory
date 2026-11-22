"""Check human channel evidence against the reserved reminder."""
import json
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
from pathlib import PurePath

from django.core.exceptions import ValidationError

from adapters import case_uploads

ATTACHMENT_LIMIT = 1024 * 1024
MAIL_FROM = 'reminders@psl.invalid'


def invoice_pdf(upload):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not 0 < upload.size <= ATTACHMENT_LIMIT or PurePath(upload.name).suffix.lower() != '.pdf':
        raise ValidationError('Choose a private PDF up to 1 MiB.')
    data = case_uploads.read(upload)
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 50:
            raise ValidationError('Choose a readable PDF of up to 50 pages.')
    except (PdfReadError, ValueError, OverflowError) as exc:
        raise ValidationError('Choose a readable invoice PDF.') from exc
    return data


def encode_message(row):
    draft = row.draft
    if not draft.contact.email.lower().endswith('.invalid'):
        raise ValidationError('The test mailbox accepts reserved test addresses only.')
    message = EmailMessage(policy=policy.SMTP)
    message['From'] = MAIL_FROM
    message['To'] = draft.contact.email
    message['Subject'] = draft.subject
    message['Message-ID'] = message_id(row)
    message.set_content(draft.body)
    if draft.attachment_id:
        message.add_attachment(invoice_pdf(draft.attachment), maintype='application', subtype='pdf',
                               filename=f'invoice-{draft.issue_id}.pdf')
    return message.as_bytes()


def message_id(row):
    return f'<{row.operation_key}@psl.invalid>'


def verify_message(row, content, fingerprint):
    if sha256(content).hexdigest() != fingerprint:
        raise ValidationError('The mailbox message fingerprint did not match.')
    message = BytesParser(policy=policy.default).parsebytes(content)
    draft = row.draft
    attachments = list(message.iter_attachments())
    actual = [sha256(part.get_payload(decode=True)).hexdigest() for part in attachments
              if part.get_content_type() == 'application/pdf']
    pinned = [draft.attachment.sha256] if draft.attachment_id else []
    body = message.get_body(preferencelist=('plain',))
    clean = lambda value: value.replace('\r\n', '\n').rstrip('\n')
    if (str(message['From']) != MAIL_FROM or str(message['To']) != draft.contact.email or
            str(message['Subject']) != draft.subject or str(message['Message-ID']) != message_id(row) or
            body is None or clean(body.get_content()) != clean(draft.body) or
            len(attachments) != len(pinned) or actual != pinned):
        raise ValidationError('The mailbox message did not match the approved draft and attachment.')


def check_evidence(body, operation, digest, recipient, reference, delivered):
    if not isinstance(body, str) or len(body.encode()) > 8000:
        raise ValidationError('Use bounded channel receipt evidence.')
    try:
        supplied = json.loads(body)
    except ValueError:
        raise ValidationError('Use the typed reminder receipt evidence.') from None
    expected = {'operation': str(operation), 'draft_sha256': digest, 'recipient': recipient,
                'reference': reference, 'delivered': delivered}
    if (not isinstance(supplied, dict) or supplied.keys() != expected.keys() or
            type(supplied['delivered']) is not bool or supplied != expected):
        raise ValidationError('Receipt evidence does not identify this exact version, recipient and outcome.')
