"""Native, deployment-owned role observations; never executes or probes business work."""
import hashlib,hmac,json,os,uuid
from datetime import datetime,timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.policy.pilot_binding_validators import identities,WORKERS

BOOT=uuid.uuid4().hex


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def profile(binding,role):
    try:
        registry=settings.PILOT_RUNTIME_IDENTITIES;identities(registry)
        d=binding.payload['deployment'];p=registry[d[role+'_key_ref']]
        assert p['role']==role and p['deployment_ref']==d['ref'] and p['revision']==d['revision']
        assert p['case_id']==str(binding.contract.case_id)
        assert p['classification']==('synthetic' if binding.contract.case.synthetic else 'operational')
        assert p['principal_id'] in {u['user_id'] for u in binding.contract.payload['participants']}
        if role=='worker':assert set(d['families'])<=set(p['families'])
        secret=os.environ.get(p['secret_env'],'').encode();assert len(secret)>=32
        other=registry.get(d[('worker' if role=='web' else 'web')+'_key_ref'])
        if other:
            assert p['secret_env']!=other['secret_env']
            assert secret!=os.environ.get(other['secret_env'],'').encode()
        return p,secret,digest({'profile':p,'credential_sha256':hashlib.sha256(secret).hexdigest()})
    except (AssertionError,KeyError,ValueError,TypeError):
        raise ValidationError('Current exact role-specific deployment identity/credential references required') from None


def observe(binding,role,family,observe_only=True):
    from adapters.pilot_preflight import technical
    p,key,identity=profile(binding,role)
    if role=='worker' and family not in binding.payload['deployment']['families']:raise ValidationError('Selected native worker family required')
    if role=='web' and family is not None:raise ValidationError('Web observations cannot claim worker coverage')
    actual=technical()
    if actual['source_identity']!=settings.PROCESS_BUILD_IDENTITY:raise ValidationError('Process source changed since startup; restart before attestation')
    value={'format':'psl.pilot-runtime/v2','binding':binding.pk,'case_id':str(binding.contract.case_id),
        'role':role,'family':family,'process_boot':BOOT,'process_build_identity':settings.PROCESS_BUILD_IDENTITY,'process_id_sha256':digest(os.getpid()),
        'principal_id':p['principal_id'],'identity':identity,'observed_at':datetime.now(timezone.utc).isoformat(),
        'technical':actual,'source':'native_web_request' if role=='web' else WORKERS[family],
        'trust':'deployment_owned_instrumentation','business_jobs_executed':False,
        'observation_phase':'before_business_handler',
        'invocation_mode':'authenticated_web_observation' if role=='web' else 'observe_only' if observe_only else 'native_handler_follows',
        'storage_retention_monitoring':'deployment_declarations_only',
        'declaration_revisions_sha256':digest([p['storage_revision'],p['retention_revision'],p['monitoring_revision']])}
    return value,hmac.new(key,json.dumps(value,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()


def verify(binding,receipt,role,family,actual):
    from django.contrib.auth import get_user_model
    from apps.policy import pilot
    from django.utils import timezone as tz
    from django.core.exceptions import PermissionDenied
    try:
        p,key,identity=profile(binding,role);v=receipt.payload
        assert v['format']=='psl.pilot-runtime/v2'
        assert v['process_build_identity']==v['technical']['source_identity']==actual['source_identity']==actual['process_build_identity']
        assert receipt.sha256==digest(v)
        assert hmac.compare_digest(receipt.signature,hmac.new(key,json.dumps(v,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest())
        assert v['binding']==binding.pk and v['case_id']==str(binding.contract.case_id) and v['role']==role and v['family']==family
        assert v['identity']==identity and v['principal_id']==p['principal_id']
        assert v['source']==('native_web_request' if role=='web' else WORKERS[family])
        user=get_user_model().objects.get(pk=v['principal_id']);pilot.context(user,binding.contract.case_id,'pilot.runtime.observe')
        age=(tz.now()-receipt.created_at).total_seconds()
        assert 0<=age<=binding.payload['deployment']['freshness_seconds']
        observed=datetime.fromisoformat(v['observed_at']);assert abs((receipt.created_at-observed).total_seconds())<30
        for k,expected in binding.payload['deployment']['expected'].items():assert v['technical'][k]==actual[k]==expected
        for k in ['debug_enabled','deployment_checks','pending_migrations']:assert v['technical'][k]==actual[k]
        assert not v['technical']['pending_migrations']
        return True
    except (AssertionError,KeyError,ValueError,TypeError,PermissionDenied,ValidationError,get_user_model().DoesNotExist):return False
