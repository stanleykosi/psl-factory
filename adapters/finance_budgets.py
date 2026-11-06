"""A bounded supplied-file adapter, not an authenticated budget/ERP connection."""
import csv
import io
import re
from django.core.exceptions import ValidationError
from apps.finance.rules import decimal

COLUMNS=['entity','period','scope','bu','metric','amount','currency','unit']
KEY=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}')


def read_budget(text,cadence):
    if cadence not in ['monthly','annual'] or len(text)>100000:raise ValidationError('Select monthly/annual supplied budget within the file budget')
    reader=csv.DictReader(io.StringIO(text))
    if reader.fieldnames!=COLUMNS:raise ValidationError('Expected budget CSV columns: '+','.join(COLUMNS))
    rows=[];findings=[];seen=set()
    for line,row in enumerate(reader,2):
        if line>1001 or None in row or any(v is None for v in row.values()):raise ValidationError('Malformed budget row or row budget exceeded')
        r={k:v.strip() for k,v in row.items()};r['line']=line
        errors=[]
        for key in ['entity','metric']:
            if not KEY.fullmatch(r[key]):errors.append('Invalid '+key)
        if not (re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])',r['period']) if cadence=='monthly' else KEY.fullmatch(r['period'])):errors.append('Invalid explicit period/year key')
        if r['scope'] not in ['company','bu'] or (r['scope']=='company' and r['bu']) or (r['scope']=='bu' and not KEY.fullmatch(r['bu'])):errors.append('Scope/BU dimensions disagree')
        if not re.fullmatch('[A-Z]{3}',r['currency']):errors.append('Invalid currency')
        if r['unit'] not in ['major_currency','thousands_currency','millions_currency']:errors.append('Unknown presentation unit')
        try:decimal(r['amount'])
        except ValidationError:r['amount']=None;errors.append('Unknown/invalid budget amount; not zero')
        dimension=tuple(r[k] for k in ['entity','period','scope','bu','metric'])
        if dimension in seen:errors.append('Duplicate budget dimension')
        seen.add(dimension);rows.append(r);findings.extend(f'{line}: {error}' for error in errors)
    if not rows:raise ValidationError('Budget has no rows')
    return rows,findings
