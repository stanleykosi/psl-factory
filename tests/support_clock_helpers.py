import json
from django.conf import settings
from .support_channel_helpers import fixture as channel_fixture,reviewed,gateway,verify,output
from .support_helpers import policy,evidence
from apps.policy.support_channel_validators import CORRECTIONS
from apps.baas import support_clock_corrections as d,support_channel as channel

def fixture(prefix='clock-successors',configured=True):
 f=channel_fixture(prefix)
 f['correction_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/support-channel.json').read_text(encoding='utf-8'))['corrections'],proposer_id=f['actor'].pk,reviewer_id=f['reviewer'].pk,source_author_id=f['actor'].pk)
 for kind in ['agent_private_channel_successor','agent_private_clock_correction','agent_private_clock_review']:f['e'][kind]=evidence(f,kind)
 if configured:f['correction_policy']=policy(f,CORRECTIONS,f['correction_rules'])
 return f

def attest(f,remote):
 r=reviewed(f,remote);f['event']=channel.attest(f['actor'],f['case'].pk,r.pk,f['e']['support_response'].pk);return r

def propose(f,mode='revalidate',receipt=None,key='correction',predecessor=None):
 return d.propose(f['actor'],f['case'].pk,mode,receipt.pk if receipt else None,key,predecessor,f['e']['agent_private_clock_correction'].pk,'Explicit synthetic human correction reason')

def confirm(f,r,verdict='confirm'):
 return d.review(f['reviewer'],f['case'].pk,r.pk,verdict,f['e']['agent_private_clock_review'].pk)

def successor(f,version='v2',key='source-v2',old=None):
 r=d.successor(f['actor'],f['case'].pk,(old or f['claim']).pk,key,version,f['e']['agent_private_channel_successor'].pk);f['claim']=r;return r
