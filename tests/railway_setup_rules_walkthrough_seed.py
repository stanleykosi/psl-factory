"""Add a synthetic Rules and wrong-role delegation browser specimen."""
import json
import os
from datetime import timedelta
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.identity.models import Grant
from apps.policy.role_assignments import draft
from apps.policy.services import transition
from tests.document_helpers import DEFINITION, artifact
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_SETUP_RULES_WALKTHROUGH'
TENANT = 'design-setup-rules-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
TITLE = 'SAMPLE workspace rules and delegation validation'
PROOF = 'synthetic:setup-rules-walkthrough'
WRONG_ROLE_USER = 'sample-setup-rules-finance'
VALID_ROLE_USER = 'sample-setup-rules-pmo-lead'
ROLE = 'PMO Lead'
TRIAL_GRANTS = ('case.read', 'policy.read', 'policy.configure', 'policy.activate',
                'evidence.add', 'rfp.read', 'document.read', 'document.template', 'delivery.read',
                'finance.read', 'finance.short_payment.read', 'costing.read', 'costing.source.read')


@transaction.atomic
def prepare():
    user_model = get_user_model()
    actor = user_model.objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    case, created = Case.objects.get_or_create(pk=CASE_ID, tenant=TENANT, kind='project', synthetic=True, title=TITLE)
    if created:
        wrong = user_model.objects.create_user(WRONG_ROLE_USER, first_name='Sample Finance', last_name='Staff')
        delegate = user_model.objects.create_user(VALID_ROLE_USER, first_name='Sample Project Management', last_name='Lead')
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in TRIAL_GRANTS] + [
            Grant(case=case, user=wrong, action='case.read'),
            Grant(case=case, user=delegate, action='case.read'),
            Grant(case=case, user=wrong, action='finance.read'),
            Grant(case=case, user=wrong, action='finance.short_payment.read'),
            Grant(case=case, user=wrong, action='finance.short_payment.decide'),
        ])
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic workspace rule evidence for browser acceptance.', PROOF)
        config = draft(actor, case.pk, [{'role': ROLE, 'user_id': actor.pk},
              {'role': ROLE, 'user_id': delegate.pk}, {'role': 'Finance', 'user_id': wrong.pk}], proof.pk, timezone.now())
        transition(actor, config.pk, 'validated')
        transition(actor, config.pk, 'active')
        artifact(actor, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v2',
                 {'rfp': {'assignment_roles': [ROLE], 'outcome_roles': ['CEO']}}, proof)
        artifact(actor, case, 'OPS.invoice_short_payment_review', 'schema:psl/invoice-short-payment-review/v1',
                 {'reviewer_id': wrong.pk, 'treatments': ['request_proof']}, proof)
        template = register_template(actor, case.pk, 'Sample controlled status', DEFINITION, proof.pk, rev(case))
        artifact(actor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v2',
                 {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30,
                  'closure_inventory': {'required_kinds': ['technical_document', 'test_results', 'project_artifact'],
                                        'archive_mode': 'immutable_local_manifest'}}, proof)
    proof = case.evidence.get(kind='policy_decision', source=PROOF)
    wrong, delegate = [user_model.objects.get(username=name, is_active=True, is_staff=False, is_superuser=False)
                       for name in (WRONG_ROLE_USER, VALID_ROLE_USER)]
    start = timezone.now().replace(microsecond=0) + timedelta(hours=2)
    return {
        'case': str(case.pk), 'rules': reverse('workspace_settings', args=[case.pk]) + '?area=rules',
        'delegation': reverse('design_delegation', args=[case.pk]) + '?' + urlencode({'role': ROLE}),
        'principal': actor.pk, 'wrong_person': wrong.pk, 'valid_person': delegate.pk,
        'role': ROLE, 'evidence': proof.pk, 'starts': start.isoformat(),
        'invalid_end': (start - timedelta(hours=1)).isoformat(), 'valid_end': (start + timedelta(hours=1)).isoformat(),
        'effective': start.isoformat(),
    }


def run():
    project = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if project != (PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The isolated Railway preview database and Setup walkthrough guard are required.')
    print(json.dumps(prepare(), sort_keys=True))
