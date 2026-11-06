import json
from django.conf import settings
from apps.baas import support_agent as native,support_release as d
from apps.policy.support_release_validators import COMPONENT
from .support_agent_helpers import fixture,extracted
from .support_helpers import policy

def ready(prefix='response-release',configured=True):
 f=fixture(prefix);r=extracted(f);draft=native.reuse(f['actor'],f['case'].pk,r.pk,'response-draft');native.review(f['reviewer'],f['case'].pk,draft.pk,'approve');f['draft']=draft
 f['release_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/support-release.json').read_text(encoding='utf-8'))['rules'],releaser_id=f['reviewer'].pk,recipient_id=f['actor'].pk)
 if configured:f['release_policy']=policy(f,COMPONENT,f['release_rules'])
 return f

def packet(f,key='response'):
 return d.prepare(f['actor'],f['case'].pk,f['draft'].pk,key)
def release(f,p=None):
 p=p or packet(f);d.decide(f['reviewer'],f['case'].pk,p.pk,'release');return d.Job.objects.get(packet=p)
