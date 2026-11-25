"""Add the synthetic test document templates every Start work line needs to the psl-demo projects.

Safe to re-run: a template is skipped when its name (or the older seed's name) already exists in the project, and
nothing is overwritten or deleted. The templates are generic test fixtures, not PSL's real templates; the D11 storage
and retention rule is revised to list every template of the project.
"""
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.documents.models import Template
from apps.policy.registry import components
from apps.policy.services import reference_values, register_reference, resolve, save_draft, transition

TENANT = 'psl-demo'
SETUP = 'psl-demo-setup'
COMPONENT = 'D11.template_storage_retention_rules'
SECTIONS = ['executive_summary', 'scope', 'timeline', 'risks', 'dependencies', 'status', 'next_steps']
LEADERSHIP = {'internal_tuesday': ['progress', 'risks', 'blockers', 'dependencies'],
              'monthly_executive': ['delivery_health', 'risks', 'performance', 'escalations', 'critical_incidents']}
FINANCE = ['executive_summary', 'financial_metrics', 'bu_totals']
MINUTES = ['executive_summary', 'decisions', 'actions', 'owners', 'deadlines']


def definition(kind, required, audiences, **extra):
    return {'document_type': kind, 'required_fields': required, 'audience_fields': audiences, **extra}


def leadership(kind):
    fields = ['executive_summary', *LEADERSHIP[kind]]
    return definition('status_report', fields, {'internal': fields, 'management': fields},
                      internal_review_required=kind == 'monthly_executive')


ARTIFACT = definition('project_artifact', ['executive_summary', 'scope', 'status', 'next_steps'],
                      {'client': SECTIONS, 'internal': SECTIONS})
# (name, older name from seed_psl_demo or None, definition)
TEMPLATES = [
    ('Meeting minutes (test template)', None, definition('minutes', MINUTES, {
        audience: [*MINUTES, 'participants', 'scope', 'timeline', 'risks', 'dependencies', 'status']
        for audience in ('client', 'internal')})),
    ('Weekly client report (test template)', 'Weekly client report', definition(
        'status_report', SECTIONS, {'client': SECTIONS, 'internal': SECTIONS})),
    ('Internal Tuesday leadership report (test template)', None, leadership('internal_tuesday')),
    ('Monthly executive leadership report (test template)', None, leadership('monthly_executive')),
    ('Project SOW (test template)', 'Project SOW', definition(
        'sow', ['executive_summary', 'scope', 'timeline'], {'client': SECTIONS})),
    ('RFP response (test template)', 'RFP response', definition(
        'rfp_response', ['executive_summary', 'scope', 'requirements_mapping', 'commercial_terms'],
        {'client': [*SECTIONS, 'requirements_mapping', 'commercial_terms']}, internal_review_required=True)),
    ('Project artifact: kick-off note (test template)', None, ARTIFACT),
    ('Project artifact: go-live note (test template)', None, ARTIFACT),
    ('Project artifact: handover note (test template)', None, ARTIFACT),
    ('Project artifact: closure note (test template)', None, ARTIFACT),
    ('Management accounts report (test template)', None, definition(
        'finance_report', FINANCE, {'internal': FINANCE, 'management': FINANCE}, internal_review_required=False)),
    ('BU totals report (test template)', None, definition(
        'finance_group_report', FINANCE, {'group': FINANCE}, internal_review_required=True)),
]


def add_templates(actor, case):
    """Register the missing test templates for one project and return their names; revise D11 when any were added."""
    case.refresh_from_db()
    owner = add_evidence(actor, case.pk, 'policy_decision',
                         'Synthetic test document templates for the demo. Generic fixtures, not PSL business policy.',
                         'synthetic:psl-demo-templates')
    added = []
    for name, older, value in TEMPLATES:
        if Template.objects.filter(case=case, name__in=[name, older or name]).exists():
            continue
        case.refresh_from_db()
        register_template(actor, case.pk, name, value, owner.pk, case.revision)
        added.append(name)
    ids = sorted(Template.objects.filter(case=case).values_list('pk', flat=True))
    current = resolve(COMPONENT, case)
    if current.status == 'ACTIVE' and added == []:
        if sorted(reference_values(current.configuration)[0]['template_ids']) == ids:
            return added
    reference = register_reference(actor, case.pk, 'psl-demo:templates:' + str(uuid4()), 'schema:psl/document-storage/v1',
                                   {'template_ids': ids, 'repository': 'internal-versioned', 'retention_days': 30},
                                   owner.pk)
    config = save_draft(actor, case.pk, {
        'slot_id': components()[COMPONENT]['parent_decision_id'], 'component_id': COMPONENT,
        'component_schema_ref': components()[COMPONENT]['schema_ref'], 'schema_version': '1',
        'subject_scope': {'kind': 'project', 'ref': str(case.pk)}, 'policy_revision': 1, 'lifecycle': 'draft',
        'effective_from': (timezone.now() - timedelta(minutes=1)).isoformat(), 'effective_until': None,
        'evidence_refs': [f'evidence:{owner.pk}'], 'human_decision_ref': f'evidence:{owner.pk}',
        'implementation_id': 'psl.reference-validation', 'implementation_version': '1',
        'reviewed_implementation_ref': 'code:apps/policy/services.py#reference-validation-v1',
        'fixture_scope': 'synthetic_test',
        'value': {'artifact_ref': reference.ref, 'artifact_version': reference.version, 'sha256': reference.sha256,
                  'schema_ref': reference.schema_ref}})
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')
    return added


def seed_demo_templates(actor):
    result = {}
    for case in Case.objects.filter(tenant=TENANT, synthetic=True, kind='project').order_by('title'):
        result[case.title] = add_templates(actor, case)
    return result


class Command(BaseCommand):
    help = 'Add the synthetic test document templates to each psl-demo project (safe to re-run; adds only what is missing)'

    def handle(self, *args, **options):
        if not Case.objects.filter(tenant=TENANT).exists():
            raise CommandError('The psl-demo tenant does not exist; run seed_psl_demo first')
        actor = get_user_model().objects.filter(username=SETUP).first()
        if actor is None:
            raise CommandError('The psl-demo setup user does not exist')
        for title, added in seed_demo_templates(actor).items():
            self.stdout.write(f'{title}: {len(added)} added' + (': ' + ', '.join(added) if added else ''))
