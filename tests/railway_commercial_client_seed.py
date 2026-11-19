"""Additive SAMPLE preparation; no client response, signature check or adoption seeded."""
import os
from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.agents.upload_views import upload_file
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo.models import CommercialCase, ClientResponse
from tests.test_commercial_changes import fixture, proposal, approvals, delivered
from tests.signature_helpers import contract as signature_contract

TENANT = 'design-commercial-client-walkthrough'
REWORK_TENANT = 'design-commercial-client-rework'


@transaction.atomic
def prepare():
    if os.getenv('PSL_COMMERCIAL_CLIENT_FIXTURE') != '1':
        raise RuntimeError('Explicit SAMPLE commercial-client fixture guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    old = Case.objects.filter(tenant=TENANT).first()
    if old:
        if not old.synthetic:
            raise RuntimeError('Unexpected operational workspace')
        current = CommercialCase.objects.get(case=old).current
        return {'already_prepared': True, 'case': str(old.pk), 'proposal': current.pk,
                'responses': ClientResponse.objects.filter(revision=current).count(), 'no_existing_records_reset': True}
    case = Case.objects.create(tenant=TENANT, title='SAMPLE statement-of-work client response', kind='project', synthetic=True)
    Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in ACTIONS])
    _, _, sources, template = fixture(context=(actor, case))
    revision = proposal(actor, case, sources)
    approvals(actor, case, revision)
    receipt = delivered(actor, case, revision, template, scoped=True)
    policy = signature_contract(actor, case, sources['policy_decision'])
    prd = add_evidence(actor, case.pk, 'prd', 'SAMPLE exact product requirements for this isolated exercise.', 'synthetic:commercial-product-requirements')
    prd_proof = add_evidence(actor, case.pk, 'signature',
        'SAMPLE separate product-requirements signature reference. Fictional test evidence, not an actual client signature.',
        'synthetic:commercial-product-signature')
    version = receipt.publication.version
    line = ('SAMPLE Synthetic client representative signed ' + version.document.title + ' version ' + str(version.number)
            + '. This fictional exercise supplies no real client signature, policy or business approval. '
            'Product requirements retain their separate signature proof and Finance has independent billing controls.')
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p></w:body></w:document>')
    proof = upload_file(actor, case, SimpleUploadedFile('SAMPLE-statement-of-work-signature.docx', stream.getvalue()))
    return {'case': str(case.pk), 'proposal': revision.pk, 'receipt': receipt.pk, 'document_version': version.pk,
            'proof': proof.pk, 'product_requirements': prd.pk, 'product_signature_source': prd_proof.pk,
            'sample_signature_policy': policy.pk,
            'native_setup': 'Explicitly simulated commercial approvals, document review and internal recipient delivery; not browser or real owner decisions',
            'client_response_recorded': False, 'signature_packet_recorded': False,
            'baseline_adopted': False, 'invoice_created': False, 'model_request_sent': False}


@transaction.atomic
def prepare_rework():
    """Create one isolated case for change, correction and recovery UI checks."""
    if (os.getenv('PSL_COMMERCIAL_CLIENT_FIXTURE') != '1'
            or os.getenv('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance'):
        raise RuntimeError('Explicit SAMPLE fixture guard and exact Railway test environment required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    title = 'SAMPLE client-requested revision'
    case, created = Case.objects.get_or_create(tenant=REWORK_TENANT, kind='project', title=title, synthetic=True)
    if not created:
        dossier = CommercialCase.objects.get(case=case)
        return {'case': str(case.pk), 'current_proposal': dossier.current_id, 'preserved_existing': True}
    Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
    _, _, sources, template = fixture(context=(actor, case))
    revision = proposal(actor, case, sources)
    approvals(actor, case, revision)
    receipt = delivered(actor, case, revision, template, scoped=True)
    proofs = {}
    for outcome, message in {
        'changes': 'The SAMPLE client asks for a clearer description of the existing delivery. The sample asks for no new price or dates.',
        'decline': 'The SAMPLE client declines the exact first version. This is fictional exercise evidence with no operating authority.',
    }.items():
        row = upload_file(actor, case, SimpleUploadedFile(f'SAMPLE-response-{outcome}.txt', message.encode()))
        proofs[outcome] = row.pk
    return {'case': str(case.pk), 'current_proposal': revision.pk, 'prior_delivery_receipt': receipt.pk,
            'proofs': proofs, 'confirmed_sources': revision.sources, 'template': template.pk,
            'initial_approvals_review_and_internal_delivery': 'synthetic setup',
            'responses_or_model_requests_seeded': False}
