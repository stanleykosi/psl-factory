"""Supplied CSV interchange. Does not authenticate a billing platform or usage meter."""
import csv,io,re
from django.core.exceptions import ValidationError
from apps.finance.rules import decimal

COLUMNS=['transaction_id','customer','service','contract','period','unit','quantity']
KEY=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$')
PERIOD=re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])$')

def preview(body):
    if not isinstance(body,str) or len(body)>100000:raise ValidationError('Usage source exceeds 100,000 characters')
    reader=csv.DictReader(io.StringIO(body))
    if reader.fieldnames!=COLUMNS:raise ValidationError('Supply exact usage columns: '+', '.join(COLUMNS))
    rows=[];findings=[];seen=set()
    for line,row in enumerate(reader,2):
        if line>1001:raise ValidationError('Usage source exceeds 1,000 rows')
        if set(row)!=set(COLUMNS) or any(v is None for v in row.values()):raise ValidationError('Malformed usage CSV row')
        row=dict(row,line=line)
        for k in COLUMNS[:-1]:
            pattern=PERIOD if k=='period' else KEY
            if not pattern.fullmatch(row[k]):findings.append(f'Line {line}: invalid {k}')
        identity=row['transaction_id']
        if identity in seen:findings.append(f'Line {line}: duplicate transaction identity')
        seen.add(identity)
        if row['quantity']=='':row['quantity']=None
        else:
            try:decimal(row['quantity'],nonnegative=True)
            except ValidationError:findings.append(f'Line {line}: invalid quantity');row['quantity']=None
        rows.append(row)
    if not rows:raise ValidationError('Usage source has no rows')
    return rows,findings
