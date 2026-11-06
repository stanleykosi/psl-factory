from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy.services import register_reference
from apps.policy.ledger_validators import PUBLICATION
from apps.documents.controlled import register_template
from apps.finance import accepted_documents as d
from .finance_acceptance_helpers import fixture,handoff,validate,af13_reviews,decide
from .ledger_helpers import policy
from .document_helpers import artifact
from .helpers import activate,rev

def ready(prefix='accepted-publication',source_fixture=None):
 f=source_fixture or fixture(prefix);handoff(f);validate(f);af13_reviews(f);decide(f,'accept');a,c=f['actor'],f['case']
 f['template']=register_template(a,c.pk,'Accepted scoped metadata',{'document_type':d.TYPE,'required_fields':['executive_summary'],'internal_review_required':True,'audience_fields':{'internal':['executive_summary'],'client':['executive_summary']}},f['e'].pk,rev(c))
 r=get_user_model().objects.create_user(username=prefix+'-audience');Grant.objects.create(case=c,user=r,action='document.receive:internal');f['audience_user']=r
 ref=register_reference(a,c.pk,'accepted-metadata-recipient','schema:psl/document-recipient/v1',{'audience':'internal','user_id':r.pk},f['e'].pk);activate(a,c,'D11.recipient_grant_refs',[ref.ref],f['e'])
 artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[f['template'].pk],'repository':'internal-versioned','retention_days':30},f['e'])
 f['publication_rules']={'handoff_ids':[f['handoff'].pk],'template_ids':[f['template'].pk],'fields':['handoff','package','acceptance','classification'],'audience':'internal','recipient_ids':[r.pk],'reviewer_id':f['recipient'].pk,'publisher_id':f['acceptor'].pk,'independent_review':True,'review_ttl_seconds':600}
 f['publication_policy']=policy(f,PUBLICATION,f['publication_rules']);return f

def draft(f,**kw):return d.draft(f['actor'],f['case'].pk,f['handoff'].pk,f['template'].pk,'internal',**kw)
def reviewed(f):
 v=draft(f);d.review(f['recipient'],f['case'].pk,v.pk,'approve','Independent exact metadata approval');return v
