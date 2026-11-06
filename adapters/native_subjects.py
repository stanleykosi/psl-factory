"""Exact pre-reservation business subjects for native validation; no expected verdicts."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import digest
from apps.core.evidence_access import public_evidence


def fingerprint(case,family,identity):
    return digest({'format':'psl.native-subject/v1','case':str(case.pk),'family':family,'identity':identity})


def invoice_identity(invoice,correction=None):
    return {'invoice':invoice.pk,'sha256':invoice.sha256,'correction':correction.pk if correction else None,'correction_source_sha256':correction.evidence.sha256 if correction else None}


def observed(case,family,j):
    if family=='handoff':value={'name':j.milestone.name,'evidence':j.milestone.evidence_id,'evidence_sha256':j.milestone.evidence.sha256}
    elif family=='publication':value={'version':j.publication.version_id,'sha256':j.publication.version.payload_sha256}
    elif family=='invoice':
        from apps.finance.models import InvoiceCorrection
        correction=None
        if j.kind in ['adjust','adjust_deliver']:
            correction=InvoiceCorrection.objects.filter(pk=j.intent.get('correction'),case=case,issue__invoice=j.invoice).first()
            if not correction:raise ValidationError('Exact native correction source required')
        value=invoice_identity(j.invoice,correction)
    elif family=='engineering':value={'reference':j.request.reference,'run':j.request.run_id,'operation_key':j.request.operation_key,'evidence':j.request.evidence_id,'evidence_sha256':j.request.evidence.sha256}
    elif family=='partner':value={'record':j.report.record_id,'evidence_sha256':j.report.record.evidence.sha256}
    elif family=='approval':value={'request':j.request_id,'sha256':digest(j.request.subject)}
    elif family=='supportresponse':value={'packet':j.packet_id,'sha256':j.packet.sha256}
    elif family=='supportchannel':value={'claim':j.claim_id,'sha256':j.claim.sha256}
    elif family=='ledgerdata':value={'projection':j.projection_id,'sha256':j.projection.sha256}
    elif family=='financefollowup':value={'packet':j.packet_id,'sha256':j.packet.sha256}
    else:raise ValidationError('Registered native subject required')
    return fingerprint(case,family,value)


def planned(actor,case,family,source_id,reference='',operation='',related_id=None,effect_key=''):
    from adapters.validation_native import FAMILIES
    from apps.workflows.operator_inventory import family_access
    from apps.identity.services import require
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current subject reader required')
    require(actor,case,'case.read')
    if family not in FAMILIES or type(source_id) is not int or source_id<1:raise ValidationError('Exact registered native source required')
    family_access(actor,case,family)
    if family!='engineering' and (related_id is not None or effect_key):raise ValidationError('Related run and effect key apply only to Engineering requests')
    if family not in ['handoff','engineering'] and reference:raise ValidationError('Planned name/reference applies only to milestones and Engineering requests')
    if family!='invoice' and operation:raise ValidationError('Invoice effect applies only to invoice sources')
    def exact(model,path='case',**extra):
        row=model.objects.filter(pk=source_id,**{path:case},**extra).first()
        if not row:raise ValidationError('Exact same-case pre-reservation source required')
        return row
    if family in ['handoff','engineering']:
        from apps.core.models import Evidence
        kind='completion' if family=='handoff' else 'corrective_request'
        row=public_evidence(Evidence.objects.filter(case=case,pk=source_id,kind=kind)).first()
        if not row or not isinstance(reference,str) or not reference.strip() or len(reference)>200:raise ValidationError('Actual public source evidence and bounded planned name/reference required')
        value={('name' if family=='handoff' else 'reference'):reference,'evidence':row.pk,'evidence_sha256':row.sha256}
        if family=='engineering':
            from apps.baas.models import CorrectiveRequest
            from apps.documents.contracts import validate
            from adapters.forecast import KEY
            validate(KEY,reference);validate(KEY,effect_key)
            model=CorrectiveRequest._meta.get_field('run').related_model
            if type(related_id) is not int or not model.objects.filter(case=case,pk=related_id).exists():raise ValidationError('Exact planned reconciliation run required')
            value.update(run=related_id,operation_key=effect_key)
    elif family=='publication':
        from apps.documents.models import Version
        row=exact(Version,'document__case')
        from apps.finance.accepted_documents import binding,access
        b=binding(row)
        if b:access(actor,b)
        from apps.finance.documents import binding_for
        if binding_for(row):require(actor,case,'finance.read')
        value={'version':row.pk,'sha256':row.payload_sha256}
    elif family=='invoice':
        from apps.finance.models import Invoice,InvoiceCorrection
        if operation not in ['issue','deliver','adjust','adjust_deliver']:raise ValidationError('Exact invoice effect required')
        row=exact(InvoiceCorrection if operation in ['adjust','adjust_deliver'] else Invoice)
        value=invoice_identity(row.issue.invoice,row) if isinstance(row,InvoiceCorrection) else invoice_identity(row)
    elif family=='partner':
        from apps.baas.models import PartnerRecord
        row=exact(PartnerRecord);value={'record':row.pk,'evidence_sha256':row.evidence.sha256}
    elif family=='approval':
        from apps.pmo.models import ApprovalRequest
        row=exact(ApprovalRequest);value={'request':row.pk,'sha256':digest(row.subject)}
    elif family=='supportresponse':
        from apps.baas.support_release_models import SupportResponsePacket
        row=exact(SupportResponsePacket);value={'packet':row.pk,'sha256':row.sha256}
    elif family=='supportchannel':
        from apps.baas.support_channel_models import SupportChannelClaim
        row=exact(SupportChannelClaim);value={'claim':row.pk,'sha256':row.sha256}
    elif family=='ledgerdata':
        from apps.agents.boundary_models import EvidenceProjection
        from apps.finance.ledger_agents import projection_access
        row=exact(EvidenceProjection);projection_access(actor,row);value={'projection':row.pk,'sha256':row.sha256}
    else:
        from apps.workflows.native_finance_models import NativeFinancePacket
        from apps.workflows.followup_transport import access
        row=exact(NativeFinancePacket,'mapping__plan__case');access(actor,row,'read');value={'packet':row.pk,'sha256':row.sha256}
    return {'format':'psl.native-subject/v1','family':family,'subject_sha256':fingerprint(case,family,value),
        'source_id':source_id,'expected_verdict_supplied':False,'effects_scheduled':False}
