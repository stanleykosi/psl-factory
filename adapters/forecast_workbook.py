"""Bounded supplied references, never an Excel parser or formula evaluator."""
from copy import deepcopy
from .forecast import obj, rows, KEY, MONEY, parsed, day
from django.core.exceptions import ValidationError

PIN = obj({'id': {'type': 'integer', 'minimum': 1}, 'version': {'type': 'integer', 'minimum': 1},
           'sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}})
OPTIONAL_PIN = {'anyOf': [PIN, {'type': 'null'}]}
SELECTION = obj({'snapshot': OPTIONAL_PIN, 'contract': OPTIONAL_PIN, 'oracle': OPTIONAL_PIN, 'unit': KEY})
POLICY = obj({'contract': PIN, 'oracle': PIN, 'snapshot_max_age_days': {'type': 'integer', 'minimum': 0, 'maximum': 365}})
ROLES = ('opening', 'inflow', 'outflow', 'closing')
MONTH = {'type': 'string', 'pattern': '^[0-9]{4}-(0[1-9]|1[0-2])$'}
CELL = obj({'sheet': {'type': 'string', 'minLength': 1, 'maxLength': 80, 'pattern': r'^[^\x00-\x1f]+$'},
            'address': {'type': 'string', 'pattern': '^[A-Z]{1,3}[1-9][0-9]{0,6}$'}})
REF = obj({'month': MONTH, 'cell': CELL})
EDGE = obj({'source': REF, 'target': REF})
SCOPE = obj({'workbook': KEY, 'workbook_version': KEY, 'scenario': KEY,
             'revision': {'type': 'integer', 'minimum': 1}, 'entity': KEY,
             'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}, 'basis': {'const': 'gross_cash'},
             'unit': KEY, 'as_of': {'type': 'string'},
             'months': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'uniqueItems': True, 'items': MONTH}})
ROLE_CELLS = obj({r: CELL for r in ROLES})
MONTH_CELLS = obj({'month': MONTH, 'cells': ROLE_CELLS})
LITERALS = obj({r: MONEY for r in ROLES})
SNAPSHOT_MONTH = obj({'month': MONTH, 'cells': ROLE_CELLS, 'literals': LITERALS})
# Text is inert provenance. Neither references nor values are extracted from it.
SNAPSHOT_MONTH['properties']['formula_text'] = obj({r: {'type': 'string', 'maxLength': 2000} for r in ROLES})
SNAPSHOT = obj({'protocol': {'const': 'forecast-workbook-chain-snapshot/v1'}, 'scope': SCOPE,
                'observed_on': {'type': 'string'}, 'extracted_on': {'type': 'string'},
                'months': rows(SNAPSHOT_MONTH), 'edges': rows(EDGE)})
CONTRACT = obj({'protocol': {'const': 'forecast-workbook-reference-contract/v1'},
                'implementation': {'const': 'monthly_cash_chain_v1'}, 'scope': SCOPE,
                'months': rows(MONTH_CELLS), 'edges': rows(EDGE), 'oracle': PIN})
ORACLE = obj({'protocol': {'const': 'forecast-workbook-oracle/v1'}, 'scope': SCOPE,
              'months': rows(obj({'month': MONTH, 'literals': LITERALS}), 1)})

def parse(body, kind):
    v = parsed(body, {'snapshot': SNAPSHOT, 'contract': CONTRACT, 'oracle': ORACLE}[kind])
    day(v['scope']['as_of'])
    if kind == 'snapshot':
        observed, extracted = day(v['observed_on']), day(v['extracted_on'])
        if observed > extracted: raise ValidationError('Snapshot extraction predates its supplied observation')
    return v

def ref(month, cell):
    return {'month': month, 'cell': deepcopy(cell)}

def key(value):
    return value['month'], value['cell']['sheet'], value['cell']['address']

def graph_findings(value, *, expected=False):
    """Unsupported expected topology is not silently broadened into a new engine."""
    findings = []
    def issue(code, **details): findings.append(dict(code=code, **details))
    months = value['scope']['months']; records = value['months']
    numbers = [int(m[:4])*12+int(m[5:]) for m in months]
    if any(b != a+1 for a,b in zip(numbers,numbers[1:])):
        issue('workbook_month_mismatch', expected='ordered_contiguous_months', actual=months)
    if [m['month'] for m in records] != months:
        issue('workbook_month_mismatch', expected=months, actual=[m['month'] for m in records])
    cells = [ref(m['month'], m['cells'][r]) for m in records for r in ROLES]
    # A physical cell cannot have two roles, including across months.
    if len({(x['cell']['sheet'], x['cell']['address']) for x in cells}) != len(cells):
        issue('workbook_cell_duplicate')
    keys = {key(x) for x in cells}; targets = []
    for edge in value['edges']:
        target = key(edge['target']); targets.append(target)
        if key(edge['source']) not in keys or target not in keys:
            issue('workbook_reference_dangling', actual=edge)
    if len(set(targets)) != len(targets): issue('workbook_reference_duplicate_target')
    if expected and not findings:
        supported = [{'source': ref(a['month'], a['cells']['closing']),
                      'target': ref(b['month'], b['cells']['opening'])} for a, b in zip(records, records[1:])]
        if value['edges'] != supported:
            issue('workbook_contract_unsupported', expected=supported, actual=value['edges'])
    return findings
