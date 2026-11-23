"""Same-entity leadership coverage over exact authorized native observations."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.factory_access import department_cases, role_managed
from apps.identity.models import Grant
from apps.identity.services import require
from apps.identity.team_models import StaffMembership
from apps.policy.services import active_component, reference_values


COMPONENT = 'OPS.leadership_project_scope'
MODE = 'all_authorised_projects'
LEAD_MODE = 'all_psl_projects'
CURRENT = 'current_information'
REGISTER_KIND = 'agent_private_leadership_project_register'
REGISTER_SOURCE = 'psl:leadership-project-register/v1'
GENERATED_SOURCE = 'psl:leadership-project-coverage/v1'
THEME_DOMAINS = {'delivery_health': ('meetings', 'actions', 'milestones'), 'risks': ('issues', 'changes'),
                 'performance': ('milestones',), 'escalations': ('escalations',), 'critical_incidents': ('issues',),
                 'progress': ('meetings', 'actions', 'milestones'), 'blockers': ('issues', 'escalations'),
                 'dependencies': ('actions', 'changes')}


def _scalar(query, params):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()[0]


def current_rule(case):
    configuration = active_component(COMPONENT, case)
    if reference_values(configuration) != [{'enabled': True}]:
        raise ValidationError('Multi-project coverage is held until the owner enables it.')
    return configuration


def snapshot(case, inputs):
    value = _scalar('SELECT psl_leadership_manifest(%s,%s::jsonb)::text', [case.pk, json.dumps(inputs)])
    if value is None:
        raise ValidationError('The exact project coverage could not be checked. Review access, current records and the coverage rule.')
    return json.loads(value)


def access(actor, case, manifest):
    if not _scalar('SELECT psl_leadership_access(%s,%s,%s::jsonb)', [case.pk, actor.pk, json.dumps(manifest)]):
        raise PermissionDenied('Current permission to the exact covered projects and evidence is required.')


def project_summary(project_scope):
    return _scalar('SELECT psl_leadership_project_summary(%s::jsonb)', [json.dumps(project_scope)])


def lock_projects(case, manifest, people):
    """Fence current decisions against edits in the projects supplying evidence."""
    scope = manifest.get('project_scope')
    if not scope:
        return
    project_ids = [member['case'] for member in scope['projects']]
    try:
        with transaction.atomic():
            projects = list(Case.objects.select_for_update(nowait=True).filter(pk__in=project_ids).order_by('pk'))
            if len(projects) != len(project_ids) or any(
                (project.tenant, project.kind, project.synthetic) != (case.tenant, 'project', case.synthetic)
                for project in projects
            ):
                raise ValidationError('Leadership coverage no longer matches its original projects.')
            list(Grant.objects.select_for_update(nowait=True).filter(
                case_id__in=project_ids, user_id__in={scope['actor'], *people}).order_by('pk'))
            if scope['mode'] == LEAD_MODE:
                list(StaffMembership.objects.select_for_update(nowait=True, of=('self',)).filter(
                    active=True, mode='lead', user_id__in={scope['actor'], *people}, case_id__in=project_ids
                ).order_by('pk'))
    except OperationalError as exc:
        if getattr(exc.__cause__, 'sqlstate', None) != '55P03':
            raise
        raise ValidationError('A covered project is being updated. Recheck the same report before continuing.') from exc


def citations(manifest):
    scope = manifest['project_scope']
    ids = {source['id'] for member in scope['projects'] for source in member['inventory']['sources']}
    if scope.get('register_id'):
        ids.add(scope['register_id'])
    return sorted(ids)


def sections(manifest, kind):
    from .leadership_reporting import THEMES

    scope = manifest['project_scope']
    fallback = citations(manifest)[:1]
    if not fallback:
        return {}
    definitions = {
        'delivery_health': 'Delivery health remains unconfirmed.',
        'risks': 'Risk severity and coverage need review.',
        'performance': 'These are records of work. Financial performance and overall delivery performance remain unknown.',
        'escalations': 'This records visible escalation requests. Their business outcome needs separate evidence.',
        'critical_incidents': 'Issue records do not establish organization-wide incident coverage or severity.',
        'progress': 'Overall project progress needs review.',
        'blockers': 'Current impact and assigned responsibility need review.',
        'dependencies': 'Open dependencies need review.',
    }
    result = {}
    for theme in THEMES[kind]:
        domains = [domain for domain in THEME_DOMAINS[theme] if domain in scope['record_counts']]
        counts = ', '.join(f"{scope['record_counts'][domain]} {domain}" for domain in domains)
        related = sorted({row[2] for member in scope['projects'] for domain in domains
                          for row in member['inventory'][domain]})
        label = 'Current records include' if scope.get('basis') == CURRENT else 'Current records in the selected period include'
        statement = f'{label} {counts}. ' if counts else ''
        result[theme] = {'text': statement + definitions[theme], 'coverage': 'unknown',
                         'evidence_ids': related[:18] or fallback}
    return result


def prepare_inputs(actor, case, inputs, *, current=False):
    """Accept a human-selected domain list and derive authority and provenance internally."""
    from .leadership_reporting import DOMAINS

    requested = inputs.get('scope')
    if department_lead(actor, case):
        if any(inputs.get('selections', {}).values()) or inputs.get('content_id') is not None:
            raise ValidationError('Leadership reports automatically use all PSL projects and their permitted records.')
        inputs = dict(inputs, selections={domain: [] for domain in DOMAINS}, content_id=None,
                      scope={'mode': LEAD_MODE, 'actor': actor.pk, 'register_id': None, 'domains': sorted(DOMAINS)})
        if current:
            inputs['scope']['basis'] = CURRENT
        manifest = snapshot(case, inputs)
        lock_projects(case, manifest, {actor.pk})
        if snapshot(case, inputs) != manifest:
            raise ValidationError('The PSL project register changed. Start the report again.')
        body = _scalar('SELECT psl_leadership_register(%s::jsonb)::text',
                       [json.dumps(manifest['project_scope']['projects'])])
        register = evidence_for(actor, case, REGISTER_KIND, REGISTER_SOURCE, body)
        inputs['scope']['register_id'] = register.pk
        return with_narrative(actor, case, inputs, snapshot(case, inputs))
    if not case.synthetic or role_managed(actor):
        raise PermissionDenied('The PMO Lead or Finance Lead can generate PSL leadership reports.')
    if requested is None:
        return inputs
    if not isinstance(requested, dict) or set(requested) != {'domains'}:
        raise ValidationError('Choose the areas to include in the authorised project report.')
    domains = requested['domains']
    if not isinstance(domains, list) or not domains or any(type(name) is not str or name not in DOMAINS for name in domains):
        raise ValidationError('Choose at least one report area from the available list.')
    if len(set(domains)) != len(domains):
        raise ValidationError('Choose each report area once.')
    if any(inputs['selections'].values()) or inputs['content_id'] is not None:
        raise ValidationError('Automatic project coverage uses current source records and its own generated report draft.')
    config = current_rule(case)
    scoped = dict(inputs, scope={'mode': MODE, 'actor': actor.pk, 'configuration': config.pk, 'domains': sorted(domains)})
    manifest = snapshot(case, scoped)
    lock_projects(case, manifest, {actor.pk})
    if snapshot(case, scoped) != manifest:
        raise ValidationError('Current project coverage changed. Recheck the selected reporting areas and start again.')
    return with_narrative(actor, case, scoped, manifest)


def department_lead(actor, case):
    return any(department_cases(actor, role, heads_only=True).filter(pk=case.pk).exists()
               for role in ('pmo-lead', 'finance-lead'))


def require_report(actor, case):
    if not department_cases(actor, 'finance-lead', heads_only=True).filter(pk=case.pk).exists():
        require(actor, case, 'report.read')


def evidence_for(actor, case, kind, source, body):
    evidence = case.evidence.filter(kind=kind, source=source, body=body, created_by=actor).order_by('-pk').first()
    return evidence or add_evidence(actor, case.pk, kind, body, source)


def with_narrative(actor, case, scoped, manifest):
    from .leadership_reporting import CONTENT, MODE as NARRATIVE_MODE

    themes = sections(manifest, scoped['kind'])
    if themes:
        body = json.dumps({'kind': scoped['kind'], 'protocol': NARRATIVE_MODE, 'sections': themes}, sort_keys=True)
        scoped['content_id'] = evidence_for(actor, case, CONTENT, GENERATED_SOURCE, body).pk
    return scoped
