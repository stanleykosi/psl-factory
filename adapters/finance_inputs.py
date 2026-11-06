import csv
import io
import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

COLUMNS = ['account', 'amount', 'currency', 'period']


def preview_csv(text):
    """Engineering interchange v1, not an assumed QuickBooks export contract."""
    if len(text) > 100000:
        raise ValidationError('Import budget exceeded (100,000 characters)')
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != COLUMNS:
        raise ValidationError('Expected CSV columns: account,amount,currency,period')
    rows, findings = [], []
    for number, row in enumerate(reader, start=2):
        if number > 1001 or None in row or any(value is None for value in row.values()):
            raise ValidationError('Malformed row or import row budget exceeded')
        record = {key: value.strip() for key, value in row.items()}
        record['line'] = number
        if not record['account']:
            findings.append({'line': number, 'field': 'account', 'message': 'Account is missing'})
        if record['amount'] == '':
            record['amount'] = None
            findings.append({'line': number, 'field': 'amount', 'message': 'Unknown amount; not zero'})
        else:
            try:
                amount = Decimal(record['amount'])
                if not amount.is_finite() or abs(amount) >= Decimal('1e18') or amount.as_tuple().exponent < -8:
                    raise InvalidOperation
                record['amount'] = str(amount)
            except InvalidOperation:
                findings.append({'line': number, 'field': 'amount', 'message': 'Invalid exact decimal amount'})
        if not re.fullmatch('[A-Z]{3}', record['currency']):
            findings.append({'line': number, 'field': 'currency', 'message': 'Explicit three-letter currency required'})
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', record['period']):
            findings.append({'line': number, 'field': 'period', 'message': 'Expected YYYY-MM period'})
        rows.append(record)
    if not rows:
        raise ValidationError('Import has no rows')
    return rows, findings
