"""Typed A01 results; source content cannot grant a tool or decision."""
import json,re
from datetime import date
from django.core.exceptions import ValidationError
from adapters.change_intake import FIELDS

LIMITS={'reference':160,'requestor':160,'date_raised':10,'module':160,'description':4000,'reason':4000}

def validate_result(source,result):
    if not isinstance(result,dict) or set(result)!={'fields','category','questions'}:
        raise ValidationError('Closed P56 extraction output required')
    if not isinstance(result['fields'],dict) or set(result['fields'])!=set(FIELDS):
        raise ValidationError('Exact P56 request fields required')
    for name,row in result['fields'].items():
        if not isinstance(row,dict) or set(row)!={'value','quote'}:raise ValidationError('Typed field and source quote required')
        value,quote=row['value'],row['quote']
        if value is None:
            if quote is not None:raise ValidationError('Unknown values cannot claim source support')
            continue
        if not isinstance(value,str) or not value.strip() or len(value)>LIMITS[name]:raise ValidationError('Invalid extracted '+name)
        if not isinstance(quote,str) or not quote or len(quote)>4500 or quote not in source.body or value not in quote:
            raise ValidationError('Every extracted value requires an exact supporting source quote')
        if name=='date_raised':
            try:
                if date.fromisoformat(value).isoformat()!=value:raise ValueError()
            except ValueError:
                row.update(value=None,quote=None)
                result['questions'].append('Supply an unambiguous date raised in YYYY-MM-DD format')
    row=result['category']
    if not isinstance(row,dict) or set(row)!={'suggestion','quote'}:raise ValidationError('Typed category suggestion required')
    if row['suggestion'] is None:
        if row['quote'] is not None:raise ValidationError('Unknown category cannot claim source support')
    elif row['suggestion'] not in ['Standard','Normal','Emergency'] or not isinstance(row['quote'],str) or not row['quote'] or len(row['quote'])>4500 or row['quote'] not in source.body or not re.search(r'\b'+re.escape(row['suggestion'])+r'\b',row['quote'],re.I):
        raise ValidationError('Exact category vocabulary and source basis required')
    if not isinstance(result['questions'],list) or len(result['questions'])>16 or any(not isinstance(q,str) or not q.strip() or len(q)>500 for q in result['questions']):
        raise ValidationError('Bounded clarification questions required')
    if len(json.dumps(result,allow_nan=False))>24000:raise ValidationError('P56 extraction output budget exceeded')
    return result
