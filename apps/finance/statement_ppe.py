"""Native PPE source selection and immutable inventory for selected statement lines."""
from django.core.exceptions import ValidationError
from django.db import connection
from apps.identity.services import active_case_grants
from apps.policy.statement_ppe import validate_binding
from . import ppe


def source_input(actor,case,row,value):
    ppe.readable(actor,case)
    work=validate_binding(row,case,value)
    ppe.current(work)
    decision=ppe.approved(work,'schedule')
    if decision.pk!=row['schedule_review_id'] or work.result['status']!='ready':
        raise ValidationError('Current exact reviewed ready PPE schedule required')
    register=ppe.exact(case,row['register_id'],'ppe_register')
    rr=ppe.approved(register,'register')
    basis=ppe.approved(register,'basis') if register.result['date_basis_ambiguous'] else None
    amount=work.result['totals'][row['metric']]
    if amount is None:raise ValidationError('Unknown PPE total cannot be a reviewed statement input')
    evidence={work.evidence_id,decision.evidence_id,rr.evidence_id,row['mapping_evidence_id'],register.payload['opening_evidence_id']}
    evidence.update(x['classification_evidence_id'] for x in register.payload['assets'])
    evidence.update(x['evidence_id'] for x in register.payload['events'])
    if basis:evidence.add(basis.evidence_id)
    return {'declaration':row,'operation_key':work.operation_key,'result_hash':ppe.digest(work.result),
        'schedule_sha256':work.sha256,'register_sha256':register.sha256,
        'review':{'id':decision.pk,'authority':decision.authority},
        'register_review':rr.pk,'basis_review':basis.pk if basis else None,
        'source_evidence_ids':sorted(evidence)}, {'value':amount,'unit':work.result['scope']['unit']}


def check_inventory(run,snap):
    keys=['destination','schedule_id','schedule_review_id','metric','contract_id','declaration']
    actual=list(run.statement_ppe_inputs.order_by('destination').values(*keys))
    expected=sorted([{'destination':r['destination'],'schedule_id':r['schedule_id'],'schedule_review_id':r['schedule_review_id'],
        'metric':r['metric'],'contract_id':run.request['contract_id'],'declaration':r}
        for r in [i['declaration'] for i in snap['inputs']] if r.get('source_type')=='ppe_schedule'],key=lambda r:r['destination'])
    if actual!=expected:raise ValidationError('Statement PPE relational inventory differs from reviewed snapshot')


def is_ppe_statement(run):
    return run.kind=='statement' and any(i['declaration'].get('source_type')=='ppe_schedule' for i in run.snapshot['inputs'])


def recipient_access(run,recipients,*,budget=None):
    if budget is not None and run.kind == 'statement':
        budget.load(run, 'snapshot')
    if not is_ppe_statement(run):return
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(pk__in=recipients):ppe.readable(user,run.case)


def denied_statement_runs(actor, runs, budget):
    """Batch bound run snapshots and exact owning-case PPE grants."""
    budget.load_many(runs, 'snapshot')
    protected = [run for run in runs if is_ppe_statement(run)]
    cases = {run.case_id for run in protected}
    grants = active_case_grants(actor, cases, actions=ppe.READ_ACTIONS)
    denied_cases = {case_id for case_id in cases if any((case_id, action) not in grants for action in ppe.READ_ACTIONS)}
    return [run.pk for run in protected if run.case_id in denied_cases]


def held_opening_statement_ids(case):
    """Select only identities before any statement or controlled draft body is loaded."""
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH RECURSIVE selected(statement_id, schedule_id, depth) AS (
                SELECT line.statement_id, line.schedule_id, 0
                FROM finance_financestatementppeinput line
                JOIN finance_financerun statement ON statement.id=line.statement_id
                WHERE statement.case_id=%s
                UNION ALL
                SELECT selected.statement_id, (schedule.payload->>'prior_id')::bigint, selected.depth + 1
                FROM selected
                JOIN finance_schedulework schedule ON schedule.id=selected.schedule_id
                WHERE schedule.case_id=%s AND selected.depth < 36 AND schedule.payload->>'prior_id' IS NOT NULL
            )
            SELECT DISTINCT selected.statement_id
            FROM selected
            JOIN finance_schedulework schedule ON schedule.id=selected.schedule_id AND schedule.case_id=%s
            WHERE NOT psl_ppe_opening_owner_current((schedule.payload->>'register_id')::bigint)
        """, [case.pk, case.pk, case.pk])
        return [row[0] for row in cursor.fetchall()]
