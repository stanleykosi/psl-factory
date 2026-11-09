from uuid import uuid4
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference
from apps.documents.controlled import register_template, create_version, request_review, review_version, reserve_publication
from .helpers import setup_case, roles, activate, rev

DEFINITION={'document_type':'status_report','required_fields':['executive_summary','status'],
 'audience_fields':{'client':['executive_summary','scope','timeline','risks','dependencies','status','next_steps'],'internal':['executive_summary','status','internal_notes']}}


def artifact(actor,case,component,schema,content,evidence):
    r=register_reference(actor,case.pk,'fixture:'+str(uuid4()),schema,content,evidence.pk)
    value={'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return activate(actor,case,component,value,evidence)


def publication_fixture():
    actor,case=setup_case()
    owner=add_evidence(actor,case.pk,'policy_decision','Synthetic owner-approved document configuration','synthetic:owner')
    source=add_evidence(actor,case.pk,'completion','Delivery is progressing. Internal incident trace is private.','synthetic:progress')
    roles(actor,case,owner)
    template=register_template(actor,case.pk,'Status report',DEFINITION,owner.pk,rev(case))
    recipient=get_user_model().objects.create_user(username='recipient')
    Grant.objects.create(case=case,user=recipient,action='document.receive:client')
    r=register_reference(actor,case.pk,'client:fixture','schema:psl/document-recipient/v1',{'audience':'client','user_id':recipient.pk},owner.pk)
    recipients=activate(actor,case,'D11.recipient_grant_refs',[r.ref],owner)
    storage=artifact(actor,case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
        {'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner)
    return actor,case,owner,source,template,recipient,recipients,storage


def fields(source):
    return {'executive_summary':{'text':'Delivery is progressing.','evidence_ids':[source.pk]},
        'status':{'text':'In progress','evidence_ids':[source.pk]},
        **{key:{'text':'Unknown: not established by the selected local progress source.','evidence_ids':[source.pk]} for key in ['scope','timeline','risks','dependencies']},
        'internal_notes':{'text':'PRIVATE TRACE DO NOT SHARE','evidence_ids':[source.pk]}}


def drafted(actor,case,template,source,document_id=None):
    return create_version(actor,case.pk,template.pk,'Delivery report','client',fields(source),rev(case),document_id)


def approved(actor,case,template,source):
    v=drafted(actor,case,template,source)
    request_review(actor,case.pk,v.pk,rev(case))
    review_version(actor,case.pk,v.pk,'approve','Reviewed exact client projection',rev(case))
    return v


def reserved(actor,case,template,source):
    v=approved(actor,case,template,source)
    return reserve_publication(actor,case.pk,v.pk,rev(case))
