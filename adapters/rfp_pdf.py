"""Render the controlled client projection as a local, plain-text PDF."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError


FONT_NAME = 'PSLBidPack'
FONT_FILE = Path(__file__).with_name('fonts') / 'DejaVuSans.ttf'
RENDER_LOCK = Lock()
BYTE_LIMIT = 1024 * 1024


@lru_cache(maxsize=1)
def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font = TTFont(FONT_NAME, str(FONT_FILE))
    pdfmetrics.registerFont(font)
    return font


def render(payload):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    title = payload['title']
    sections = [(section['heading'].replace('_', ' ').capitalize(), section['text'])
                for section in payload['sections']]
    output = BytesIO()
    with RENDER_LOCK:
        glyphs = _font().face.charToGlyph
        styles = {
            'title': ParagraphStyle('Title', fontName=FONT_NAME, fontSize=18, leading=22, spaceAfter=14),
            'heading': ParagraphStyle('Heading', fontName=FONT_NAME, fontSize=13, leading=17,
                                      spaceAfter=6, keepWithNext=True),
            'body': ParagraphStyle('Body', fontName=FONT_NAME, fontSize=10, leading=15),
        }

        def paragraph(text, role):
            text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\t', '    ')
            if any(char != '\n' and not glyphs.get(ord(char)) for char in text):
                raise ValidationError('The exact pack contains characters the PDF format cannot print.')
            return Paragraph(escape(text).replace('\n', '<br/>'), styles[role])

        story = [paragraph(title, 'title')]
        for name, body in sections:
            story.extend([paragraph(name, 'heading'), paragraph(body, 'body'), Spacer(1, 13)])
        document = SimpleDocTemplate(output, pagesize=A4, title=title, author='PSL',
                                     invariant=1, pageCompression=1)
        document.build(story)
    return output.getvalue()


def verify_pdf(data):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not 0 < len(data) <= BYTE_LIMIT or not data.startswith(b'%PDF-'):
        raise ValidationError('The prepared client PDF is unreadable or exceeds the file preparation limit.')
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted or not pdf.pages:
            raise ValueError
    except (PdfReadError, ValueError, KeyError, IndexError, OverflowError) as exc:
        raise ValidationError('The prepared client file could not be verified as a readable PDF.') from exc
