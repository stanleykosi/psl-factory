"""Evidenced client replies, reviewed corrections and a source-owned release successor."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters.go_live_replies import SuppliedGoLiveReplyAdapter
from apps.core.evidence_access import public_evidence
from apps.core.models import Audit
from apps.core.services import bump, event, lock_case
from apps.documents.models import PublicationReceipt
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import active_component, decision_authority, reference_values
from . import delivery, issues
from .models import GoLiveClientReply, GoLiveReplyIssue, GoLiveRemediation, DeliveryDocumentBinding


COMPONENT = 'D11.adapter_configuration_refs'


def rules(case):
    configuration = active_component(COMPONENT, case)
    matches = [row for row in reference_values(configuration) if row.get('kind') == 'go_live_reply']
    if len(matches) != 1:
        raise ValidationError('owner_needed: Review the rules for client changes, declines and recorded corrections.')
    return configuration, matches[0]


def readable(actor, case):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('A current active account is required.')
    require(actor, case, 'case.read')
    require(actor, case, 'delivery.read')


def locked(actor, case_id, expected):
    case = lock_case(actor, case_id, 'delivery.manage', expected)
    list(get_user_model().objects.select_for_update().filter(pk=actor.pk))
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    readable(actor, case)
    return case


def proof(case, pk):
    source = public_evidence(case.evidence.filter(pk=pk)).defer('body').first()
    if not source or source.kind not in ['client_feedback', 'go_live_response', 'go_live_response_correction']:
        raise ValidationError('Select this project client response or correction evidence.')
    return source


def resolved_issue(case,issue):
    state=issue.current
    resolution=issue.states.filter(status='Resolved',fix_id=state.fix_id,resolved_at=state.resolved_at).order_by('pk').first()
    if not resolution or not state.fix_id or not Audit.objects.filter(case=case,actor=resolution.actor,action='issue.updated',
        data={'issue':issue.pk,'state':resolution.pk,'status':'Resolved'}).exists():
        raise ValidationError('The issue needs its actual native resolution and fix provenance.')
    require(resolution.actor,case,'issue.work')
    issues.owned(case,resolution.owner_id)
    issues.subject(case,resolution.fix_id)
    return resolution


def head(reply):
    return GoLiveClientReply.objects.filter(receipt_id=reply.receipt_id).order_by('-number').first()


def current_heads(dossier):
    rows = list(GoLiveClientReply.objects.filter(dossier=dossier).order_by('receipt_id', '-number')
        .distinct('receipt_id').select_related('dossier__case','receipt__publication__version__deliverydocumentbinding', 'actor', 'evidence')
        .defer('evidence__body','receipt__payload','receipt__publication__version__payload','receipt__publication__version__fields',
               'receipt__publication__version__source_manifest','receipt__publication__version__baseline_manifest',
               'receipt__publication__version__template_current_manifest')[:101])
    if len(rows) > 100:
        raise ValidationError('Review the client-response history with the process owner before preparing another report.')
    return rows


def current_authority(reply, value):
    case = reply.dossier.case
    readable(reply.actor, case)
    require(reply.actor, case, 'delivery.manage')
    roles = value['correction_roles'] if reply.outcome == 'withdrawn' else value['recording_roles']
    if reply.role not in roles or reply.channel not in value['channels']:
        raise ValidationError('The recorded client response needs current configured authority and channel coverage.')
    if reply.authority != decision_authority(reply.actor, case, reply.role):
        raise ValidationError('Client response authority changed. Record an evidenced current correction.')
    if not Audit.objects.filter(case=case, actor=reply.actor, action='delivery.client_reply_recorded',
        data={'reply_id':reply.pk,'receipt_id':reply.receipt_id,'evidence_id':reply.evidence_id,
              'sha256':reply.evidence.sha256,'outcome':reply.outcome}).exists():
        raise ValidationError('The client response needs its native recording provenance.')
    proof(case, reply.evidence_id)


def effect(dossier, data):
    """Bind current client responses to each prepared report."""
    rows = current_heads(dossier)
    if not rows:
        return None
    configuration, value = rules(dossier.case)
    contexts = []
    for reply in rows:
        current_authority(reply, value)
        if reply.outcome == 'withdrawn':
            continue
        if reply.outcome == 'declined':
            raise ValidationError('The client declined this release. Resolve the issue and review a new release candidate.')
        if value['changes_handling'] != 'reviewed_document_successor':
            raise ValidationError('owner_needed: The client changes need the configured owner review before a successor report.')
        if reply.receipt.publication.version.deliverydocumentbinding.data == data:
            raise ValidationError('The client requested changes. Select corrected source versions before preparing the next report.')
        contexts.append({'reply_id':reply.pk,'receipt_id':reply.receipt_id,'evidence_id':reply.evidence_id,
                         'sha256':reply.evidence.sha256})
    return {'configuration':configuration.pk,'replies':sorted(contexts,key=lambda row:row['reply_id'])}


@transaction.atomic
def record(actor, case_id, dossier_id, receipt_id, previous_id, outcome, party, responded_at,
           channel, evidence_id, note, role, attested, expected):
    if any(type(pk) is not int or pk<1 for pk in [dossier_id,receipt_id,evidence_id,expected]) or previous_id is not None and (type(previous_id) is not int or previous_id<1):
        raise ValidationError('Use the exact current report, receipt, evidence and response references.')
    case = locked(actor, case_id, expected)
    dossier = delivery.dossier_for(case, dossier_id, current=False)
    delivery.ensure_open(dossier)
    facts = SuppliedGoLiveReplyAdapter.validate(party, responded_at, channel, note, attested)
    if outcome not in ['changes_requested', 'declined', 'withdrawn']:
        raise ValidationError('Choose the evidenced client response or a reviewed correction.')
    receipt = PublicationReceipt.objects.filter(pk=receipt_id, publication__version__deliverydocumentbinding__dossier=dossier,
        publication__version__deliverydocumentbinding__purpose='go_live', publication__version__audience='client')
    receipt = receipt.select_related('publication__version__document').first()
    if not receipt or receipt.payload_sha256 != receipt.publication.version.payload_sha256 or receipt.payload != receipt.publication.version.payload:
        raise ValidationError('Select an exact delivered client report and matching receipt.')
    previous = GoLiveClientReply.objects.filter(receipt=receipt).order_by('-number').first()
    if (previous.pk if previous else None) != previous_id:
        raise ValidationError('The client response changed. Review its current recorded version.')
    source = proof(case, evidence_id)
    if previous and previous.evidence_id == source.pk:
        raise ValidationError('A response successor needs new supporting evidence.')
    try:
        _, value = rules(case)
    except ValidationError:
        value = None
    if outcome == 'withdrawn':
        if not previous or value is None or role not in value['correction_roles']:
            raise ValidationError('A recorded response and configured correction authority are required.')
        if not value['allow_recorder_correction'] and previous.actor_id == actor.pk:
            raise PermissionDenied('A separate authorised reviewer must correct this response.')
    else:
        from .delivery_closure import latest_go_live
        if latest_go_live(dossier, False):
            raise ValidationError('Go-live sign-off is already recorded. Record later problems as an issue.')
        if receipt.publication.version.document.current_id != receipt.publication.version_id:
            raise ValidationError('Select the current delivered report before recording the client response.')
        if previous and previous.outcome=='declined' and outcome!='declined':
            raise ValidationError('A recorded decline needs reviewed correction before a different response can replace it.')
        if role not in (value['recording_roles'] if value else ['PM']):
            raise PermissionDenied('A current configured response recorder is required.')
    if value and channel not in value['channels']:
        raise ValidationError('This response channel needs reviewed coverage in the client-response rules.')
    authority = decision_authority(actor, case, role)
    reply = GoLiveClientReply.objects.create(dossier=dossier, receipt=receipt, previous=previous,
        number=previous.number+1 if previous else 1, outcome=outcome, evidence=source,
        actor=actor, role=role, authority=authority, **facts)
    event(actor, case, 'delivery.client_reply_recorded', reply_id=reply.pk, receipt_id=receipt.pk,
          evidence_id=source.pk, sha256=source.sha256, outcome=outcome)
    bump(case)
    return reply


@transaction.atomic
def log_problem(actor, case_id, reply_id, owner_id, title, next_action, note, expected,existing_issue_id=None):
    case = locked(actor, case_id, expected)
    reply = GoLiveClientReply.objects.select_related('dossier').filter(pk=reply_id, dossier__case=case).first()
    if not reply or head(reply).pk != reply.pk or reply.outcome != 'declined':
        raise ValidationError('Select the current recorded client decline.')
    old = GoLiveReplyIssue.objects.filter(reply=reply).first()
    if old:
        require(actor, case, 'issue.read')
        if existing_issue_id is not None and existing_issue_id != old.issue_id:
            raise ValidationError('This response already has a linked issue. Review that issue before changing the relation.')
        return old
    require(actor, case, 'issue.manage')
    previous=GoLiveReplyIssue.objects.filter(reply__receipt_id=reply.receipt_id).order_by('-pk').first()
    if existing_issue_id is not None or previous:
        require(actor,case,'issue.read')
        from .models import Issue
        item=Issue.objects.filter(case=case,pk=existing_issue_id or previous.issue_id,current__isnull=False).first()
        if not item or not note.strip():raise ValidationError('Select the existing project issue and record the relation rationale.')
        bump(case)
    else:
        issue = issues.log_issue(actor, case.pk, 'GO-LIVE-REPLY-'+str(reply.pk), title, 'Client go-live decline',
            owner_id, next_action, reply.evidence_id, note, case.revision)
        item=issue.issue
    link = GoLiveReplyIssue.objects.create(reply=reply, issue=item, actor=actor)
    event(actor, case, 'delivery.client_decline_issue', reply_id=reply.pk, issue_id=item.pk)
    return link


@transaction.atomic
def create_candidate(actor, case_id, reply_id, reference, requirements_id, note, expected):
    case=locked(actor,case_id,expected)
    _,value=rules(case)
    if value['decline_handling']!='new_release_candidate':
        raise ValidationError('The recorded decline needs its configured owner review before a new candidate.')
    reply=GoLiveClientReply.objects.select_related('dossier').filter(pk=reply_id,dossier__case=case,outcome='declined').first()
    if not reply or head(reply).pk!=reply.pk:raise ValidationError('Select the current client decline.')
    current_authority(reply,value)
    if not public_evidence(case.evidence.filter(pk=requirements_id,kind='requirements')).exists():
        raise ValidationError('Select this project requirements source for the new candidate.')
    from .gates import register_candidate
    candidate=register_candidate(actor,case.pk,reference,requirements_id,case.revision)
    case.refresh_from_db()
    dossier=delivery.open_dossier(actor,case.pk,candidate.pk,reply.evidence_id,note,case.revision,declined_reply_id=reply.pk)
    return dossier


@transaction.atomic
def remediate(actor, case_id, reply_id, previous_id, destination_id, role, evidence_id, note, expected):
    case = locked(actor, case_id, expected)
    configuration, value = rules(case)
    if value['decline_handling'] != 'new_release_candidate' or role not in value['remediation_roles']:
        raise ValidationError('Review the configured authority and decline handling before starting another release.')
    if not note.strip() or len(note) > 4000:
        raise ValidationError('Record the reason for the reviewed release handoff.')
    reply = GoLiveClientReply.objects.select_related('dossier').filter(pk=reply_id, dossier__case=case, outcome='declined').first()
    if not reply or head(reply).pk != reply.pk:
        raise ValidationError('Select the current client decline.')
    current_authority(reply, value)
    require(actor, case, 'issue.read')
    link = GoLiveReplyIssue.objects.select_related('issue__current').filter(reply=reply).first()
    if not link or link.issue.current.status not in value['issue_states_for_new_release'] or not link.issue.current.fix_id:
        raise ValidationError('Resolve the linked issue with actual fix evidence before the release handoff.')
    if not link.issue.current.resolved_at or link.issue.current.resolved_at<reply.responded_at:
        raise ValidationError('Review fix evidence that follows the actual client decline.')
    if not Audit.objects.filter(case=case,actor=link.actor,action='delivery.client_decline_issue',
        data={'reply_id':reply.pk,'issue_id':link.issue_id}).exists():
        raise ValidationError('The decline issue needs its native source relation.')
    state = issues.current_issue(case, link.issue_id, link.issue.current_id).current
    resolved_issue(case,link.issue)
    destination = delivery.dossier_for(case, destination_id)
    if destination.pk == reply.dossier_id or destination.candidate_id == reply.dossier.candidate_id:
        raise ValidationError('Choose a distinct release candidate with its own native gates.')
    if not destination.declined_reply_id or head(destination.declined_reply).pk != reply.pk:
        raise ValidationError('Choose the new candidate recorded against this exact client decline.')
    delivery.ensure_open(destination)
    if delivery.latest(destination, 'release_outcome', False):
        raise ValidationError('Choose a candidate awaiting its new release gates and actual release.')
    previous = GoLiveRemediation.objects.filter(reply=reply).order_by('-number').first()
    if (previous.pk if previous else None) != previous_id:
        raise ValidationError('The release handoff changed. Review its current version.')
    authority = decision_authority(actor, case, role)
    result = GoLiveRemediation.objects.create(reply=reply, previous=previous,
        number=previous.number+1 if previous else 1, destination=destination, issue_state=state,
        configuration=configuration, evidence=proof(case, evidence_id), role=role,
        authority=authority, note=note.strip(), actor=actor)
    event(actor, case, 'delivery.client_decline_handoff', reply_id=reply.pk, review_id=result.pk,
          destination_id=destination.pk, deployment_authorized=False)
    bump(case)
    return result


def release_handoff(dossier):
    if dossier.declined_reply_id is None:return None
    marker=Audit.objects.filter(case=dossier.case,action='delivery.client_decline_candidate',data__dossier_id=dossier.pk).order_by('-pk').first()
    if not marker:raise ValidationError('Review the new candidate source relation before release readiness.')
    expected={'reply_id','candidate_id','dossier_id','deployment_authorized'}
    if set(marker.data)!=expected or marker.data['deployment_authorized'] is not False or marker.data['candidate_id']!=dossier.candidate_id:
        raise ValidationError('Review the new candidate source relation.')
    original=GoLiveClientReply.objects.select_related('dossier').filter(pk=dossier.declined_reply_id,dossier__case=dossier.case).first()
    if not original or marker.data['reply_id']!=original.pk or original.outcome!='declined' or marker.actor_id!=dossier.actor_id:
        raise ValidationError('The new candidate needs its exact recorded decline source.')
    current=head(original)
    configuration,value=rules(dossier.case)
    current_authority(current,value)
    if current.outcome=='withdrawn':
        return {'corrected_response':current.pk,'configuration':configuration.pk}
    if current.outcome!='declined' or value['decline_handling']!='new_release_candidate':
        raise ValidationError('Review the current client response before release readiness.')
    review=GoLiveRemediation.objects.filter(reply=current,destination=dossier).order_by('-number').first()
    if not review or review.configuration_id!=configuration.pk or review.role not in value['remediation_roles']:
        raise ValidationError('The declined release needs its reviewed issue-fix handoff before release readiness.')
    readable(review.actor,dossier.case)
    require(review.actor,dossier.case,'delivery.manage')
    require(review.actor,dossier.case,'issue.read')
    if review.authority!=decision_authority(review.actor,dossier.case,review.role):
        raise ValidationError('The release handoff review authority changed.')
    if not Audit.objects.filter(case=dossier.case,actor=review.actor,action='delivery.client_decline_handoff',
        data={'reply_id':review.reply_id,'review_id':review.pk,'destination_id':review.destination_id,'deployment_authorized':False}).exists():
        raise ValidationError('The release handoff needs its native review provenance.')
    link=GoLiveReplyIssue.objects.select_related('issue__current').filter(reply=current).first()
    if not link or link.issue.current_id!=review.issue_state_id or link.issue.current.status not in value['issue_states_for_new_release']:
        raise ValidationError('The linked issue or its reviewed resolution changed.')
    state=link.issue.current
    if not state.resolved_at or state.resolved_at<current.responded_at:
        raise ValidationError('Review fix evidence that follows the actual client decline.')
    resolution=resolved_issue(dossier.case,link.issue)
    proof(dossier.case,review.evidence_id)
    return {'reply_id':current.pk,'review_id':review.pk,'issue_state_id':state.pk,
            'resolution_id':resolution.pk,'configuration':configuration.pk}


def projection(actor, dossier):
    readable(actor,dossier.case)
    rows=current_heads(dossier)
    allowed=set(public_evidence(dossier.case.evidence.filter(pk__in=[row.evidence_id for row in rows])).values_list('pk',flat=True))
    items=[]
    for reply in rows:
        items.append({'id':reply.pk,'outcome':reply.outcome,'number':reply.number,
            'party':reply.party if reply.evidence_id in allowed else 'Restricted response source',
            'responded_at':reply.responded_at.isoformat(),'channel':reply.channel,
            'note':reply.note if reply.evidence_id in allowed else None,'source_available':reply.evidence_id in allowed,
            'evidence_id':reply.evidence_id,'receipt_id':reply.receipt_id,'version_id':reply.receipt.publication.version_id,
            'version_number':reply.receipt.publication.version.number,'recorder':reply.actor.get_full_name() or reply.actor.username})
    try:
        configuration,value=rules(dossier.case)
        finding=''
    except (ValidationError,PermissionDenied):
        configuration,value=None,None
        finding='Review the handling rules before continuing from a recorded client response.'
    try:
        require(actor,dossier.case,'issue.read')
        links=list(GoLiveReplyIssue.objects.filter(reply__dossier=dossier).select_related('issue__current').order_by('pk')[:100])
    except PermissionDenied:
        links=[]
    reviews=list(GoLiveRemediation.objects.filter(reply__dossier=dossier).order_by('reply_id','-number').distinct('reply_id')[:100])
    destinations=[]
    active_declines={row.pk:row for row in rows if row.outcome=='declined'}
    for review in reviews:
        try:
            if not value or review.reply_id not in active_declines or configuration.pk!=review.configuration_id or review.role not in value['remediation_roles']:
                continue
            current_authority(active_declines[review.reply_id],value)
            readable(review.actor,dossier.case)
            require(review.actor,dossier.case,'delivery.manage')
            if review.authority!=decision_authority(review.actor,dossier.case,review.role):continue
            link=next((link for link in links if link.reply_id==review.reply_id),None)
            if not link or link.issue.current_id!=review.issue_state_id:continue
            if link.issue.current.status not in value['issue_states_for_new_release']:continue
            if not Audit.objects.filter(case=dossier.case,actor=review.actor,action='delivery.client_decline_handoff',
                data={'reply_id':review.reply_id,'review_id':review.pk,'destination_id':review.destination_id,'deployment_authorized':False}).exists():continue
            resolved_issue(dossier.case,link.issue)
            proof(dossier.case,review.evidence_id)
            delivery.dossier_for(dossier.case,review.destination_id)
            destinations.append({'review_id':review.pk,'dossier_id':review.destination_id,'reply_id':review.reply_id})
        except (ValidationError,PermissionDenied):
            continue
    return {'items':items,'configuration_id':configuration.pk if configuration else None,
            'rules':value,'finding':finding,'issues':links,'destinations':destinations}
