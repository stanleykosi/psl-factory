"""Initial synthetic signed adoption; excludes emergency and post-sign repair."""
import inspect
from tests import test_commercial_changes as commercial
from tests.signature_helpers import packet_for
from tests.document_helpers import artifact
from tests.helpers import rev
from apps.pmo import recoveries

RULE={'roles':['PMO Lead'],'scope':'authority_only','original_times':'preserve','financial_release_controls':'independent'}
def policy(f):
    return artifact(f['a'],f['c'],'D05.revision_invalidation_rules','schema:psl/commercial-revision/v2',
        {'unchanged_subject_reuse_roles':[],'changed_cost_requires_full_chain':True,
         'historical_authority':{'signed_adoption':RULE}},f['e']['policy_decision'])
def fixture(username='impact798'):
    from adapters.publications import InternalPublicationAdapter
    from apps.documents.delivery import run_publication_once
    from adapters.signed_baselines import InternalSignedBaselineAdapter
    from apps.pmo.models import RFPCase,ChangeAuthorization,EmergencyOutcome,AuthorityRecoveryDecision,AuthorityRecoveryRecord,CommercialSignatureReaffirmation
    if InternalPublicationAdapter.deliver.__module__!='adapters.publications' or 'adapter=adapter or InternalPublicationAdapter()' not in inspect.getsource(run_publication_once):raise AssertionError('Canonical local publication required')
    if InternalSignedBaselineAdapter.deliver.__module__!='adapters.signed_baselines':raise AssertionError('Canonical local signed intake required')
    a,c,e,t=commercial.fixture(existing=False,username=username)
    v=commercial.proposal(a,c,e);commercial.approvals(a,c,v)
    receipt=commercial.delivered(a,c,v,t)
    response=commercial.capture_response(a,c.pk,v.pk,receipt.pk,'signed',e['signature'].pk,'Synthetic exact signed adoption',rev(c))
    packet_for(a,c,e,v);adoption=commercial.adopt_signed(a,c.pk,v.pk,response.pk,rev(c))
    f={'a':a,'c':c,'e':e,'adoption':adoption};f['policy']=policy(f)
    f['request']=recoveries.request_recovery(a,c.pk,'signed_adoption',adoption.pk,e['policy_decision'].pk,'Synthetic request only, not recovered authority',rev(c))
    if RFPCase.objects.filter(case=c).exists() or ChangeAuthorization.objects.filter(commercial__dossier__case=c).exists() or EmergencyOutcome.objects.filter(profile__version__change__case=c).exists():raise AssertionError('Initial project adoption fixture scope exceeded')
    if AuthorityRecoveryDecision.objects.filter(request__case=c).exists() or AuthorityRecoveryRecord.objects.filter(request__case=c).exists():raise AssertionError('No recovery decisions or finalization in request fixture')
    if CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists():raise AssertionError('No signature reaffirmation in initial fixture')
    return f
