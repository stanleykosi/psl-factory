from io import BytesIO
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from adapters.upload_text import extract


def document(path, body):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr(path, body)
    return stream.getvalue()


class UploadTextTests(SimpleTestCase):
    def test_word_text(self):
        data = document('word/document.xml', '''
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:p><w:r><w:t>Approval pending</w:t></w:r></w:p>
            </w:document>''')
        self.assertEqual(extract('example.docx', data), 'Approval pending')

    def test_excel_preserves_formula_and_cached_value(self):
        data = document('xl/worksheets/sheet1.xml', '''
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <row><c r="A1"><f>40+2</f><v>42</v></c></row>
            </worksheet>''')
        self.assertIn('A1: =40+2 (stored value: 42)', extract('example.xlsx', data))

    def test_rejects_oversized_text_and_document_entities(self):
        with self.assertRaises(ValidationError):
            extract('example.txt', b'x' * 16001)
        with self.assertRaises(ValidationError):
            extract('example.docx', document('word/document.xml', '<!DOCTYPE a><a/>'))
