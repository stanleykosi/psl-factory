from django.db import transaction,connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import event,bump
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.policy.operator_validators import PROTECTION,OPERATOR,KINDS
from apps.policy.validation_validators import PROCESS_IDS,process_ids
from adapters.forecast import obj,KEY
from adapters.costing import read,HASH,ID
from adapters.hrfinance import timestamp
from adapters.operator_protection import file_receipt,restore_receipt
from .operator_recovery import locked,readable,config,authority
from . import private_readiness_operations as private
from apps.finance.acceptance_evaluation import evaluated
from .operator_models import RecoveryPlan,RecoveryProof,RecoveryJob,RecoveryArtifact,RecoveryAssessment,RecoveryReview
NKEY={'anyOf':[KEY,{'type':'null'}]};NINT={'anyOf':[{'type':'integer','minimum':0},{'type':'null'}]};NHASH={'anyOf':[HASH,{'type':'null'}]}
PLAN=obj({'scope':{'enum':['portable_case_metadata_v1','reported_full_database']},'process_ids':PROCESS_IDS,'build_ref':KEY,'source_ref':NKEY,'source_version':NKEY,'target_ref':NKEY,'expected_record_count':NINT,'expected_manifest_sha256':NHASH})
for field in [private.FIELD,private.protection.FIELD]:PLAN['properties'][field]={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID}
PROOF=obj({'plan_id':ID,'plan_sha256':HASH,'kind':{'enum':KINDS},'scope':{'enum':['portable_case_metadata_v1','reported_full_database']},'system':KEY,'external_ref':KEY,'receipt_version':KEY,'source_ref':NKEY,'target_ref':NKEY,'source_version':NKEY,'recorded_at':{'type':'string'},'outcome':{'enum':['passed','failed','unknown','unavailable']},'evidence_class':{'enum':['supplied_report','synthetic_report']},'record_count':NINT,'manifest_sha256':NHASH,'elapsed_seconds':NINT,'source_lag_seconds':NINT})
def plan_for(c,pk):
    p=RecoveryPlan.objects.select_related('case','actor').filter(case=c,pk=pk).first()
    if not p:raise ValidationError('Exact case recovery plan required')
    return p
def current_plan(p):
    if RecoveryPlan.objects.filter(case=p.case,reference=p.reference,version__gt=p.version).exists() or p.sha256!=digest(p.payload):raise ValidationError('Recovery plan superseded or changed; preserve historical receipts')
@transaction.atomic
def capture_plan(a,case_id,reference,payload,evidence_id,expected=None,predecessor=None):
    c=locked(a,case_id,'ops.capture',expected);readable(a,c,True);validate(KEY,reference);validate(PLAN,payload);process_ids(payload['process_ids']);e=subject(c,evidence_id,'ops_plan');old=RecoveryPlan.objects.filter(case=c,reference=reference).order_by('-version').first()
    private.validate_plan(a,c,payload);private.protection.validate_plan(a,c,payload,reference)
    for prior in RecoveryPlan.objects.filter(case=c,reference=reference):private.plan_access(a,prior)
    if old and private.ids(old) and not payload.get(private.FIELD):raise ValidationError('Private plan history cannot become a public reference')
    if old and private.protection.ids(old) and not payload.get(private.protection.FIELD):raise ValidationError('Protection plan history cannot become a public reference')
    if old and old.sha256==digest(payload):return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current plan predecessor required')
    r=RecoveryPlan.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,payload=payload,sha256=digest(payload),evidence=e,actor=a);private.audit(a,c,r,'plan_captured',plan=r.pk);bump(c);return r
@transaction.atomic
def capture_proof(a,case_id,plan_id,evidence_id,expected=None):
    c=locked(a,case_id,'ops.capture',expected);readable(a,c,True);p=plan_for(c,plan_id);private.plan_access(a,p);e=subject(c,evidence_id,'ops_proof');v=read(e.body,PROOF)
    if v['scope']!=p.payload['scope'] or v['plan_id']!=p.pk or v['plan_sha256']!=p.sha256 or any(v[k]!=p.payload[k] for k in ['source_ref','source_version','target_ref']):raise ValidationError('Supplied proof must bind the exact plan/source/version/target')
    if timestamp(v['recorded_at'])>timezone.now():raise ValidationError('Actual proof cannot be future dated')
    if not c.synthetic and v['evidence_class']=='synthetic_report':raise ValidationError('Synthetic reports cannot enter operational evidence')
    identity={'tenant':c.tenant,**{k:v[k] for k in ['system','external_ref','receipt_version']}}
    with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(digest(identity)[:15],16)])
    old=RecoveryProof.objects.filter(tenant=c.tenant,system=v['system'],external_ref=v['external_ref'],receipt_version=v['receipt_version']).first()
    if old:
        if old.plan_id!=p.pk or old.sha256!=digest(v):raise ValidationError('Conflicting or cross-case receipt identity; investigate without another claim')
        return old
    r=RecoveryProof.objects.create(plan=p,**identity,kind=v['kind'],payload=v,sha256=digest(v),evidence=e,actor=a);private.audit(a,c,p,'supplied_report',proof=r.pk,native_execution_verified=False);bump(c);return r

@evaluated
def inputs(p):
    current_plan(p);policy,rules=config(p.case,PROTECTION);private.rules(p,rules);operator,_=config(p.case,OPERATOR);heads=[];findings=[];native={};reported={};objectives={'rpo':'unknown','rto':'unknown'}
    if any(p.payload[k] is None for k in ['source_ref','source_version','target_ref','expected_record_count','expected_manifest_sha256']):findings.append('Expected coverage/source/target remains unknown')
    for kind in rules['required_proofs']:
        proof=RecoveryProof.objects.filter(plan=p,kind=kind).order_by('-pk').first();heads.append([kind,proof.pk if proof else None]);artifact=RecoveryArtifact.objects.filter(job__plan=p,job__kind=kind).select_related('job').order_by('-pk').first() if kind!='verification' else None
        if artifact:
            heads.append(['native:'+kind,artifact.pk]);native[kind]=True
            if private.has_private(p):
                try:private.current(artifact.job.actor,p,artifact.manifest)
                except (ValidationError,PermissionDenied,ConnectionError):findings.append('Private accepted metadata is historical; fresh scope/owner evidence required')
            try:
                if kind=='backup':file_receipt(artifact.job) or (_ for _ in ()).throw(ValidationError('Backup bytes unavailable'))
                if kind=='restore':restore_receipt(artifact.job) or (_ for _ in ()).throw(ValidationError('Drill receipt unavailable'))
            except (ValidationError,ConnectionError):findings.append('Native metadata '+kind+' currently unavailable')
            if p.payload['expected_manifest_sha256'] is not None and artifact.sha256!=p.payload['expected_manifest_sha256']:findings.append('Native metadata differs from expected manifest')
            if p.payload['expected_record_count'] is not None and len(artifact.manifest['evidence'])+len(artifact.manifest['jobs'])+private.count(artifact.manifest)!=p.payload['expected_record_count']:findings.append('Native metadata differs from expected record count')
            if (timezone.now()-(timestamp(artifact.receipt['completed_at']) if artifact.receipt.get('completed_at') else artifact.created_at)).total_seconds()>rules['freshness_seconds']:findings.append('Native metadata '+kind+' expired')
        if proof:
            v=proof.payload;reported[kind]=v['scope'];readable(proof.actor,p.case,True)
            if v['outcome']!='passed':findings.append('Reported '+kind+' is failed, unknown or unavailable')
            if (timezone.now()-timestamp(v['recorded_at'])).total_seconds()>rules['freshness_seconds']:findings.append('Reported '+kind+' expired')
            if v['manifest_sha256'] is None or v['record_count'] is None:findings.append('Reported '+kind+' digest/count unknown')
            elif p.payload['expected_manifest_sha256'] is not None and v['manifest_sha256']!=p.payload['expected_manifest_sha256'] or p.payload['expected_record_count'] is not None and v['record_count']!=p.payload['expected_record_count']:findings.append('Reported '+kind+' differs from expected coverage')
            if kind=='restore':
                for name,field in [('rto','elapsed_seconds'),('rpo','source_lag_seconds')]:
                    limit=rules[name+'_seconds'];value=v[field];objectives[name]='unknown' if limit is None or value is None else 'reported_within' if value<=limit else 'reported_exceeded'
                    if objectives[name]=='reported_exceeded':findings.append('Reported '+name+' exceeds configured objective')
        elif not artifact:findings.append('Missing '+kind+' evidence')
    result={'documentary_complete':not findings,'findings':list(dict.fromkeys(findings)),'native_metadata_effects':native,'supplied_report_scopes':reported,'objectives':objectives,'native_metadata_drill_verified':bool(native.get('export') and native.get('backup') and native.get('restore')),'full_database_restore_verified':False,'operational_ready':False,'deployment_authorized':False,'business_jobs_reenacted':False}
    return {'plan':p.sha256,'protection_policy':policy.pk,'operator_policy':operator.pk,'heads':heads,**({'accepted_protection_policy':private.protection.rules(p)} if private.protection.ids(p) else {})},result
@transaction.atomic
def assess(a,case_id,plan_id,operation_key,expected=None):
    c=locked(a,case_id,'ops.assess',expected);readable(a,c,True);validate(KEY,operation_key);p=plan_for(c,plan_id);private.plan_access(a,p);pins,result=inputs(p);old=RecoveryAssessment.objects.filter(plan=p,operation_key=operation_key).first()
    if old:
        if old.actor_id!=a.pk or old.snapshot!=pins or old.result!=result:raise ValidationError('Assessment intent changed; use a new key')
        return old
    r=RecoveryAssessment.objects.create(plan=p,operation_key=operation_key,snapshot=pins,result=result,actor=a);private.audit(a,c,p,'assessed',assessment=r.pk);bump(c);return r
def current_assessment(r):
    readable(r.actor,r.plan.case,True);private.plan_access(r.actor,r.plan);require_assess(r)
    if RecoveryAssessment.objects.filter(plan=r.plan,pk__gt=r.pk).exists():raise ValidationError('Newer protection assessment is current')
    from .operator_inventory import readable_manifest
    for artifact in RecoveryArtifact.objects.filter(job__plan=r.plan):readable_manifest(r.actor,r.plan.case,artifact.manifest)
    pins,result=inputs(r.plan)
    if r.snapshot!=pins or r.result!=result:raise ValidationError('Protection evidence/policy changed; reassess')
    if not result['documentary_complete']:raise ValidationError('Documentary evidence is incomplete')
def require_assess(r):
    from apps.identity.services import require
    require(r.actor,r.plan.case,'ops.assess')
@transaction.atomic
def review(a,case_id,assessment_id,verdict,operation_key,evidence_id,expected=None):
    c=locked(a,case_id,'ops.review',expected);readable(a,c,True);auth=authority(a,c,'review');_,rule=config(c,OPERATOR);r=RecoveryAssessment.objects.select_related('plan__case','actor').filter(plan__case=c,pk=assessment_id).first()
    if not r or a.pk!=rule['reviewer_id'] or auth['role']!=rule['reviewer_role']:raise PermissionDenied('Exact configured evidence reviewer required')
    private.plan_access(a,r.plan)
    preparers={r.actor_id,r.plan.actor_id}|set(RecoveryProof.objects.filter(plan=r.plan).values_list('actor_id',flat=True))|set(RecoveryJob.objects.filter(plan=r.plan).values_list('actor_id',flat=True))
    from .operator_inventory import readable_manifest
    for artifact in RecoveryArtifact.objects.filter(job__plan=r.plan):readable_manifest(a,c,artifact.manifest)
    if rule['independent_review'] and a.pk in preparers:raise PermissionDenied('Configured independent protection evidence review required')
    if verdict not in ['confirm','return','withdraw']:raise ValidationError('Typed evidence-review disposition required')
    validate(KEY,operation_key);e=subject(c,evidence_id,'ops_review');old=RecoveryReview.objects.filter(assessment=r,operation_key=operation_key).first()
    if old:
        if (old.actor_id,old.verdict,old.evidence_id)!=(a.pk,verdict,e.pk):raise ValidationError('Review intent conflicts')
        return old
    if verdict=='confirm':current_assessment(r)
    row=RecoveryReview.objects.create(assessment=r,operation_key=operation_key,verdict=verdict,snapshot=r.snapshot,authority=auth,evidence=e,actor=a);private.audit(a,c,r.plan,'evidence_reviewed',review=row.pk,operational_ready=False);bump(c);return row
@transaction.atomic
def report(a,case_id,assessment_id):
    c=locked(a,case_id,'ops.read');r=RecoveryAssessment.objects.select_related('plan__case','actor').filter(plan__case=c,pk=assessment_id).first()
    if not r:raise ValidationError('Exact case assessment required')
    private.plan_access(a,r.plan)
    from .operator_inventory import readable_manifest
    for artifact in RecoveryArtifact.objects.filter(job__plan=r.plan):readable_manifest(a,c,artifact.manifest)
    holds=[]
    try:current_assessment(r)
    except (ValidationError,PermissionDenied,ConnectionError):holds.append('Current assessment requires evidence/authority reassessment')
    latest=RecoveryReview.objects.filter(assessment=r).select_related('actor').order_by('-pk').first();reviewed=False
    if latest and latest.verdict=='confirm' and not holds:
        try:
            readable(latest.actor,c,True)
            from .operator_inventory import readable_manifest
            for artifact in RecoveryArtifact.objects.filter(job__plan=r.plan):readable_manifest(latest.actor,c,artifact.manifest)
            reviewed=latest.authority==authority(latest.actor,c,'review') and latest.snapshot==r.snapshot
        except (ValidationError,PermissionDenied):pass
    value={'assessment':r.pk,'recorded_documentary_complete':r.result['documentary_complete'],'current_documentary_complete':not holds,'review_current':reviewed,'holds':holds,'full_database_restore_verified':False,'operational_ready':False,'deployment_authorized':False}
    from apps.identity.models import Grant
    if Grant.objects.filter(case=c,user=a,action='ops.proof.read',active=True).exists():value['recorded_result']=r.result
    return value
