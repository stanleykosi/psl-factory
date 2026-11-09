"""Exact supplied workbook comparison. No native workbook/authenticity claim."""
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import Evidence
from adapters.forecast import day
from adapters.forecast_workbook import parse, graph_findings, ROLES, key
from .rules import decimal

KINDS = {'snapshot': 'forecast_workbook_snapshot', 'contract': 'forecast_workbook_contract', 'oracle': 'forecast_workbook_oracle'}

def source_ids(scenario):
    selected = scenario.payload.get('workbook_chain', {})
    return {p['id'] for kind in KINDS if (p := selected.get(kind)) is not None}

def read(case, pin, kind):
    if pin is None: raise ValidationError('workbook_'+kind+'_missing')
    e = Evidence.objects.filter(case=case, pk=pin['id'], kind=KINDS[kind], version=pin['version'], sha256=pin['sha256']).first()
    if e is None: raise ValidationError('workbook_'+kind+'_unavailable')
    return e, parse(e.body, kind)

def equal(a, b):
    return a is None and b is None or a is not None and b is not None and decimal(a) == decimal(b)

def validate_contract(case, policy):
    _, contract = read(case, policy['contract'], 'contract')
    _, oracle = read(case, policy['oracle'], 'oracle')
    if contract['oracle'] != policy['oracle'] or contract['scope'] != oracle['scope']:
        raise ValidationError('Workbook contract and exact oracle scope/pin differ')
    if graph_findings(contract, expected=True): raise ValidationError('Unsupported or incomplete supplied workbook reference contract')
    if [m['month'] for m in oracle['months']] != contract['scope']['months']:
        raise ValidationError('Workbook oracle requires exact complete ordered months')
    from apps.policy.forecast_validators import chain
    previous = None
    for index, month in enumerate(oracle['months']):
        values = month['literals']
        if not equal(chain(values['opening'], values['inflow'], values['outflow']), values['closing']):
            raise ValidationError('Workbook oracle differs from supported monthly chain')
        if index and not equal(previous, values['opening']): raise ValidationError('Workbook oracle carry differs from exact previous closing')
        previous = values['closing']
    return contract, oracle

def compare(scenario, method, periods):
    selected = scenario.payload['workbook_chain']; findings = []; sources = {}; data = {}
    def issue(code, **details): findings.append(dict(code=code, **details))
    for kind in KINDS:
        try:
            e, value = read(scenario.case, selected[kind], kind)
            sources[kind] = {'id': e.pk, 'version': e.version, 'sha256': e.sha256}
            data[kind] = value
        except ValidationError:
            # Do not disclose bytes/scope from unavailable or foreign evidence.
            issue('workbook_'+kind+('_missing' if selected[kind] is None else '_unavailable'))
    policy = method.get('workbook_reference') if method else None
    if policy is None: issue('workbook_contract_missing')
    elif any(policy[k] != selected[k] for k in ['contract', 'oracle']): issue('workbook_policy_pin_mismatch')
    if len(data) == 3:
        snapshot, contract, oracle = (data[k] for k in KINDS)
        expected_scope = contract['scope']; scope = snapshot['scope']; v = scenario.payload
        if (scope != expected_scope or oracle['scope'] != expected_scope or
            any(scope[k] != v[k] for k in ['entity', 'currency', 'basis', 'as_of', 'months']) or
            scope['scenario'] != scenario.reference or scope['revision'] != scenario.number or scope['unit'] != selected['unit']):
            issue('workbook_scope_mismatch')
        if contract['oracle'] != selected['oracle']: issue('workbook_oracle_pin_mismatch')
        findings.extend(graph_findings(snapshot)); findings.extend(graph_findings(contract, expected=True))
        if [m['month'] for m in oracle['months']] != v['months']: issue('workbook_oracle_month_mismatch')
        if day(snapshot['observed_on']) > day(v['as_of']) or day(snapshot['extracted_on']) > timezone.localdate(): issue('workbook_source_date_mismatch')
        if policy and (day(v['as_of']) - day(snapshot['observed_on'])).days > policy['snapshot_max_age_days']:
            issue('workbook_source_stale')
        if [{k: m[k] for k in ['month', 'cells']} for m in snapshot['months']] != contract['months']:
            issue('workbook_cell_roles_mismatch', expected=contract['months'], actual=[{k: m[k] for k in ['month', 'cells']} for m in snapshot['months']])
        actual_edges = {key(e['target']): e for e in snapshot['edges']}
        for edge in contract['edges']:
            actual = actual_edges.get(key(edge['target']))
            if actual != edge: issue('workbook_reference_missing' if actual is None else 'workbook_reference_mismatch', month=edge['target']['month'], role='opening', expected=edge, actual=actual)
        if len(snapshot['edges']) != len(contract['edges']): issue('workbook_reference_count_mismatch')
        # Numeric coincidence must never excuse a wrong graph.
        if not findings:
            from apps.policy.forecast_validators import chain
            previous = None
            for index, (supplied, golden, native) in enumerate(zip(snapshot['months'], oracle['months'], periods)):
                literals = supplied['literals']; expected = golden['literals']
                for role in ROLES:
                    if not equal(literals[role], expected[role]) or not equal(literals[role], native[role]):
                        issue('workbook_oracle_mismatch', month=supplied['month'], role=role)
                if not equal(chain(literals['opening'], literals['inflow'], literals['outflow']), literals['closing']) or index and not equal(previous, literals['opening']):
                    issue('workbook_oracle_mismatch', month=supplied['month'], role='closing')
                previous = literals['closing']
    return {'protocol': 'forecast-workbook-comparison/v1', 'status': 'held' if findings else 'equivalent',
            'verification': 'supplied_snapshot_only_not_native_workbook_authenticated',
            'selection': selected, 'sources': sources, 'findings': findings}

def apply(scenario, method, manifest, result):
    if 'workbook_chain' not in scenario.payload: return
    comparison = compare(scenario, method, result['periods'])
    manifest['workbook_comparison'] = comparison
    result['workbook_comparison'] = comparison
    if comparison['status'] == 'held':
        result['status'] = 'held'
        result['findings'].append('Supplied workbook comparison held; exact reference or oracle evidence requires correction')
        # Preserve separately verified initial opening and flow inputs, not generated balances.
        for index, period in enumerate(result['periods']):
            period['closing'] = None
            if index: period['opening'] = None
