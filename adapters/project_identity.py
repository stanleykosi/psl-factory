"""Reviewed manual identifier contract; no inferred native tracker API."""
import re
from django.core.exceptions import ValidationError

def normalize(value,rules):
    if not isinstance(value,str) or not value.strip() or value!=value.strip() or len(value)>rules['max_length'] or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValidationError('Identifier needs bounded nonempty source text without control or surrounding whitespace')
    if rules['format']=='ascii_token' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]*',value):raise ValidationError('Configured ASCII identifier token required')
    normalized=value if rules['case_sensitive'] else value.casefold()
    if len(normalized)>120:raise ValidationError('Normalized identifier exceeds the storage contract; use reviewed namespace criteria')
    return normalized
