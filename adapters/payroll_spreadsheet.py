"""Read an explicitly mapped payroll table without retaining the supplied file."""
import csv
from io import StringIO
from pathlib import PurePosixPath
import re
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from adapters.upload_text import xml_parts
from django.core.exceptions import ValidationError

FIELDS = ('row_ref', 'employee_id', 'component', 'amount')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def csv_rows(content, delimiter):
    yield from csv.reader(StringIO(content.decode('utf-8-sig'), newline=''), delimiter=delimiter, strict=True)


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
