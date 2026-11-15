"""Bounded text extraction from case uploads."""
from io import BytesIO
from pathlib import PurePath
from zipfile import ZipFile
from xml.etree import ElementTree

from django.core.exceptions import ValidationError

TEXT_LIMIT = 16000
XML_LIMIT = 2 * 1024 * 1024


def xml_parts(data, select):
    with ZipFile(BytesIO(data)) as archive:
        parts = [part for part in archive.infolist() if select(part.filename)]
        if len(parts) > 32 or sum(part.file_size for part in parts) > XML_LIMIT:
            raise ValidationError('The document has too much embedded content.')
        for part in parts:
            payload = archive.read(part)
            if b'\x00' in payload or b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
                raise ValidationError('Unsupported document markup.')
            yield part.filename, ElementTree.fromstring(payload)


def word(data):
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    for _, root in xml_parts(data, lambda name: name == 'word/document.xml'):
        for paragraph in root.iter(ns + 'p'):
            yield ''.join(node.text or '' for node in paragraph.iter(ns + 't'))


def excel(data):
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    parts = dict(xml_parts(data, lambda name: name == 'xl/sharedStrings.xml'
                          or name.startswith('xl/worksheets/sheet') and name.endswith('.xml')))
    strings = [''.join(t.text or '' for t in entry.iter(ns + 't'))
               for entry in parts.pop('xl/sharedStrings.xml', ())]
    for name, sheet in sorted(parts.items()):
        yield PurePath(name).stem
        for row in sheet.iter(ns + 'row'):
            values = []
            for cell in row.findall(ns + 'c'):
                formula = cell.findtext(ns + 'f')
                value = cell.findtext(ns + 'v', '')
                if cell.get('t') == 's' and value:
                    value = strings[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.iter(ns + 't'))
                if formula:
                    value = f'={formula} (stored value: {value or "unavailable"})'
                if value:
                    values.append(f'{cell.get("r", "?")}: {value}')
            if values:
                yield ' | '.join(values)


def pdf(data):
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 20:
        raise ValidationError('Choose an unencrypted PDF with up to 20 pages.')
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            yield f'Page {number}\n{text}'


def extract(name, data):
    suffix = PurePath(name).suffix.lower()
    readers = {'.docx': word, '.xlsx': excel, '.pdf': pdf}
    if suffix in ('.txt', '.csv'):
        lines = [data.decode('utf-8-sig')]
    elif suffix in readers:
        lines = readers[suffix](data)
    else:
        raise ValidationError('Choose a text, CSV, Word, Excel or PDF file.')
    selected, size = [], 0
    for line in lines:
        size += len(line) + 1
        if size > TEXT_LIMIT + 1:
            raise ValidationError('The document exceeds the agent text limit.')
        selected.append(line)
    text = '\n'.join(selected)
    if not text.strip() or '\x00' in text:
        raise ValidationError('The file has no readable text. Scanned PDFs need text recognition first.')
    return text
