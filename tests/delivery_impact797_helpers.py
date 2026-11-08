"""Explicit synthetic baseline replacement fixture; no post-sign roster repair."""
from tests.test_delivery import DeliveryFixture
from tests.helpers import setup_case,project_evidence,rev,activate
from tests.test_commercial_changes import change_roles,DEFINITION
from tests.signature_helpers import packet_for
from tests.document_helpers import artifact
from apps.pmo.services import prepare_baseline,decide,sign_baseline
from apps.pmo.gates import register_candidate
from apps.pmo.delivery import open_dossier
from apps.documents.controlled import register_template
from apps.policy.services import register_reference

class ReplacementDeliveryFixture(DeliveryFixture):
    def setup_delivery(self):
        self.actor,self.case=setup_case(username='impact797-replacement')
        a,c=self.actor,self.case;self.e=project_evidence(a,c);e=self.e
        # Complete original authority roster BEFORE any baseline decision/signature.
        change_roles(a,c,e['policy_decision'])
        prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(c))
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
        packet_for(a,c,e);sign_baseline(a,c.pk,e['signature'].pk,rev(c))
        self.candidate=register_candidate(a,c.pk,'impact797-build',e['requirements'].pk,rev(c))
        self.d=open_dossier(a,c.pk,self.candidate.pk,e['plan'].pk,'Synthetic original scope',rev(c))
        self.t=register_template(a,c.pk,'Delivery artifact',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'internal_review_required':False,'audience_fields':{x:['executive_summary','scope','risks','status','next_steps','timeline','dependencies'] for x in ['client','internal']}},e['policy_decision'].pk,rev(c))
        self.commercial_template=register_template(a,c.pk,'Replacement SOW',DEFINITION,e['policy_decision'].pk,rev(c))
        refs=[]
        for audience in ['client','internal']:
            r=register_reference(a,c.pk,'impact797-recipient:'+audience,'schema:psl/document-recipient/v1',{'audience':audience,'user_id':a.pk},e['policy_decision'].pk);refs.append(r.ref)
        activate(a,c,'D11.recipient_grant_refs',refs,e['policy_decision'])
        artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
            {'template_ids':[self.t.pk,self.commercial_template.pk],'repository':'internal-versioned','retention_days':30},e['policy_decision'])


def replace_baseline(f):
    from apps.core.services import add_evidence
    from apps.pmo.changes import log_change,assess_change,decide_change,authorize_change
    from tests.test_commercial_changes import impact_fixture,proposal,approvals,delivered,capture_response,adopt_signed
    a,c=f.actor,f.case
    source=add_evidence(a,c.pk,'change_request','Synthetic independent baseline replacement','synthetic:impact797')
    change=log_change(a,c.pk,'CR-IMPACT797','Normal','Delivery','Owner-authored synthetic replacement','New exact baseline',source.pk,rev(c))
    for team in ['Engineering','QA','Infra','Security']:
        assess_change(a,c.pk,change.pk,team,True,True,True,source.pk,'Explicit synthetic team assessment',rev(c),**impact_fixture(team,True))
    for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
        decide_change(a,c.pk,change.pk,role,'approve',source.pk,'Explicit synthetic owner approval',rev(c))
    revised=dict(f.e)
    for kind in ['plan','costing','sow','signature']:
        revised[kind]=add_evidence(a,c.pk,kind,'Synthetic replacement '+kind,'synthetic:impact797')
    commercial=proposal(a,c,revised,source);approvals(a,c,commercial)
    receipt=delivered(a,c,commercial,f.commercial_template)
    response=capture_response(a,c.pk,commercial.pk,receipt.pk,'signed',revised['signature'].pk,'Synthetic exact signed response',rev(c))
    packet=packet_for(a,c,revised,commercial)
    authorize_change(a,c.pk,change.pk,commercial.pk,rev(c))
    adoption=adopt_signed(a,c.pk,commercial.pk,response.pk,rev(c))
    return adoption,packet
