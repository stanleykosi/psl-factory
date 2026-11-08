import json
from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator

WORKERS={
 'handoff':'apps.workflows.management.commands.work_outbox',
 'publication':'apps.documents.management.commands.work_publications',
 'invoice':'apps.core.management.commands.work_invoices',
 'engineering':'apps.core.management.commands.work_corrective_requests',
 'partner':'apps.core.management.commands.work_partner_finance',
 'approval':'apps.core.management.commands.work_approval_routes',
 'supportresponse':'apps.baas.management.commands.work_support_responses',
 'supportchannel':'apps.baas.management.commands.work_support_channels',
 'ledgerdata':'apps.agents.management.commands.work_private_evidence',
 'protection':'apps.workflows.management.commands.work_operator_recovery',
 'readiness':'apps.workflows.management.commands.work_integration_readiness',
 'application':'apps.workflows.management.commands.work_application_recovery',
 'cold':'apps.workflows.management.commands.run_cold_recovery',
 'reconstitution':'apps.workflows.management.commands.run_reconstitution',
 'nativefinance':'apps.workflows.management.commands.run_native_finance_publications',
 'financefollowup':'apps.workflows.management.commands.work_finance_followup'}
KEY={'type':'string','pattern':'^[a-zA-Z][a-zA-Z0-9_.:-]{0,99}$'}
SHA={'type':'string','pattern':'^[a-f0-9]{64}$'}
ID={'type':'integer','minimum':1,'maximum':9223372036854775807}


def obj(fields):return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}


def schema():
    from adapters.pilot_guards import REGISTRY
    args={'expected_revision':ID}
    from .document_validators import ROLES
    from adapters.billing_usage import KEY as CASH_OPERATION_KEY
    specs={'recognition.attest':dict(args,recognition_input_id=ID,recognition_input_sha256={'type':'string','pattern':'^[a-f0-9]{64}$'}),
        'planning.readiness':dict(args,planning_packet_id=ID),'approval.route':dict(args,approval_request_id=ID,approval_purpose={'enum':['request','reminder']}),
        'ledger.review':dict(args,ledger_check_id=ID,ledger_review_evidence_id=ID,ledger_verdict={'enum':['approve','reject']}),
        'receipt.verify':dict(args,cash_receipt_id=ID,role={'enum':ROLES},cash_verification_evidence_id=ID),
        'receipt.allocate':dict(args,cash_lot_id=ID,issued_invoice_id=ID,cash_amount={'type':'string','minLength':1,'maxLength':70,'pattern':r'^(0|[1-9][0-9]{0,39})(\.[0-9]{1,20})?$'},operation_key={'type':'string','minLength':1,'maxLength':100,'pattern':CASH_OPERATION_KEY.pattern},role={'enum':ROLES},cash_allocation_evidence_id=ID),
        'payment.assess':dict(args,dossier_id=ID,coverage_id=ID),'hypercare.evaluate':dict(args,dossier_id=ID),
        'workflow.clock.evaluate':dict(args,action_state_id=ID),'role.decision.evaluate':dict(args,role={'enum':ROLES},decision_action={'enum':['approve','return','reject','withdraw','reopen']},delegated={'type':'boolean'}),
        'document.publish':dict(args,version_id=ID),'pmo.baseline.prepare':dict(args,plan_id=ID,cost_id=ID,sow_id=ID),
        'pmo.decision.record':dict(args,role={'enum':['PM','Head of PMO','CEO','PMO Lead']}),
        'pmo.baseline.sign':dict(args,signature_id=ID),
        'pmo.milestone.complete':dict(args,name={'type':'string','minLength':1,'maxLength':200},evidence_id=ID),
        'finance.invoice.issue':dict(args,invoice_id=ID,role={'type':'string','minLength':1,'maxLength':50}),
        'finance.invoice.deliver':dict(args,invoice_id=ID,role={'type':'string','minLength':1,'maxLength':50}),
        'finance.invoice.correct':dict(args,correction_id=ID,role={'type':'string','minLength':1,'maxLength':50}),
        'finance.invoice.correction_deliver':dict(args,correction_id=ID,role={'type':'string','minLength':1,'maxLength':50}),
        'baas.response.decide':dict(args,packet_id=ID,verdict={'enum':['release','withdraw']})}
    guard={'oneOf':[obj({'operation':{'const':key},'user_id':ID,'arguments':obj(specs[key])}) for key in REGISTRY]}
    deploy=obj({'ref':KEY,'revision':KEY,'web_key_ref':KEY,'worker_key_ref':KEY,
        'families':{'type':'array','minItems':1,'maxItems':16,'uniqueItems':True,'items':{'enum':list(WORKERS)}},
        'freshness_seconds':{'type':'integer','minimum':30,'maximum':900},
        'expected':obj({'source_identity':SHA,'schema_identity':SHA,'database_identity':SHA})})
    return obj({'format':{'const':'psl.pilot-bindings/v1'},
        'guards':{'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':guard},'deployment':deploy})


def validate(contract,payload):
    try:bounded=len(json.dumps(payload,allow_nan=False))<=24000
    except (ValueError,TypeError):bounded=False
    if not bounded or list(Draft202012Validator(schema()).iter_errors(payload)):raise ValidationError('Invalid bounded typed pilot bindings')
    for guard in payload['guards']:
        if type(guard['user_id']) is not int or any(type(value) is not int for key,value in guard['arguments'].items() if key.endswith('_id') or key=='expected_revision'):
            raise ValidationError('Native identifiers and revisions require exact bounded integers')
    participants={p['user_id'] for p in contract.payload['participants']}
    if any(g['user_id'] not in participants or g['operation'] not in contract.payload['operations'] for g in payload['guards']):
        raise ValidationError('Native guards must name selected participants and selected registered operations')
    from apps.core.models import Evidence
    from apps.core.evidence_access import public_evidence
    kinds={'plan_id':'plan','cost_id':'costing','sow_id':'sow','signature_id':'signature','evidence_id':'completion','cash_verification_evidence_id':'cash_verification','cash_allocation_evidence_id':'cash_allocation'}
    for g in payload['guards']:
        if g['operation']=='planning.readiness' and not Evidence.objects.filter(case=contract.case,pk=g['arguments']['planning_packet_id'],kind='planning_packet').exists():
            raise ValidationError('Exact scoped planning packet required')
        if g['operation']=='ledger.review' and not public_evidence(Evidence.objects.filter(case=contract.case,pk=g['arguments']['ledger_review_evidence_id'])).exists():
            raise ValidationError('Exact permitted public review evidence required')
        for k,kind in kinds.items():
            if k in g['arguments'] and not public_evidence(Evidence.objects.filter(case=contract.case,pk=g['arguments'][k],kind=kind)).exists():
                raise ValidationError('Exact permitted case source evidence required')
        from django.apps import apps
        for key,model,path in [('recognition_input_id','core.Evidence','case'),('approval_request_id','pmo.ApprovalRequest','case'),('ledger_check_id','finance.LedgerCheck','lineage__case'),('cash_receipt_id','finance.CashReceipt','case'),('cash_lot_id','finance.CashVerification','receipt__case'),('issued_invoice_id','finance.InvoiceIssue','invoice__case'),('dossier_id','pmo.DeliveryDossier','case'),('coverage_id','finance.BillingCoverage','case'),('action_state_id','pmo.ActionState','item__case'),('version_id','documents.Version','document__case'),('invoice_id','finance.Invoice','case'),('correction_id','finance.InvoiceCorrection','case'),('packet_id','baas.SupportResponsePacket','case')]:
            if key in g['arguments'] and not apps.get_model(model).objects.filter(pk=g['arguments'][key],**{path:contract.case}).exists():raise ValidationError('Exact native case subject required')
    d=payload['deployment']
    if d['web_key_ref']==d['worker_key_ref']:raise ValidationError('Independent role key references required')


def identities(value):
    profile=obj({'deployment_ref':KEY,'revision':KEY,'role':{'enum':['web','worker']},'principal_id':ID,
        'case_id':{'type':'string','pattern':'^[a-f0-9-]{36}$'},'classification':{'enum':['synthetic','operational']},
        'families':{'type':'array','maxItems':16,'uniqueItems':True,'items':{'enum':list(WORKERS)}},
        'secret_env':{'type':'string','pattern':'^PSL_PILOT_[A-Z0-9_]{1,70}$'},
        'storage_revision':KEY,'retention_revision':KEY,'monitoring_revision':KEY})
    schema={'type':'object','maxProperties':32,'propertyNames':KEY,'additionalProperties':profile}
    if list(Draft202012Validator(schema).iter_errors(value)):raise ValueError('Invalid pilot identity')
