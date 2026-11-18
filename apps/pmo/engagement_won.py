"""Carry exact submitted facts into a draft; native Planning decisions remain fresh."""
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from apps.core.models import Evidence,Audit
from apps.core.workbench import active
from apps.core.evidence_access import public_evidence
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.services import require
from adapters.won_planning import PROTOCOL,checked,INPUTS
from . import engagement,planning
from .models import RFPDisposition
from .rfp_outcomes import historical_submission,assert_public_submission_sources
from .rfp import public_terms_for
from .rfp_pricing import read as price,QUOTE


def read(actor,case):
    active(actor)
    for action in ['case.read','engagement.read','planning.read']:require(actor,case,action)
    capture=engagement.current_capture(case)
    if capture.data['route']!='A':return None
    # Check current reader authority before loading any proposal payload.
    require(actor,case,'rfp.read')
    for action in ['case.read','engagement.read','engagement.capture']:require(capture.actor,case,action)
    disposition=RFPDisposition.objects.select_related('rfp','outcome__submission__response__commercial').filter(
        pk=capture.data['rfp_disposition'],rfp__case=case,kind='route_a',outcome__result='won').first()
    if disposition is None:raise ValidationError('An actual same-project winning proposal is required.')
    submission=disposition.outcome.submission
    # Validate the current classification of all cited documents from metadata,
    # before historical verification loads its necessary response/plan-draft bodies.
    assert_public_submission_sources(case,submission)
    response=historical_submission(case,submission)
    expected={'response':response.pk,'submission':submission.pk,'outcome':disposition.outcome_id,'case':str(case.pk),
              'route':'A','baseline_imported':False,'sources':response.snapshot,'commercial_sources':response.commercial.sources}
    if disposition.snapshot!=expected:raise ValidationError('The winning proposal conversion and retained sources differ.')
    terms=public_terms_for(response,metadata_only=True)
    ids={'prd_id':response.commercial.sources['requirements'],'scope_id':response.commercial.sources['plan'],
         'engineering_estimate_id':response.snapshot['inputs']['Engineering']['evidence'],
         'security_estimate_id':response.snapshot['inputs']['Security']['evidence']}
    exact={*ids.values(),response.evidence_id,terms.pk}
    records={item['id']:item for item in public_evidence(Evidence.objects.filter(case=case,pk__in=exact)).values(
        'id','kind','source','version','sha256')}
    if set(records)!=exact:raise ValidationError('The supplied public proposal sources require domain review.')
    quote=price(terms,QUOTE)
    return checked({'format':PROTOCOL,'capture':capture.pk,'disposition':disposition.pk,'submission':submission.pk,
        'response':response.pk,'reference':disposition.rfp.reference,'response_number':response.number,
        'inputs':{key:records[pk] for key,pk in ids.items()},'response_source':records[response.evidence_id],
        'terms_source':records[terms.pk],'quoted_price':None if quote is None else {
            'amount':format(quote['amount'],'f'),'currency':quote['currency'],'basis':quote['basis']},
        'requirements':len(response.matrix),'addressed':sum(row['disposition']=='addressed' for row in response.matrix),
        'historical_authority_reused':False,'planning_approval_granted':False})


def projection(actor,case):
    try:
        for action in ['case.read','engagement.read','planning.read']:require(actor,case,action)
    except PermissionDenied:return None
    capture=engagement.latest(case,'capture')
    if capture is None or capture.data['route']!='A':return None
    try:return read(actor,case)
    except PermissionDenied:return {'held':True,'finding':'Winning-proposal sources need current proposal access.'}
    except ValidationError:return {'held':True,'finding':'Winning-proposal evidence needs source review before reuse.'}


@transaction.atomic
def adopt(actor,case_id,predecessor=None):
    case=planning.locked(actor,case_id,'coordinate')
    original=planning.latest(case,'packet')
    if (original.pk if original else None)!=predecessor:raise ValidationError('Planning inputs changed; review the current version first.')
    selected=read(actor,case)
    if selected is None:raise ValidationError('Only a recorded winning proposal supplies these inputs.')
    if original:
        _,value=planning.packet(case,original.pk)
        payload=dict(value['payload'])
    else:
        from apps.workflows.factory_engagement import empty_planning_payload
        payload=empty_planning_payload()
    # These are supplied document references, not an accepted PRD or scope baseline.
    # Preserve human contacts/questions and require explicit reconciliation for conflicts.
    for field in INPUTS:
        supplied=selected['inputs'][field]['id']
        if payload[field] is not None and payload[field]!=supplied:
            raise ValidationError('Existing Planning sources differ from the winning proposal. Review the difference; no input was replaced.')
        payload[field]=supplied
    if original and payload==value['payload']:packet=original
    else:packet=planning.capture(actor,case.pk,payload,predecessor)
    marker={'packet':packet.pk,'capture':selected['capture'],'disposition':selected['disposition'],
            'manifest_sha256':digest(selected),'historical_authority_reused':False,'planning_approval_granted':False}
    if not Audit.objects.filter(case=case,actor=actor,action='planning.won_sources_adopted',data=marker).exists():
        event(actor,case,'planning.won_sources_adopted',**marker)
    return packet
