"""P40/P42 human-cited preparation. No calculated health or Finance performance.

Native document review, distribution and receipts remain the execution boundary.
This service does not register a factory envelope or invent publication cadence.
"""
import json
from collections import defaultdict
from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.evidence_access import (
    CONFIRMED_CHANGE_SOURCE, forecast_private, forecast_private_query, other_private_query, restricted,
)
from apps.core.services import lock_case, add_evidence, event
from apps.identity.services import active_case_grants, require
from apps.documents.contracts import validate
from apps.documents.models import Template, Publication, PublicationReceipt
from .clocks import aware
from .models import Meeting, ActionItem, Milestone, Issue, ChangeRequest, EscalationRequest, PeriodReport, MinutesReportBinding
from .reporting import report_source_access

MODE = 'leadership_selected_facts/v1'
CONTENT = 'agent_private_leadership_report_content'
THEMES = {
    'internal_tuesday': ['progress', 'risks', 'blockers', 'dependencies'],
    'monthly_executive': ['delivery_health', 'risks', 'performance', 'escalations', 'critical_incidents'],
}
DOMAINS = {'meetings': 'meeting.read', 'actions': 'meeting.read', 'milestones': 'meeting.read',
           'issues': 'issue.read', 'changes': 'change.read', 'escalations': 'issue.read'}
SOURCE_OVERLAPS = (
    ('meeting.read', Meeting, 'case_id', 'current__evidence_id'),
    ('meeting.read', ActionItem, 'case_id', 'current__evidence_id'),
    ('meeting.read', Milestone, 'case_id', 'evidence_id'),
    ('issue.read', Issue, 'case_id', 'current__evidence_id'),
    ('change.read', ChangeRequest, 'case_id', 'current__evidence_id'),
    ('issue.read', EscalationRequest, 'profile__state__issue__case_id', 'evidence_id'),
)


def window(kind, start, end, audience):
    start, end = aware(start, 'Period start'), aware(end, 'Period end')
    if kind not in THEMES or end <= start or end - start > timedelta(days=366) or end > timezone.now():
        raise ValidationError('Choose an elapsed native report period of at most 366 days')
    if audience not in (['internal'] if kind == 'internal_tuesday' else ['internal', 'management']):
        raise ValidationError('Leadership preparation supports only the selected internal audience')
    return start, end


def inventory(actor, case, start, end, selections):
    """Authorize before fetching selected rows; never expand to raw case histories."""
    require(actor, case, 'report.read')
    ids = {'type': 'array', 'maxItems': 200, 'uniqueItems': True,
           'items': {'type': 'integer', 'minimum': 1}}
    validate({'type': 'object', 'properties': {k: ids for k in DOMAINS},
              'required': list(DOMAINS), 'additionalProperties': False}, selections)
    queries = {
        'meetings': Meeting.objects.filter(case=case, current__occurred_at__gte=start, current__occurred_at__lt=end),
        'actions': ActionItem.objects.filter(case=case),
        'milestones': Milestone.objects.filter(case=case, completed_at__gte=start, completed_at__lt=end),
        'issues': Issue.objects.filter(case=case), 'changes': ChangeRequest.objects.filter(case=case),
        'escalations': EscalationRequest.objects.filter(profile__state__issue__case=case,
            profile__state_id=F('profile__state__issue__current_id')),
    }
    manifest, evidence_ids, gaps = {}, set(), []
    source_actions = set()
    for domain, selected in selections.items():
        if any(type(pk) is not int for pk in selected):
            raise ValidationError('Exact positive native source identifiers required')
        if selected:
            require(actor, case, DOMAINS[domain]); source_actions.add(DOMAINS[domain])
        rows = list(queries[domain].filter(pk__in=selected).order_by('pk'))
        if len(rows) != len(selected):
            raise ValidationError('Selected '+domain+' source is missing, outside this project/window, or no longer current')
        manifest[domain] = []
        for row in rows:
            state = row.current if domain in ['meetings', 'actions', 'issues', 'changes'] else row
            evidence_ids.add(state.evidence_id)
            manifest[domain].append([row.pk, state.pk, state.evidence_id])
            if domain == 'escalations':
                from .escalations import current_request, approved_request
                current_request(case, row.pk)
                decision = row.decisions.order_by('-pk').first()
                if decision and decision.verdict == 'approve': approved_request(case, row)
                manifest.setdefault('escalation_decisions', []).append([row.pk, decision.pk if decision else None])
            if domain == 'actions':
                gaps.append({'action_id': row.pk, 'owner_unknown': state.owner_id is None,
                             'deadline_unknown': state.due_at is None, 'status': state.status})
    confirmed = set(ChangeRequest.objects.filter(case=case, pk__in=selections['changes']).values_list('current__evidence_id', flat=True))
    sources, overlapping = authorize_sources(actor, case, evidence_ids, confirmed)
    manifest['source_actions'] = sorted(source_actions | overlapping)
    manifest['sources'] = [{'id': e.pk, 'sha256': e.sha256, 'version': e.version} for e in sources]
    return manifest, sources, gaps


def authorize_sources(actor, case, evidence_ids, confirmed):
    """Historical grants persist, and later private-domain reuse cannot widen access."""
    actions = set()
    for action, model, case_lookup, evidence_lookup in SOURCE_OVERLAPS:
        if model.objects.filter(**{case_lookup: case.pk, f'{evidence_lookup}__in': evidence_ids}).exists():
            require(actor, case, action)
            actions.add(action)
    # Raw native bodies are never extracted or copied by this report path.
    sources = list(Evidence.objects.filter(case=case, pk__in=evidence_ids).defer('body').order_by('pk'))
    if len(sources) != len(evidence_ids) or any(forecast_private(e) or restricted(e) and not
            (e.pk in confirmed and e.source == CONFIRMED_CHANGE_SOURCE) for e in sources):
        raise PermissionDenied('Selected source requires an unsupported private domain interface')
    return sources, actions


def content(case, kind, content_id, sources):
    e = Evidence.objects.filter(case=case, pk=content_id, kind=CONTENT).first()
    if not e or forecast_private(e): raise ValidationError('Select this project human-authored leadership narrative')
    try: data = json.loads(e.body)
    except (TypeError, ValueError): raise ValidationError('Typed leadership narrative required') from None
    section = {'type': 'object', 'properties': {
        'text': {'type': 'string', 'minLength': 1, 'maxLength': 10000},
        'evidence_ids': {'type': 'array', 'minItems': 1, 'maxItems': 18, 'uniqueItems': True,
                         'items': {'type': 'integer', 'minimum': 1}},
        'coverage': {'enum': ['supported', 'partial', 'unknown', 'not_applicable']}},
        'required': ['text', 'evidence_ids', 'coverage'], 'additionalProperties': False}
    validate({'type': 'object', 'properties': {'protocol': {'const': MODE}, 'kind': {'const': kind},
        'sections': {'type': 'object', 'properties': {k: section for k in THEMES[kind]},
                     'required': THEMES[kind], 'additionalProperties': False}},
        'required': ['protocol', 'kind', 'sections'], 'additionalProperties': False}, data)
    allowed = {source.pk for source in sources}
    for key, value in data['sections'].items():
        if value['text'].strip().casefold() in ['', 'tbd', 'todo', 'unknown', 'n/a', 'pending']:
            raise ValidationError('Explain '+key+' facts or missing coverage rather than a placeholder')
        if any(type(pk) is not int or pk not in allowed for pk in value['evidence_ids']):
            raise ValidationError('Every theme needs exact selected native evidence, including explanations of missing coverage')
    return e, data['sections']


def package(actor, case, kind, start, end, audience, selections, content_id):
    if case.kind != 'project': raise ValidationError('Leadership reporting requires a project')
    start, end = window(kind, start, end, audience)
    manifest, sources, gaps = inventory(actor, case, start, end, selections)
    narrative, sections = content(case, kind, content_id, sources)
    manifest.update(source_mode=MODE, selections={key: sorted(ids) for key, ids in selections.items()},
                    content={'id': narrative.pk, 'sha256': narrative.sha256})
    from .incident_reporting import bind
    bind(actor, case, manifest, sections)
    return manifest, sources, gaps, sections


def investigate(actor, case, kind, start, end, audience, selections, content_id):
    manifest, sources, gaps, sections = package(actor, case, kind, start, end, audience, selections, content_id)
    return {'capability': 'Selected leadership source coverage and unsupported-claim investigation',
        'source_manifest': manifest, 'as_of': timezone.now().isoformat(), 'commitment_gaps': gaps,
        'themes': {key: {'coverage': value['coverage'], 'evidence_ids': value['evidence_ids']} for key, value in sections.items()},
        'source_dates': [{'evidence_id': e.pk, 'recorded_at': e.created_at.isoformat()} for e in sources],
        'unknowns': ['Unselected records and external systems are not covered',
                    'Recorded time is not proof of operational freshness',
                    'No overall health, risk score, performance denominator or financial metric is calculated'],
        'approval_granted': False, 'communications_dispatched': False}


@transaction.atomic
def prepare(actor, case_id, kind, start, end, template_id, audience, selections, content_id, expected, *, force_revision=False):
    case = lock_case(actor, case_id, 'report.draft', expected)
    manifest, sources, gaps, sections = package(actor, case, kind, start, end, audience, selections, content_id)
    start, end = window(kind, start, end, audience)
    template = Template.objects.filter(case=case, pk=template_id, definition__document_type='status_report').first()
    required = {'executive_summary', *THEMES[kind]}
    if not template or template.definition.get('internal_review_required') != (kind=='monthly_executive') or set(template.definition['required_fields']) != required or set(template.definition['audience_fields'].get(audience, [])) != required:
        raise ValidationError('Select an exact theme-complete internal template with purpose-specific review requirements')
    report, _ = PeriodReport.objects.get_or_create(case=case, kind=kind, start_at=start, end_at=end, audience=audience)
    old = MinutesReportBinding.objects.filter(report=report, version_id=report.document.current_id if report.document_id else None).first()
    if not force_revision and old and old.manifest == manifest and old.version.template_id == template.pk:
        review = old.version.reviews.order_by('-pk').first()
        if not review or review.verdict == 'approve':
            from apps.documents.controlled import current_version
            try: current_version(case, old.version_id)
            except ValidationError: pass
            else: return old
    if Publication.objects.filter(version__minutesreportbinding__report=report, job__status__in=['pending', 'unknown', 'leased', 'held']).exists():
        raise ValidationError('Resolve original report delivery before revising its source package')
    values = {key: '['+value['coverage']+'] '+value['text'] for key, value in sections.items()}
    values['executive_summary'] = (kind.replace('_', ' ').title()+' · '+start.isoformat()+' / '+end.isoformat()+
        '. Selected native PMO evidence only. Unselected records, external systems and Finance reporting are not covered. '
        'Human project-performance statements are not calculated financial performance. Source timestamps do not establish completeness or freshness.')
    from .incident_reporting import summary
    values['executive_summary'] += summary(manifest)
    projection = add_evidence(actor, case.pk, 'ops_leadership_report_projection',
        json.dumps(values, sort_keys=True), 'psl:leadership-report:'+str(report.pk))
    case.refresh_from_db()
    from apps.documents.controlled import _create_version
    version = _create_version(actor, case.pk, template.pk,
        report.document.title if report.document_id else 'Report: '+kind+' · '+start.isoformat()+' / '+end.isoformat(),
        audience, {k: {'text': v, 'evidence_ids': [projection.pk]} for k, v in values.items()}, case.revision,
        report.document_id, authorized_restricted_source_ids=[projection.pk])
    if not report.document_id:
        report.document = version.document; report.save(update_fields=['document'])
    binding = MinutesReportBinding.objects.create(version=version, report=report, manifest=manifest)
    event(actor, case, 'report.leadership_prepared', report=report.pk, version=version.pk, binding=binding.pk)
    return binding


def binding_access(actor, version, *, budget=None):
    bindings = MinutesReportBinding.objects.filter(version=version, manifest__source_mode=MODE).select_related('report__case')
    if budget is not None:
        bindings = bindings.defer('manifest', 'policies')
    b = bindings.first()
    if not b: return
    if budget is not None:
        require(actor, b.report.case, 'report.read')
        budget.load(b, 'manifest')
    _bound_access(actor, b.report.case, b.manifest, version.created_at, budget=budget)


def _bound_access(actor, case, manifest, recorded_at, *, budget):
    report_source_access(actor, case, manifest, budget=budget)
    if 'incident_claims' not in manifest:
        from .incident_reporting import legacy_access
        legacy_access(actor, case, manifest, recorded_at, budget=budget)
    _manifest_actions(actor, case, manifest, require)
    ids, confirmed = _source_ids(manifest)
    authorize_sources(actor, case, ids, confirmed)


def _manifest_actions(actor, case, manifest, require_action):
    if manifest.get('escalations'):
        require_action(actor, case, 'issue.read')
    for action in manifest.get('source_actions', []):
        require_action(actor, case, action)


def _source_ids(manifest):
    ids = {s['id'] for s in manifest['sources']}
    confirmed = {row[2] for row in manifest.get('changes', [])}
    return ids, confirmed


def _selected_evidence(references):
    pairs = Q(pk__in=[])
    for case_id, ids in references.items():
        pairs |= Q(case_id=case_id, pk__in=ids)
    return Evidence.objects.filter(pairs)


def _source_facts(references):
    overlaps = {}
    for index, (_, model, case_lookup, evidence_lookup) in enumerate(SOURCE_OVERLAPS):
        overlaps[f'_overlap_{index}'] = Exists(model.objects.filter(
            **{case_lookup: OuterRef('case_id'), evidence_lookup: OuterRef('pk')},
        ))
    rows = _selected_evidence(references).annotate(
        forecast=forecast_private_query(same_case=True),
        other_private=other_private_query(),
        **overlaps,
    ).values_list('case_id', 'pk', 'source', 'forecast', 'other_private', *overlaps)
    return {
        (case_id, pk): (source, forecast, private, {
            action for (action, *_), present in zip(SOURCE_OVERLAPS, flags) if present
        })
        for case_id, pk, source, forecast, private, *flags in rows
    }


def _check_source_facts(case, ids, confirmed, facts, grants):
    for pk in ids:
        fact = facts.get((case.pk, pk))
        if fact is None:
            return False
        source, forecast, private, actions = fact
        if forecast or (private and not (pk in confirmed and source == CONFIRMED_CHANGE_SOURCE)):
            return False
        if any((case.pk, action) not in grants for action in actions):
            return False
    return True


def denied_binding_templates(actor, bindings, budget):
    """Batch current grant and citation facts while retaining exact incident checks."""
    from .incident_reporting import legacy_access, narrative_citations

    grants = active_case_grants(actor, {binding.report.case_id for binding in bindings})
    admitted = [binding for binding in bindings if (binding.report.case_id, 'report.read') in grants]
    denied = {binding.version.template_id for binding in bindings if (binding.report.case_id, 'report.read') not in grants}
    budget.load_many(admitted, 'manifest')

    def require_action(actor, case, action):
        if (case.pk, action) not in grants:
            raise PermissionDenied('This record/action has no active grant')

    groups = defaultdict(list)
    for binding in admitted:
        manifest = binding.manifest
        # Only legacy incident history depends on the version's timestamp.
        cutoff = binding.version.created_at if 'incident_claims' not in manifest and manifest.get('issues') else None
        groups[(binding.report.case_id, cutoff, json.dumps(manifest, sort_keys=True))].append(binding)

    ready, narratives = [], defaultdict(set)
    for group in groups.values():
        binding = group[0]
        case, manifest = binding.report.case, binding.manifest
        templates = {member.version.template_id for member in group}
        try:
            report_source_access(actor, case, manifest, budget=budget, require_action=require_action)
        except PermissionDenied:
            denied.update(templates)
            continue
        narrative = None
        if 'incident_claims' not in manifest:
            pk = Evidence._meta.pk.get_prep_value(manifest['content']['id'])
            narrative = (case.pk, pk)
            narratives[case.pk].add(pk)
        ready.append((binding, templates, narrative))

    bodies = list(_selected_evidence(narratives).only('id', 'case_id'))
    budget.load_many(bodies, 'body')
    retained = {(row.case_id, row.pk): row for row in bodies}
    parsed = {}
    source_checks, references = [], defaultdict(set)
    for binding, templates, narrative in ready:
        case, manifest = binding.report.case, binding.manifest
        try:
            if narrative is not None:
                if narrative not in retained:
                    raise Evidence.DoesNotExist('Exact retained report narrative is missing')
                if narrative not in parsed:
                    parsed[narrative] = narrative_citations(retained[narrative].body)
                legacy_access(actor, case, manifest, binding.version.created_at, budget=budget, citations=parsed[narrative])
            _manifest_actions(actor, case, manifest, require_action)
            ids, confirmed = _source_ids(manifest)
            if any(type(pk) is not int for pk in ids):
                # Retain native coercion and cardinality semantics for legacy IDs.
                authorize_sources(actor, case, ids, confirmed)
                continue
        except PermissionDenied:
            denied.update(templates)
            continue
        references[case.pk].update(ids)
        source_checks.append((case, ids, confirmed, templates))

    facts = _source_facts(references)
    for case, ids, confirmed, templates in source_checks:
        if not _check_source_facts(case, ids, confirmed, facts, grants):
            denied.update(templates)
    return denied


def current_manifest(binding):
    r = binding.report
    if binding.version.document.current_id != binding.version_id:
        return {'superseded': True}
    try:
        return package(binding.version.created_by, r.case, r.kind, r.start_at, r.end_at, r.audience,
                       binding.manifest['selections'], binding.manifest['content']['id'])[0]
    except (ValidationError, PermissionDenied):
        return {'current_source_unavailable': True}


AUDIENCE_COMPONENT = 'OPS.leadership_audience'
AUDIENCE_PURPOSES = ['internal_tuesday:internal', 'monthly_executive:internal', 'monthly_executive:management']


def recipient_access(version, recipients):
    binding = MinutesReportBinding.objects.filter(version=version, manifest__source_mode=MODE).select_related('report__case').first()
    if not binding: return {}
    from apps.policy.services import active_component, reference_values
    from django.contrib.auth import get_user_model
    cfg = active_component(AUDIENCE_COMPONENT, binding.report.case)
    members = reference_values(cfg)[0][binding.report.kind+':'+version.audience]
    if members is None:
        raise ValidationError('owner_needed: Supply the actual PMO participants or leadership recipients for this report purpose')
    if sorted(members) != sorted(recipients):
        raise ValidationError('Document recipients must exactly match the owner-designated report participants for this purpose')
    for actor in get_user_model().objects.filter(pk__in=recipients): binding_access(actor, version)
    return {AUDIENCE_COMPONENT: cfg.pk}


def verify(actor, binding):
    from apps.documents.controlled import current_version, validate_review, publication_requirements
    binding_access(actor, binding.version)
    v = current_version(binding.report.case, binding.version_id)
    review = validate_review(binding.report.case, v)
    policies, recipients, retention = publication_requirements(binding.report.case, v)
    p = Publication.objects.filter(version=v, review=review, policies=policies,
        recipient_ids=recipients, retention_days=retention).first()
    receipts = list(PublicationReceipt.objects.filter(publication=p)) if p else []
    if not p or p.job.status != 'confirmed' or {r.recipient_id for r in receipts} != set(recipients) or any(r.payload != v.payload or r.payload_sha256 != v.payload_sha256 for r in receipts):
        raise ValidationError('Await exact current reviewed report and every configured recipient receipt')
    return {'verified': True, 'scope': 'selected_native_leadership_report', 'publication': p.pk,
            'receipt_ids': [r.pk for r in receipts], 'complete_project_coverage': False, 'external_delivery_verified': False}


REVIEW_COMPONENT = 'OPS.leadership_review_authority'


def review_context(version):
    """Only model-bound P40 has no extra approval; P42 uses an owner-selected existing role."""
    binding = MinutesReportBinding.objects.filter(version=version, manifest__source_mode=MODE).select_related('report__case').first()
    if not binding: return 'PMO Lead', {}
    if binding.report.kind == 'internal_tuesday':
        if binding.report.audience!='internal' or version.audience!='internal' or version.template.definition.get('internal_review_required') is not False:
            raise ValidationError('No-approval handling is restricted to the exact internal Tuesday report')
        return None, {}
    if binding.report.kind!='monthly_executive' or binding.report.audience not in ['internal','management'] or version.audience!=binding.report.audience or version.template.definition.get('internal_review_required') is not True:
        raise ValidationError('Monthly leadership review requires the exact internal monthly report')
    from apps.policy.services import active_component, reference_values
    policy = active_component(REVIEW_COMPONENT, binding.report.case)
    role = reference_values(policy)[0]['role']
    if role is None: raise ValidationError('owner_needed: Configure the existing D05 role responsible for internal PMO leadership review')
    return role, {REVIEW_COMPONENT: policy.pk}
