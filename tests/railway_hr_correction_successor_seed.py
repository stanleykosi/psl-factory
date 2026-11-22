"""Stage the exact synthetic HR correction's later source without making its decision."""
import json
import os
from uuid import UUID

from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence, event
from apps.finance import hrfinance as hr, payroll, payroll_identity
from apps.finance.payroll_models import PayrollHRFollowup
from tests.helpers import rev
from tests.railway_admitted_payroll_seed import MARKER as ORIGINAL_SAMPLE, TENANT
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_HR_CORRECTION_SUCCESSOR_FIXTURE'
CASE = UUID('aeb79335-44bf-5eec-b2f3-387dc75f6a2e')
MARKER = 'sample.payroll_hr_correction_successor_prepared'
INVITATION, MAKER, TRIAL = 7, 243, 1
LINK, RECORD, MATCH, ORIGINAL, REQUEST_PROOF, COMPARISON = 3, 88, 63, 29, 3945, 33891
VERSION = 'SAMPLE-corrected-HR-source-3-v2'
PROOF_SOURCE = 'synthetic:exact-payroll-hr-correction-3'


@transaction.atomic
@sensitive_variables()
def prepare():
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit exact synthetic HR correction guard.')
    actor = fixture_reviewer()
    if actor.pk != TRIAL:
        raise RuntimeError('The original sample HR source holder is required.')
    admission, maker = admitted_user(INVITATION, MAKER, actor)
    case = Case.objects.select_for_update().get(pk=CASE, tenant=TENANT, synthetic=True, kind='project')
    baseline = Audit.objects.get(case=case, actor=actor, action=ORIGINAL_SAMPLE)
    expectation = {'admission': admission.pk, 'invitation': INVITATION, 'maker': maker.pk, 'hr': actor.pk,
                   'hr_snapshot': ORIGINAL, 'match': MATCH}
    if case.pk == admission.invitation.case_id or any(baseline.data.get(key) != value for key, value in expectation.items()):
        raise RuntimeError('Preserve the exact admitted independent sample and original source.')
    if not case.audit.filter(action=payroll_identity.ROUTED, data__comparison=COMPARISON, data__followup=LINK).exists():
        raise RuntimeError('The tested same-ID comparison must already be routed to the exact HR correction.')
    link = PayrollHRFollowup.objects.select_related('record__contract').get(pk=LINK, actor=maker, run_id=MATCH,
        run__request__case=case, record_id=RECORD, record__kind='correction', record__snapshot_id=ORIGINAL,
        record__evidence_id=REQUEST_PROOF, record__contract__need__case=case)
    correction = link.record
    original = hr.exact(case, hr.HRReadSnapshot, ORIGINAL)
    contract = correction.contract
    if (original.actor_id != actor.pk or original.status != 'accepted' or original.contract_id != contract.pk
            or contract.payload['purpose'] != 'payroll_matching'
            or set(contract.payload['fields']) != set(payroll.REQUIRED) or maker.pk not in contract.payload['recipient_ids']):
        raise RuntimeError('Use the same approved minimal HR disclosure and original authorized holder.')
    authorization = hr.authorized(contract)
    hr.authority(actor, case, 'respond')
    payroll_identity.hr_holder(original)
    marker = case.audit.filter(action=MARKER, actor=actor).first()
    if marker is None:
        if hr.correction_disposition(correction).exists() or contract.snapshots.filter(status='accepted', pk__gt=original.pk).exists():
            raise RuntimeError('Preserve the existing correction decision or replacement export.')
        source = {**original.payload, 'source_version': VERSION, 'extracted_at': timezone.now().isoformat()}
        successor = hr.capture(actor, case.pk, contract.pk, 'sample-exact-correction-3-successor',
                               json.dumps(source, sort_keys=True), rev(case))
        hr.snapshot_access(maker, successor)
        proof = add_evidence(actor, case.pk, 'hr_correction_response',
            'Synthetic source for the HR review of the exact same-ID mismatch. The new minimal export leaves authorised '
            'membership dates and business-unit assignments unchanged. Names remain outside this disclosure.', PROOF_SOURCE, rev(case))
        marker = event(actor, case, MARKER, old=original.pk, successor=successor.pk, correction=correction.pk,
                       evidence=proof.pk, finance_receipt_proof=authorization.evidence_id)
    data = marker.data
    successor = hr.exact(case, hr.HRReadSnapshot, data['successor'])
    if (data['correction'] != correction.pk or data['old'] != original.pk or successor.pk <= original.pk
            or successor.contract_id != contract.pk or successor.actor_id != actor.pk
            or successor.payload['source_version'] != VERSION or successor.payload['rows'] != original.payload['rows']
            or not Evidence.objects.filter(case=case, pk=data['evidence'], created_by=actor, kind='hr_correction_response',
                                           source=PROOF_SOURCE).exists()):
        raise RuntimeError('Preserve the exact staged successor and original minimal source facts.')
    hr.snapshot_access(maker, successor)
    decision = hr.correction_disposition(correction).first()
    if decision and (decision.kind != 'response' or decision.snapshot_id != successor.pk
                     or decision.actor_id != actor.pk or decision.evidence_id != data['evidence']):
        raise RuntimeError('This correction has an unrelated human decision; preserve it for review.')
    return {**data, 'case': str(case.pk), 'maker': maker.pk, 'hr': actor.pk,
            'decision': decision.pk if decision else None,
            'finance_receipt': contract.records.filter(kind='receipt', snapshot=successor, actor=maker).exists(),
            'decision_path': reverse('design_hr_payroll_correction', args=[case.pk, link.pk]),
            'receipt_path': reverse('hrfinance', args=[case.pk])}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD)) != (PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
