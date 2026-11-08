"""Explicit synthetic unsigned internal applicability, never operational owner defaults."""
from uuid import uuid4
from tests.helpers import setup_case,roles,rev
from tests.document_helpers import artifact
from apps.core.services import add_evidence
from apps.policy.signature_validators import COMPONENT,SCHEMA
from apps.pmo import signature_exemptions as native
from apps.pmo.services import prepare_baseline,decide

def policy(f,scope=None,requirement='not_applicable'):
    return artifact(f['a'],f['c'],COMPONENT,SCHEMA,{
        'parties':[],'methods':[],'assurance':'human_verified_reference_only',
        'unchanged_prd_signature_reuse':'unconfigured','applicability':'internal_project',
        'signature_requirement':requirement,'scope_evidence_id':(scope or f['scope']).pk,
        'allow_synthetic':True},f['e']['policy_decision'])

def capture(f):
    previous=native.latest(f['c'])
    return native.record_exemption(f['a'],f['c'].pk,f['prd'].pk,'Explicit synthetic owner-backed internal scope only',str(uuid4()),rev(f['c']),previous.pk if previous else None)

def fixture(username='impact801'):
    a,c=setup_case(username=username,synthetic=True)
    if not c.synthetic:raise AssertionError('Explicit synthetic case required')
    e={k:add_evidence(a,c.pk,k,'Synthetic '+k,'synthetic:impact801') for k in ('requirements','engineering_estimate','security_estimate','plan','costing','sow','policy_decision')}
    roles(a,c,e['policy_decision']);prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(c))
    for role in ('PM','Head of PMO','CEO','PMO Lead'):decide(a,c.pk,role,rev(c))
    f={'a':a,'c':c,'e':e,'prd':add_evidence(a,c.pk,'prd','Synthetic internal PRD','synthetic:impact801'),
        'scope':add_evidence(a,c.pk,'internal_project_scope','Synthetic owner decision: internal unit only','synthetic:impact801')}
    f['policy']=policy(f);f['row']=capture(f)
    from apps.pmo.models import Baseline,CommercialSignaturePacket,CommercialSignatureUse,CommercialSignatureReaffirmation,BaselineAdoption,RFPCase,ClientResponse
    from apps.documents.models import PublicationReceipt
    from apps.core.models import Audit
    if Baseline.objects.get(case=c).signed_id is not None:raise AssertionError('Unsigned fixture required')
    if (CommercialSignaturePacket.objects.filter(case=c).exists() or CommercialSignatureUse.objects.filter(packet__case=c).exists()
        or CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists() or BaselineAdoption.objects.filter(revision__dossier__case=c).exists()
        or RFPCase.objects.filter(case=c).exists() or ClientResponse.objects.filter(revision__dossier__case=c).exists()
        or PublicationReceipt.objects.filter(publication__version__document__case=c).exists()
        or Audit.objects.filter(case=c,action='baseline.signed').exists()):
        raise AssertionError('No signing/adoption/publication/conversion/repair in unsigned fixture')
    return f
