"""New isolated SAMPLE setup only. Never records a client response or review."""
import json
import os
from io import BytesIO
from zipfile import ZipFile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core import client_contacts
from apps.identity.models import Grant
from apps.identity.actions import ACTIONS
from apps.agents.upload_views import upload_file
from apps.policy.client_uat_validators import COMPONENT,SCHEMA_REF
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev
from tests.document_helpers import artifact

TENANT='design-client-uat-walkthrough'


@transaction.atomic
def prepare():
    if os.environ.get('PSL_CLIENT_UAT_FIXTURE')!='1':raise RuntimeError('Explicit SAMPLE client testing fixture guard required')
    actor=get_user_model().objects.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    case=Case.objects.filter(tenant=TENANT).first()
    if case:
        if not case.synthetic:raise RuntimeError('Unexpected operational workspace')
        return {'already_prepared':True,'case':str(case.pk),'no_existing_records_reset':True}
    case=Case.objects.create(tenant=TENANT,title='SAMPLE client testing and release evidence',kind='project',synthetic=True)
    Grant.objects.bulk_create([Grant(case=case,user=actor,action=action) for action in ACTIONS])
    f=DeliveryFixture();f.setup_delivery(context=(actor,case));f.plan();f.gates([k for k in ['qa_exit','uat_product_manager','uat_product_owner','engineering_go']])
    from apps.policy.operator_drafts import draft_operator_policy
    from apps.policy.services import transition
    from apps.workflows.factory_delivery import start
    from apps.workflows.factory_progress import set_progress
    from pathlib import Path
    execution=json.loads(Path('fixtures/factory-delivery.json').read_text());execution.pop('classification')
    profile=draft_operator_policy(actor,case.pk,'OPS.factory_delivery_execution',execution,f.e['policy_decision'].pk,timezone.now())
    transition(actor,profile.pk,'validated');transition(actor,profile.pk,'active')
    work=start(actor,case.pk,'SAMPLE-CLIENT-UAT',f.d.pk,'SAMPLE client testing release',rev(case))
    set_progress(actor,work.pk,work.revision,True)
    contact=client_contacts.save(actor,case,'project',{'customer':'','client_name':'SAMPLE Client','name':'SAMPLE Client Witness',
        'email':'sample-client@example.invalid','role':'SAMPLE client representative','evidence':f.e['policy_decision'],'revision':rev(case)})
    rules={'format':'psl.client-uat-rules/v1','human_only':True,'qualification_mode':'reviewed_human_attestation_v1',
        'reviewer_ids':[actor.pk],'reviewer_role':'PM','independent_review':False,'agent_review_required':True,
        'exact_mentions_required':True,'proof_formats':['txt','pdf','docx','xlsx'],'workaround_mode':'explicit_client_approved_scope_v1',
        'assurance':'human_witnessed_not_external_authentication','financial_controls':'independent'}
    cfg=artifact(actor,case,COMPONENT,SCHEMA_REF,rules,f.e['policy_decision'])
    stream=BytesIO()
    with ZipFile(stream,'w') as archive:
        archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>SAMPLE Client Witness approved delivery-build for the SAMPLE testing exercise. This is fictional proof, not an actual client approval.</w:t></w:r></w:p></w:body></w:document>')
    proof=upload_file(actor,case,SimpleUploadedFile('SAMPLE-client-testing-proof.docx',stream.getvalue()))
    return {'case':str(case.pk),'dossier':f.d.pk,'work':work.pk,'candidate':f.candidate.reference,'contact':contact.pk,'proof':proof.pk,'policy':cfg.pk,
        'source_setup':'Explicitly simulated baseline, planning and other owner gates; not browser or operational approval evidence',
        'client_request_recorded':False,'client_response_recorded':False,'proof_review_recorded':False,'gate_bound':False,
        'operational_owner_values_adopted':False}


print('PSL_CLIENT_UAT_FIXTURE='+json.dumps(prepare()))
