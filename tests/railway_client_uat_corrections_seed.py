"""Append fictional correction proofs only; never alter a response or decision."""
import json
import os
from io import BytesIO
from zipfile import ZipFile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from adapters import case_uploads,upload_text
from apps.core.models import Case
from apps.agents.models import CaseUpload
from apps.agents.upload_views import upload_file
from apps.pmo import client_uat as domain


@transaction.atomic
def prepare():
    if os.environ.get('PSL_CLIENT_UAT_CORRECTION_FIXTURE')!='1':raise RuntimeError('Explicit SAMPLE correction-file fixture guard required')
    case=Case.objects.get(tenant='design-client-uat-walkthrough',synthetic=True)
    actor=get_user_model().objects.get(username='psl-agent-trial',is_active=True,is_staff=False,is_superuser=False)
    domain.witness(actor,case)
    statements={
        'changes':'SAMPLE Client Witness asked for changes to delivery-build at 14:15 WAT on 19 November 2026. The SAMPLE totals label needs correction before approval.',
        'rejected':'SAMPLE Client Witness rejected delivery-build at 14:20 WAT on 19 November 2026. This is a fictional client response for the SAMPLE testing exercise.',
        'workaround':'SAMPLE Client Witness approved delivery-build at 14:25 WAT on 19 November 2026 with this exact workaround: Use SAMPLE offline reconciliation until the separate remediation is reviewed.',
    }
    result=[]
    for label,text in statements.items():
        text+=' This entire source is fictional test data, not an actual client approval or operating policy.'
        name='SAMPLE-client-testing-'+label+'.docx'
        old=CaseUpload.objects.filter(case=case,actor=actor,name=name).order_by('pk').first()
        if old:
            if upload_text.extract(old.name,case_uploads.read(old))!=text:raise RuntimeError('Existing sample file differs; preserve it and investigate')
            row=old
        else:
            output=BytesIO()
            with ZipFile(output,'w') as archive:
                archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
                archive.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
                archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')
            row=upload_file(actor,case,SimpleUploadedFile(name,output.getvalue()))
        result.append({'kind':label,'upload':row.pk,'sha256':row.sha256})
    return {'case':str(case.pk),'files':result,'source_files_only':True,'responses_reviews_bindings_or_policies_changed':False,'model_requests_created':False}


print('PSL_CLIENT_UAT_CORRECTION_FILES='+json.dumps(prepare()))
