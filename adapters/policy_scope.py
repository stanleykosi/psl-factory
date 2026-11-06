"""Closed JSON-value binding protocol; no code, authority or external effects."""
import copy
import json
from django.core.exceptions import ValidationError


def leaf(value, path):
    if not isinstance(path, str) or not path.startswith('/') or len(path) > 300:
        raise ValidationError('Bindings need bounded JSON pointers to existing scalar leaves')
    parts = path[1:].split('/')
    import re
    if any(re.search(r'~(?![01])', part) for part in parts):
        raise ValidationError('JSON pointer escape must be canonical')
    current = value
    try:
        for part in parts[:-1]:
            key = part.replace('~1', '/').replace('~0', '~')
            if isinstance(current, list) and (not key.isdecimal() or str(int(key)) != key):
                raise ValidationError('Array indices must be canonical nonnegative integers')
            current = current[int(key)] if isinstance(current, list) and key.isdecimal() else current[key]
        key = parts[-1].replace('~1', '/').replace('~0', '~')
        if isinstance(current, list) and (not key.isdecimal() or str(int(key)) != key):
            raise ValidationError('Array indices must be canonical nonnegative integers')
        key = int(key) if isinstance(current, list) and key.isdecimal() else key
        result = current[key]
    except (IndexError, KeyError, TypeError, ValueError):
        raise ValidationError('Binding pointer must identify an existing leaf')
    if isinstance(result, (dict, list)):
        raise ValidationError('Binding entire objects or arrays is unavailable; select scalar leaves')
    return current, key, result


def bind(values, paths, bindings, cross_case=False):
    if not isinstance(paths, list) or len(paths) > 100 or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        raise ValidationError('At most 100 distinct authorized binding pointers')
    for path in paths:
        leaf(values, path)
    if not isinstance(bindings, list) or len(bindings) > 100:
        raise ValidationError('Bindings must be a bounded list')
    result = copy.deepcopy(values)
    seen = set()
    for item in bindings:
        if not isinstance(item, dict) or set(item) != {'path', 'value'} or item['path'] not in paths or item['path'] in seen:
            raise ValidationError('Only distinct source-authorized binding paths may change')
        seen.add(item['path'])
        parent, key, original = leaf(result, item['path'])
        value = item['value']
        if isinstance(value, (dict, list)) or (original is not None and type(value) is not type(original)):
            raise ValidationError('Binding must preserve the declared scalar type')
        parent[key] = value
    if cross_case and seen != set(paths):
        raise ValidationError('Cross-case application must explicitly bind every contextual path')
    try:
        encoded = json.dumps(result, allow_nan=False)
    except (ValueError, TypeError):
        raise ValidationError('Bindings require finite JSON values')
    if len(encoded) > 100000:
        raise ValidationError('Bound value budget exceeded')
    return result
