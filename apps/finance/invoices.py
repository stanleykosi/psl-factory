from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.pmo.services import subject
from .analysis import note,review_authority
from .billing import exact,digest,ensure_current
from .models import BillingPreparation,Invoice,InvoiceReview,InvoiceJob,InvoiceIssue


def obligation(prep):
    cov=prep.coverage
    identity={'case':str(prep.case_id),'customer':cov.customer,'contract':cov.contract,'kind':prep.kind}
    identity['usage']=prep.usage_id if prep.kind=='usage' else None
    return digest(identity)

def current(invoice):
    require(invoice.actor,invoice.case,'finance.invoice.draft');ensure_current(invoice.preparation)
    if Invoice.objects.filter(case=invoice.case,obligation_key=invoice.obligation_key,pk__gt=invoice.pk).exists():raise ValidationError('A newer invoice draft exists for this obligation')
    if invoice.sha256!=digest(invoice.payload):raise ValidationError('Invoice artifact hash mismatch')

def adapter_config(case):
    configs=[active_component(k,case) for k in ['D08.adapter_contract_ref','D08.duplicate_correction_rules']]
    return {c.component:c.pk for c in configs},reference_values(configs[0])[0],reference_values(configs[1])[0]

@transaction.atomic
def draft(actor,case_id,preparation_id,reference,due_date,expected):
    case=lock_case(actor,case_id,'finance.invoice.draft',expected);require(actor,case,'finance.read')
    prep=exact(case,BillingPreparation,preparation_id);ensure_current(prep)
    from adapters.billing_usage import KEY
    if not KEY.fullmatch(reference):raise ValidationError('Use a bounded explicit invoice reference')
    key=obligation(prep)
    if InvoiceIssue.objects.filter(obligation_key=key).exists():raise ValidationError('Obligation already issued; retain it and use an authorised correction workflow')
    if Invoice.objects.filter(case=case,reference=reference).exclude(obligation_key=key).exists():raise ValidationError('Invoice reference belongs to another obligation')
    previous=Invoice.objects.filter(case=case,reference=reference).order_by('-version').first()
    if due_date is not None and not isinstance(due_date,date):raise ValidationError('Explicit due date must be a date')
    if prep.kind!='usage':
        if prep.result['amount_basis']!='gross_including_tax':raise ValidationError('Stage payable tax basis unresolved; configure explicit gross stage terms before invoicing')
        if due_date!=date.fromisoformat(prep.result['due_date']):raise ValidationError('Stage invoice due date must match exact configured terms')
    amount=Decimal(prep.result['total'])
    if amount<=0:raise ValidationError('Only a positive known payable amount can generate this invoice document')
    cov=prep.coverage
    payload={'document_type':'invoice','reference':reference,'version':previous.version+1 if previous else 1,'customer':cov.customer,'contract':cov.contract,
        'preparation':prep.pk,'preparation_key':prep.operation_key,'source_basis':cov.amount_basis,'amount_basis':'gross_including_tax',
        'currency':prep.result['currency'],'amount':format(amount,'f'),'due_date':due_date.isoformat() if due_date else None,'lines':prep.result['lines'],
        'usage_completeness':prep.result['usage_completeness'],'coverage_completeness':cov.completeness}
    record=Invoice.objects.create(case=case,preparation=prep,obligation_key=key,reference=reference,version=payload['version'],due_date=due_date,
        amount=amount,currency=prep.result['currency'],amount_basis='gross_including_tax',payload=payload,sha256=digest(payload),actor=actor)
    event(actor,case,'invoice.drafted',invoice=record.pk,obligation=key);bump(case);return record

@transaction.atomic
def review(actor,case_id,invoice_id,role,verdict,evidence_id,reason,expected,*,delegated=False):
    case=lock_case(actor,case_id,'finance.invoice.review',expected);i=exact(case,Invoice,invoice_id);current(i);note(reason)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose a configured invoice review decision')
    authority=review_authority(actor,case,'invoice',role,verdict,i.actor_id,delegated=delegated,invoice=i)
    from apps.workflows.factory_routing import for_invoice
    for_invoice(i,actor,delegated=delegated)
    record=InvoiceReview.objects.create(invoice=i,role=role,verdict=verdict,authority=authority,publication_packet=review_packet(i),evidence=subject(case,evidence_id,'invoice_review'),note=reason,actor=actor)
    event(actor,case,'invoice.reviewed',invoice=i.pk,review=record.pk,verdict=verdict);bump(case);return record

def reviewed(invoice):
    current(invoice);r=InvoiceReview.objects.filter(invoice=invoice).order_by('-pk').first()
    if not r or r.verdict!='approve':raise ValidationError('Exact current invoice requires configured human Finance approval')
    if not isinstance(r.authority,dict):raise ValidationError('Typed recorded invoice authority required')
    delegated='D05.delegation_rules' in r.authority
    from apps.workflows.factory_routing import for_invoice
    for_invoice(invoice,r.actor,delegated=delegated)
    if r.publication_packet!=review_packet(invoice):raise ValidationError('Publication target, destination, policy or evidence changed; fresh exact-packet review required')
    require(r.actor,invoice.case,'finance.invoice.review')
    authority=review_authority(r.actor,invoice.case,'invoice',r.role,r.verdict,invoice.actor_id,delegated=delegated,invoice=invoice)
    strip=lambda v:{k:x for k,x in v.items() if k!='D05.decision_action_matrix'}
    if strip(authority)!=strip(r.authority):raise ValidationError('Invoice review authority changed')
    return r


def review_packet(invoice):
    """One exact packet for native UI, agents and dispatch; old empty packets need fresh review."""
    bindings={k:resolve(k,invoice.case) for k in ['D08.adapter_contract_ref','D08.duplicate_correction_rules']}
    policies={k:r.configuration.pk if r.configuration is not None else None for k,r in bindings.items()}
    adapter=reference_values(bindings['D08.adapter_contract_ref'].configuration)[0] if bindings['D08.adapter_contract_ref'].status=='ACTIVE' else None
    packet={'schema':'invoice-publication-review/v1','invoice':invoice.pk,'version':invoice.version,
        'payload_hash':invoice.sha256,'amount':invoice.payload['amount'],'currency':invoice.currency,
        'recipient_id':adapter['recipient_id'] if adapter else None,'adapter_policies':policies,
        'adapter_readiness':{k:r.status for k,r in bindings.items()},
        'preparation':invoice.preparation_id,'sources':invoice.preparation.snapshot}
    from apps.workflows.models import FactoryWork
    work=FactoryWork.objects.filter(invoice=invoice).select_related('policy').first()
    if work and work.policy_id:
        from apps.core.evidence_access import public_evidence
        from apps.core.models import Evidence
        required=reference_values(work.policy)[0]['required_evidence_kinds'];latest={}
        for e in public_evidence(Evidence.objects.filter(case=invoice.case,kind__in=required)).order_by('kind','-version'):
            latest.setdefault(e.kind,{'id':e.pk,'version':e.version,'sha256':e.sha256})
        if set(latest)!=set(required):raise ValidationError('Required factory source evidence is missing from publication packet')
        packet['factory_sources']={'work':work.pk,'profile':work.policy_id,'evidence':latest}
        from apps.workflows.factory_routing import binding
        packet['factory_responsibility']=binding(work)
    return packet

def factory_binding(actor,invoice,work_id):
    from apps.workflows import factory
    from apps.workflows.models import FactoryWork
    if type(work_id) is not int or work_id<1:raise ValidationError('Exact factory work identity required')
    work=FactoryWork.objects.select_related('case').filter(pk=work_id,case=invoice.case,invoice=invoice).first()
    if not work:raise ValidationError('Factory execution scope differs from the invoice target')
    factory.access(actor,work.case,'factory.execute');config,value=factory.profile(work)
    if work.cancel_requested or work.status in ['cancelled','followup_needed','verified']:raise ValidationError('Factory execution is stopped; no new invoice dispatch is permitted')
    if value['executor_id']!=actor.pk:raise PermissionDenied('Current separately configured invoice executor required')
    packet=review_packet(invoice)
    refs=packet.get('factory_sources',{}).get('evidence',{})
    from apps.core.models import Evidence
    from django.utils import timezone
    observed=list(Evidence.objects.filter(case=work.case,pk__in=[row['id'] for row in refs.values()]))
    if set(refs)!=set(value['required_evidence_kinds']) or len(observed)!=len(refs):raise ValidationError('Current factory source evidence is required before a new send')
    now=timezone.now()
    if any(not 0<=(now-record.created_at).total_seconds()<=value['max_age_seconds'] for record in observed):
        raise ValidationError('Stale factory source evidence prevents a new send; original receipt lookup remains available')
    return {'schema':'factory-invoice-execution/v1','work':work.pk,'profile':config.pk,'executor':actor.pk}

def legacy_factory_work_id(job):
    """Infer only recorded coordinator intent, never an association or model assertion."""
    from apps.workflows.models import FactoryAttempt
    ids=list(FactoryAttempt.objects.filter(activity__work__case=job.invoice.case,activity__work__business_key=job.invoice.obligation_key,activity__kind__in=['ACT11','ACT12'],phase='observed')
        .filter(Q(result__job=job.pk)|Q(result__dispatch_job=job.pk)).values_list('activity__work_id',flat=True).distinct()[:2])
    if len(ids)>1:raise ValidationError('Conflicting historical factory scope requires operator investigation')
    return ids[0] if ids else None

def intent(actor,invoice,kind,role,correction_id=None,factory_work_id=None):
    if kind in ['adjust','adjust_deliver']:
        if factory_work_id is not None:raise ValidationError('This factory definition does not authorise correction dispatch; use the native correction workflow')
        from .corrections import effect_intent
        return effect_intent(actor,invoice,kind,role,correction_id)
    policies,adapter,identity=adapter_config(invoice.case)
    if kind=='issue':
        r=reviewed(invoice)
        if role not in adapter['issuer_roles']:raise PermissionDenied('Issuer role is not configured')
        auth=decision_authority(actor,invoice.case,role)
        if adapter['require_due_date'] and invoice.due_date is None:raise ValidationError('Invoice due terms are not configured')
        if invoice.preparation.kind=='usage' and invoice.payload['usage_completeness']!='complete' and not adapter['allow_partial_usage']:raise ValidationError('Configured invoice policy does not allow incomplete usage coverage')
        value={'policies':policies,'adapter':adapter,'identity':identity,'review':r.pk,'issuer_role':role,'issuer_authority':auth,'sha256':invoice.sha256}
        from .billing_evidence import release_context
        context=release_context(invoice,kind)
        if context is not None:value['d03_release']=context
        if factory_work_id is not None:value['factory_execution']=factory_binding(actor,invoice,factory_work_id)
        return value
    if kind!='deliver':raise ValidationError('Unknown invoice effect')
    reviewed(invoice)
    if not InvoiceIssue.objects.filter(invoice=invoice).exists():raise ValidationError('Proven invoice issuance is required before delivery')
    from django.contrib.auth import get_user_model
    recipient=get_user_model().objects.get(pk=adapter['recipient_id']);require(recipient,invoice.case,'finance.invoice.receive')
    value={'policies':policies,'adapter':adapter,'identity':identity,'recipient':recipient.pk,'sha256':invoice.sha256,'delivery_hash':digest(delivery_payload(invoice))}
    from .billing_evidence import release_context
    context=release_context(invoice,kind)
    if context is not None:value['d03_release']=context
    if factory_work_id is not None:value['factory_execution']=factory_binding(actor,invoice,factory_work_id)
    return value

def guard_reserve(actor,case,invoice_id,kind,role,factory_work_id=None):
    if kind not in ['issue','deliver']:raise ValidationError('Typed ordinary invoice effect required')
    require(actor,case,'finance.invoice.issue' if kind=='issue' else 'finance.invoice.deliver')
    i=exact(case,Invoice,invoice_id)
    # A never-claimed pending draft remains protected by the worker's current-version
    # check. Preserve native draft revisioning; unresolved attempted effects need recovery.
    if kind=='issue' and InvoiceJob.objects.filter(invoice__case=case,invoice__obligation_key=i.obligation_key,
            status__in=['unknown','leased','held']).exclude(invoice=i).exists():
        raise ValidationError('Another invoice for this obligation has unresolved native work; reconcile its original effect before a new issuance')
    job=InvoiceJob.objects.filter(invoice=i,kind=kind).order_by('-generation').first()
    if factory_work_id is None and job:factory_work_id=job.intent.get('factory_execution',{}).get('work') or legacy_factory_work_id(job)
    value=intent(actor,i,kind,role,factory_work_id=factory_work_id)
    if kind=='issue' and InvoiceIssue.objects.filter(obligation_key=i.obligation_key).exists():raise ValidationError('This obligation already has a proven issued invoice')
    if job:
        if job.intent!=value or job.actor_id!=actor.pk:raise ValidationError('Reserved invoice intent differs; use operator reconciliation before a new reservation')
    return i,value,job


@transaction.atomic
def reserve(actor,case_id,invoice_id,kind,role,expected,factory_work_id=None):
    case=lock_case(actor,case_id,'finance.invoice.issue' if kind=='issue' else 'finance.invoice.deliver',expected)
    i,value,job=guard_reserve(actor,case,invoice_id,kind,role,factory_work_id)
    if job:return job
    job=InvoiceJob.objects.create(invoice=i,kind=kind,intent=value,operation_key=f'invoice:{i.pk}:{kind}:g1',actor=actor)
    event(actor,case,'invoice.effect_reserved',job=job.pk,kind=kind);bump(case);return job


def delivery_payload(invoice):
    p=invoice.payload
    fields=['reference','version','customer','contract','currency','amount','amount_basis','due_date']
    return dict({k:p[k] for k in fields},document_type='invoice',projection='finance-invoice-public/v1',
        lines=[{k:v for k,v in line.items() if k in ['transaction_id','stage','quantity','unit','rate','net','tax','total']} for line in p['lines']])


def effect_action(kind):
    actions={'issue':'finance.invoice.issue','deliver':'finance.invoice.deliver','adjust':'finance.invoice.correct','adjust_deliver':'finance.invoice.correction_deliver'}
    if kind not in actions:raise ValidationError('Unregistered invoice effect kind')
    return actions[kind]
