"""Selected typed incident citations, never a second incident lifecycle.

A citation matching an incident link on a selected issue is an explicit claim.
Unrelated links neither confer authority nor become report dependencies.
"""
from datetime import timezone
from django.core.exceptions import ValidationError
from apps.identity.services import require
from . import issue_references as refs
from .issue_access import issue_subject
from .models import Issue, IssueState, IssueReferenceRevision


def claims(actor, case, selections, sections, *, historical_at=None, states=None):
    result = []
    for theme, section in sorted(sections.items()):
        for citation in sorted(section['evidence_ids']):
            matches = []
            for issue in Issue.objects.filter(case=case, pk__in=selections['issues']).select_related('current'):
                revisions = issue.reference_revisions.order_by('-number')
                if historical_at is not None:
                    revisions = revisions.filter(created_at__lte=historical_at)
                revisions = list(revisions)
                state = IssueState.objects.get(issue=issue, pk=states[issue.pk]) if states else issue.current
                links = revisions[0].references if revisions else state.external_links
                if historical_at is None and not any(link['kind'] == 'incident' and link['evidence_id'] == citation for link in links):
                    if any(link['kind'] == 'incident' and link['evidence_id'] == citation for revision in revisions for link in revision.references):
                        raise ValidationError('Selected incident citation was removed; select current source evidence')
                for link in links:
                    if link['kind'] != 'incident' or link['evidence_id'] != citation:
                        continue
                    # Exact selected membership provenance, not whole-issue latest-wins.
                    origin = None
                    for revision in revisions:
                        if link not in revision.references:
                            break
                        origin = revision
                    matches.append((issue, link, origin))
            if len(matches) > 1:
                raise ValidationError('Ambiguous incident citation: select distinct source evidence for the intended incident')
            if not matches:
                continue
            issue, link, origin = matches[0]
            pin = {'theme': theme, 'issue_id': issue.pk, 'revision_id': origin.pk if origin else None,
                   'reference': link, 'observation_id': link.get('observation_id'),
                   'source_sha256': None, 'observed_at': None, 'availability': 'unknown',
                   'currentness': 'unobserved', 'freshness': 'unknown', 'fields': {},
                   'source_authenticity_verified': False}
            selected_access(actor, case, pin)
            if pin['observation_id']:
                row = refs.observation(actor, case, pin['observation_id'], issue)
                if row.contract.kind != 'incident' or row.source_ref != link['source_ref']:
                    raise ValidationError('Exact selected incident observation required')
                if historical_at is None and (refs.source_superseded(row) or issue.reference_observations.filter(
                        contract=row.contract, source_ref=row.source_ref, pk__gt=row.pk).exists()):
                    raise ValidationError('Selected incident observation is superseded; obtain the current source reference')
                pin.update(source_sha256=row.source_sha256,
                    observed_at=row.observed_at.astimezone(timezone.utc).isoformat(timespec='microseconds'),
                    availability=row.availability, currentness='current', fields=row.fields)
            if historical_at is None and pin['availability'] != 'available' and section['coverage'] != 'unknown':
                raise ValidationError('Unavailable or unobserved incident citation requires explicitly unknown coverage')
            result.append(pin)
    return result


def selected_access(actor, case, pin):
    """Historical permission is independent of current source availability."""
    require(actor, case, 'issue.read')
    issue_subject(case, pin['reference']['evidence_id'])
    if pin['revision_id'] is not None:
        revision = IssueReferenceRevision.objects.filter(pk=pin['revision_id'], issue_id=pin['issue_id'], issue__case=case).first()
        if not revision or pin['reference'] not in revision.references:
            raise ValidationError('Exact retained incident membership required')
        issue_subject(case, revision.evidence_id)
        require(revision.actor, case, 'issue.manage')
    if pin['observation_id'] is not None:
        row = refs.observation(actor, case, pin['observation_id'])
        if row.issue_id != pin['issue_id'] or row.contract.kind != 'incident' or row.source_ref != pin['reference']['source_ref']:
            raise ValidationError('Exact retained incident observation required')


def bind(actor, case, manifest, sections):
    pins = claims(actor, case, manifest['selections'], sections)
    if pins:
        manifest['incident_claims'] = pins
    return manifest


def summary(manifest):
    """Only provenance, no inferred severity mapping, timing calculation or RCA."""
    return ''.join(' Incident source '+str(pin['reference']['evidence_id'])+
        ' as of '+(pin['observed_at'] or 'unknown')+'; availability '+pin['availability']+
        '; freshness unknown; source authenticity unverified.' for pin in manifest.get('incident_claims', []))


def legacy_access(actor, case, manifest, recorded_at):
    """Conservative scopes from recorded history, NOT an original claim binding.

    Never persist these candidates or treat them as current report provenance.
    Ambiguous histories require all recorded candidate scopes, not a guessed one.
    """
    import json
    from apps.core.models import Evidence
    narrative = Evidence.objects.get(case=case, pk=manifest['content']['id'])
    citations = {pk for section in json.loads(narrative.body)['sections'].values() for pk in section['evidence_ids']}
    for issue_id, state_id, _ in manifest['issues']:
        issue = Issue.objects.get(case=case, pk=issue_id)
        revisions = list(issue.reference_revisions.filter(created_at__lte=recorded_at).order_by('-number'))
        state = IssueState.objects.get(issue=issue, pk=state_id)
        links = revisions[0].references if revisions else state.external_links
        for link in links:
            if link['kind'] != 'incident' or link['evidence_id'] not in citations:
                continue
            origin = None
            for revision in revisions:
                if link not in revision.references: break
                origin = revision
            selected_access(actor, case, {'issue_id': issue_id, 'reference': link,
                'revision_id': origin.pk if origin else None, 'observation_id': link.get('observation_id')})
