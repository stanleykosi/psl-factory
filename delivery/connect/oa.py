#!/usr/bin/env python3
"""Condensed view of an OpenAPI operation.

Used to build the connection map (README.md); run from anywhere in the repo.

usage:
  oa.py live|v7 list [regex]            list operations whose path matches regex
  oa.py live|v7 METHOD /api/v1/path     show params, request body and 2xx/4xx responses (depth 4)
  oa.py live|v7 METHOD /api/v1/path 6   same, deeper
"""
import json, re, sys

import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
SPECS = {
    'live': ROOT / 'contracts/psl-factory.openapi.json',
    'v7': ROOT / 'architecture/packages/v7/openapi.json',
}
spec = json.load(open(SPECS[sys.argv[1]]))


def deref(s):
    for _ in range(12):
        if isinstance(s, dict) and '$ref' in s:
            t = spec
            for x in s['$ref'].split('/')[1:]:
                t = t[x]
            s = t
        else:
            break
    return s


def show(s, depth, maxd, name, out):
    s = deref(s)
    if not isinstance(s, dict):
        return
    pad = '  ' * depth
    t = s.get('type')
    if isinstance(t, list):
        t = '|'.join(t)
    kind = t or next((u for u in ('oneOf', 'anyOf', 'allOf') if u in s), 'any')
    bits = []
    if 'enum' in s:
        bits.append('enum=' + json.dumps(s['enum'])[:200])
    if 'format' in s:
        bits.append(s['format'])
    req = s.get('required')
    out.append(f"{pad}{name}: {kind} {' '.join(bits)}".rstrip() + (f"  required={req}" if req and depth < maxd else ''))
    if depth >= maxd:
        return
    for k, v in (s.get('properties') or {}).items():
        show(v, depth + 1, maxd, k, out)
    if 'items' in s:
        show(s['items'], depth + 1, maxd, '[]', out)
    for u in ('oneOf', 'anyOf', 'allOf'):
        for i, x in enumerate(s.get(u, [])):
            x = deref(x)
            if isinstance(x, dict) and x.get('type') == 'null':
                out.append(f"{pad}  {u}{i}: null")
                continue
            show(x, depth + 1, maxd, f'{u}{i}', out)


if sys.argv[2] == 'list':
    rx = re.compile(sys.argv[3] if len(sys.argv) > 3 else '.')
    for p, m in spec['paths'].items():
        if rx.search(p):
            for k, op in m.items():
                if k in ('get', 'post', 'put', 'patch', 'delete'):
                    print(k.upper().ljust(7), p, '  #', op.get('operationId', ''), '-', (op.get('summary') or '')[:80])
    sys.exit()

method, path = sys.argv[2].lower(), sys.argv[3]
maxd = int(sys.argv[4]) if len(sys.argv) > 4 else 4
item = spec['paths'].get(path)
if not item or method not in item:
    print('NOT IN', sys.argv[1], method.upper(), path)
    sys.exit(1)
op = item[method]
out = [f"{method.upper()} {path}  operationId={op.get('operationId')}", f"summary: {op.get('summary', '')}"]
if op.get('description'):
    out.append('description: ' + op['description'][:1200])
for prm in item.get('parameters', []) + op.get('parameters', []):
    prm = deref(prm)
    sch = deref(prm.get('schema', {}))
    out.append(f"param {prm['in']} {prm['name']} required={prm.get('required', False)} {sch.get('type', '')} {json.dumps(sch.get('enum')) if sch.get('enum') else ''}")
rb = op.get('requestBody')
if rb:
    rb = deref(rb)
    for ct, v in rb.get('content', {}).items():
        out.append(f'request {ct}:')
        show(v.get('schema', {}), 1, maxd, 'body', out)
for code, r in op.get('responses', {}).items():
    r = deref(r)
    out.append(f"response {code}: {r.get('description', '')[:120]}")
    if code.startswith('2') or code in ('409', '422', '400'):
        for ct, v in (r.get('content') or {}).items():
            show(v.get('schema', {}), 1, maxd, ct, out)
print('\n'.join(out))
