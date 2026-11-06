"""Reviewed query/operation registry. No arbitrary model, SQL or job-payload access."""
from django.apps import apps
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from apps.identity.services import require
from apps.identity.models import Grant
from apps.core.evidence_access import public_evidence

ROUTES={
 'financefollowup':('workflows.FinanceFollowupDispatch','packet__mapping__plan__case','finance.read','reconstitution.native_finance.transport','native-finance'),
 'handoff':('workflows.Outbox','case','workflow.read','workflow.operate','case'),
 'publication':('documents.PublicationJob','publication__version__document__case','document.read','document.operate','documents'),
 'invoice':('finance.InvoiceJob','invoice__case','finance.read','finance.invoice.operate','finance/settlement'),
 'engineering':('baas.CorrectiveJob','request__case','baas.read','baas.corrective.operate','baas/reconciliation'),
 'partner':('baas.PartnerFinanceJob','report__record__case','partner.read','partner.finance.operate','partners'),
 'approval':('pmo.ApprovalRouteJob','request__case','approval.read','approval.operate','approvals'),
 'supportresponse':('baas.SupportResponseJob','packet__case','support.response.read','support.response.operate','support/responses'),
 'supportchannel':('baas.SupportChannelCheck','claim__case','support.channel.read','support.channel.operate','support/channels'),
 'ledgerdata':('agents.EvidenceExtraction','projection__case','ledger.agent.read','agent.data.operate','finance/ledger/agents'),
 'protection':('workflows.RecoveryJob','plan__case','ops.read','ops.operate','operations')}
SAFE_KINDS=['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','completion']

PRIVATE_FAMILY='supportresponse'
PRIVATE_FAMILIES={'supportresponse','supportchannel','ledgerdata'}
PRIVATE_GRANTS=['case.read','support.read','support.private.read','agent.data.read','agent.data.source','support.response.read']
def family_access(a,c,family):
    if family=='ledgerdata':
        from apps.finance.ledger_agents import source_access
        source_access(a,c)
    elif family in PRIVATE_FAMILIES:
        if c.kind!='support':raise PermissionDenied('Private response requires Support scope')
        if family=='supportchannel':
            from apps.baas.support_channel import access
        else:
            from apps.baas.support_release import access
        access(a,c)
    else:require(a,c,ROUTES[family][2])
def can_private(a,c,family=PRIVATE_FAMILY):
    try:family_access(a,c,family);return family=='ledgerdata' or c.kind=='support'
    except PermissionDenied:return False

def lock_scope(case_id):
    # Finance evidence may include resolved claims from other cases. Acquire its
    # ordered participant/principal locks before any shared operator case lock.
    from apps.agents.boundary import lock_scope as finance_scope
    finance_scope(case_id)

def source_query(c,family):
    label,path,*_=ROUTES[family]
    q=apps.get_model(label).objects.filter(**{path:c})
    if family=='ledgerdata':
        from apps.finance.ledger_agent_models import LedgerProjection
        q=q.filter(projection_id__in=LedgerProjection.objects.filter(case=c).values('projection_id'),projection__process_id='F01',projection__evidence__kind='agent_private_ledger')
    return q

def job_access(a,c,family,j):
    family_access(a,c,family)
    if family=='financefollowup':
        from .followup_transport import access
        access(a,j.packet,'read')
    if family=='publication':
        from apps.finance.accepted_documents import binding,access
        b=binding(j.publication.version)
        if b:access(a,b)
    if family=='protection':
        from .private_readiness_operations import plan_access
        plan_access(a,j.plan)
    if family=='ledgerdata':
        from apps.finance.ledger_agents import projection_access
        projection_access(a,j.projection)

def jobs(a,c,limit=500,include_private=True):
    rows=[];omitted=[];grants={'case.read'}
    for family,(label,path,read,action,url) in ROUTES.items():
        if family in PRIVATE_FAMILIES and (not include_private or family!='ledgerdata' and c.kind!='support'):continue
        if family=='ledgerdata' and not source_query(c,family).exists():continue
        try:family_access(a,c,family)
        except PermissionDenied:omitted.append(family);continue
        if family in PRIVATE_FAMILIES and family!='ledgerdata':grants.update(PRIVATE_GRANTS if family==PRIVATE_FAMILY else [x for x in PRIVATE_GRANTS if x!='support.response.read']+['support.channel.read'])
        if family=='ledgerdata':grants.update(['finance.read','ledger.read','ledger.private.read','ledger.agent.read','agent.data.read','agent.data.source'])
        grants.add(read);query=source_query(c,family).order_by('pk')
        for j in query[:limit+1]:
            if family=='protection' and not include_private:
                from .private_readiness_operations import has_private
                if has_private(j.plan):continue
            if family=='publication' and not include_private:
                from apps.finance.accepted_documents import binding
                if binding(j.publication.version):continue
            try:job_access(a,c,family,j)
            except PermissionDenied:
                if family not in omitted:omitted.append(family)
                continue
            source_url=f'/cases/{c.pk}/'+('' if url=='case' else url+'/')
            if family=='publication':
                from apps.finance.accepted_documents import binding
                if binding(j.publication.version):source_url=f'/cases/{c.pk}/finance/accepted-documents/'
            rows.append({'family':family,'id':j.pk,'status':j.status,'fence':j.fence,'attempts':j.attempts,'lease_until':j.lease_until.isoformat() if j.status=='leased' and j.lease_until else None,'lease_expired':bool(j.status=='leased' and j.lease_until and j.lease_until<=timezone.now()),'source_url':source_url})
            if len(rows)>limit:raise ValidationError('Inventory budget exceeded; narrow the scoped case inventory')
    return rows,omitted,sorted(grants)

def bundle(a,c,max_records,private_packet_ids=(),protection_packet_ids=()):
    rows,omitted,grants=jobs(a,c,max_records)
    # Protection jobs are diagnostics, not restored business work. Do not create a self-referential export.
    rows=[{k:v for k,v in r.items() if k not in ['lease_expired','source_url']} for r in rows if r['family']!='protection']
    evidence=list(public_evidence(c.evidence.filter(kind__in=SAFE_KINDS)).order_by('pk').values('id','kind','version','sha256')[:max_records+1])
    if len(evidence)+len(rows)>max_records:raise ValidationError('Metadata export exceeds configured record budget')
    manifest={'schema':'portable_case_metadata_v1','case_id':str(c.pk),'evidence':evidence,'jobs':rows,'source_grants':grants,'omitted_families':omitted,'evidence_bodies_included':False,'credentials_included':False,'business_jobs_reenacted':False}
    from .private_readiness_operations import add
    from .accepted_protection_operations import add as add_protection
    return add_protection(a,c,add(a,c,manifest,private_packet_ids,max_records),protection_packet_ids,max_records)

def readable_manifest(a,c,m):
    if m['case_id']!=str(c.pk):raise ValidationError('Exact case metadata bundle required')
    from .private_readiness_operations import historical
    historical(a,c,m)
    for action in m['source_grants']:require(a,c,action)
    for family in {r['family'] for r in m['jobs']} & PRIVATE_FAMILIES:family_access(a,c,family)
    for row in m['jobs']:
        if row['family']=='financefollowup':
            j=source_query(c,'financefollowup').filter(pk=row['id']).first()
            if not j:raise PermissionDenied('Exact Finance intake dispatch source required')
            job_access(a,c,'financefollowup',j)
        if row['family']=='protection':
            j=source_query(c,'protection').filter(pk=row['id']).first()
            if not j:raise PermissionDenied('Exact private protection job required')
            job_access(a,c,'protection',j)
        if row['family']=='publication':
            j=source_query(c,'publication').filter(pk=row['id']).first()
            if not j:raise PermissionDenied('Exact publication source required')
            job_access(a,c,'publication',j)
        if row['family']=='ledgerdata':
            j=source_query(c,'ledgerdata').filter(pk=row['id']).first()
            if not j:raise PermissionDenied('Exact native Finance extraction source required')
            job_access(a,c,'ledgerdata',j)

def recover_source(a,c,family,pk,operation,reason):
    if family not in ROUTES:raise ValidationError('Reviewed workflow family required')
    label,path,read,action,url=ROUTES[family];family_access(a,c,family);require(a,c,action)
    j=source_query(c,family).filter(pk=pk).first()
    if not j:raise ValidationError('Exact case job required')
    job_access(a,c,family,j)
    # Generic recovery cannot exploit a source service that allows cancellation while uncertain.
    if j.status=='unknown':raise ValidationError('Unknown effects need source worker receipt lookup; no force retry/cancel')
    if family=='financefollowup':
        from .followup_transport import retry
        return retry(a,c.pk,pk,operation,reason)
    if family=='ledgerdata':
        from apps.agents.boundary_delivery import operate
        return operate(a,c.pk,pk,operation)
    if family=='handoff':
        from .operator_recovery import operate_handoff
        return operate_handoff(a,c,pk,operation,reason)
    if family=='publication':
        from apps.documents.delivery import operate_publication
        return operate_publication(a,c.pk,pk,operation,reason,None)
    if family=='invoice':
        from apps.finance.invoice_delivery import operate
    elif family=='engineering':
        from apps.baas.corrective_delivery import operate
    elif family=='partner':
        from apps.baas.partner_delivery import operate
    elif family=='supportchannel':
        from apps.baas.support_channel_delivery import operate
    elif family==PRIVATE_FAMILY:
        from apps.baas.support_release import operate
    elif family=='approval':
        from apps.pmo.approval_routing import operate
    else:
        from .operator_delivery import operate
    return operate(a,c.pk,pk,operation,reason,None)
