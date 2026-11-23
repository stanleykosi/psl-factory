"""Read an explicitly mapped payroll table without retaining the supplied file."""
import csv
from io import BytesIO, StringIO
from pathlib import PurePosixPath
import re
from xml.etree.ElementTree import Element, ParseError, SubElement, tostring
from zipfile import BadZipFile, ZipFile

from adapters.upload_text import xml_parts
from django.core.exceptions import ValidationError

FIELDS = ('row_ref', 'employee_id', 'component', 'amount')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def csv_rows(content, delimiter):
    yield from csv.reader(StringIO(content.decode('utf-8-sig'), newline=''), delimiter=delimiter, strict=True)


def blank_template(layout):
    headers = list(layout['columns'].values())
    if layout['format'] == 'csv':
        if any(header.lstrip().startswith(('=', '+', '-', '@')) for header in headers):
            raise ValidationError('The payroll source owner needs to correct a spreadsheet heading.')
        out = StringIO(newline='')
        csv.writer(out, delimiter=layout['delimiter']).writerow(headers)
        return out.getvalue().encode('utf-8-sig')

    main = NS[1:-1]
    office = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package = 'http://schemas.openxmlformats.org/package/2006/relationships'
    types = 'http://schemas.openxmlformats.org/package/2006/content-types'
    workbook = Element('workbook', {'xmlns': main, 'xmlns:r': office})
    SubElement(SubElement(workbook, 'sheets'), 'sheet', {'name': layout['sheet'], 'sheetId': '1', 'r:id': 'rId1'})
    sheet = Element('worksheet', {'xmlns': main})
    row = SubElement(SubElement(sheet, 'sheetData'), 'row', {'r': '1'})
    for column, name in enumerate(headers):
        cell = SubElement(row, 'c', {'r': f'{chr(65 + column)}1', 't': 'inlineStr'})
        SubElement(SubElement(cell, 'is'), 't').text = name
    content = Element('Types', {'xmlns': types})
    SubElement(content, 'Default', {'Extension': 'rels',
                                     'ContentType': 'application/vnd.openxmlformats-package.relationships+xml'})
    SubElement(content, 'Default', {'Extension': 'xml', 'ContentType': 'application/xml'})
    SubElement(content, 'Override', {'PartName': '/xl/workbook.xml',
        'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'})
    SubElement(content, 'Override', {'PartName': '/xl/worksheets/sheet1.xml',
        'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
    root_links = Element('Relationships', {'xmlns': package})
    SubElement(root_links, 'Relationship', {'Id': 'rId1', 'Type': office + '/officeDocument', 'Target': 'xl/workbook.xml'})
    book_links = Element('Relationships', {'xmlns': package})
    SubElement(book_links, 'Relationship', {'Id': 'rId1', 'Type': office + '/worksheet', 'Target': 'worksheets/sheet1.xml'})
    out = BytesIO()
    with ZipFile(out, 'w') as archive:
        for name, part in [('[Content_Types].xml', content), ('_rels/.rels', root_links), ('xl/workbook.xml', workbook),
                           ('xl/_rels/workbook.xml.rels', book_links), ('xl/worksheets/sheet1.xml', sheet)]:
            archive.writestr(name, tostring(part, encoding='utf-8', xml_declaration=True))
    return out.getvalue()


def excel_rows(content, name, width=4):
    index = dict(xml_parts(content, lambda path: path in ('xl/workbook.xml', 'xl/_rels/workbook.xml.rels')))
    workbook = index['xl/workbook.xml']
    links = index['xl/_rels/workbook.xml.rels']
    id_ = next((sheet.get(REL) for sheet in workbook.iter(NS + 'sheet') if sheet.get('name') == name), None)
    relation = next((link for link in links if id_ and link.get('Id') == id_), None)
    if relation is None:
        raise ValueError
    target = relation.get('Target', '')
    path = PurePosixPath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
    if relation.get('TargetMode') == 'External' or not re.fullmatch(r'xl/worksheets/[\w.-]+\.xml', str(path), re.ASCII):
        raise ValueError
    parts = dict(xml_parts(content, lambda path_: path_ in (str(path), 'xl/sharedStrings.xml')))
    strings = [''.join(node.text or '' for node in item.iter(NS + 't'))
               for item in parts.get('xl/sharedStrings.xml', ())]
    for row in parts[str(path)].iter(NS + 'row'):
        values = ['']*width
        seen = set()
        for cell in row.findall(NS + 'c'):
            match = re.fullmatch(r'([A-'+('E' if width==5 else 'D')+r'])([1-9][0-9]*)', cell.get('r', ''))
            kind = cell.get('t', 'n')
            if not match or match[2] != row.get('r') or match[1] in seen or kind not in ('n', 's', 'inlineStr', 'str'):
                raise ValueError
            if cell.find(NS + 'f') is not None:
                raise ValueError
            seen.add(match[1])
            value = cell.findtext(NS + 'v', '')
            if kind == 's':
                if not value.isascii() or not value.isdigit():
                    raise ValueError
                value = strings[int(value)]
            elif kind == 'inlineStr':
                value = ''.join(node.text or '' for node in cell.iter(NS + 't'))
            values[ord(match[1]) - ord('A')] = value
        yield values


def rows(content, layout):
    """Return only explicitly mapped authorized fields; reject extras/formulas."""
    from adapters.payroll import PayrollExportError

    expected = layout['columns']
    if set(expected) not in [set(FIELDS),set(FIELDS)|{'currency'}]:
        raise PayrollExportError('spreadsheet_columns')
    if not isinstance(content, bytes) or len(content) > 256000:
        raise PayrollExportError('spreadsheet_budget')
    stream = csv_rows(content, layout['delimiter']) if layout['format'] == 'csv' else excel_rows(content, layout['sheet'],len(expected))
    try:
        header = next(stream)
        if len(header) != len(expected) or set(header) != set(expected.values()):
            raise PayrollExportError('spreadsheet_columns')
        positions = {field: header.index(expected[field]) for field in expected}
        result = []
        for number, row in enumerate(stream):
            if number >= 500 or len(row) != len(expected):
                raise PayrollExportError('spreadsheet_inventory')
            record = {field: row[position] for field, position in positions.items()}
            if record['amount'] == '':
                record['amount'] = None
            result.append(record)
        return result
    except PayrollExportError:
        raise
    except (BadZipFile, csv.Error, IndexError, KeyError, ParseError, StopIteration, ValueError, ValidationError):
        raise PayrollExportError('spreadsheet_format') from None
