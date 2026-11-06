"""Read-only native projections. Never call probes, dispatchers or recovery workers."""
import hashlib,json
from django.conf import settings
from django.core.checks import run_checks, Tags
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.executor import MigrationExecutor
from apps.identity.services import require


def technical():
    from adapters.native_application_archive import build_identity,schema_inventory
    migrations=sorted(MigrationRecorder(connection).applied_migrations())
    executor=MigrationExecutor(connection)
    pending=[m.app_label+'.'+m.name for m,backward in executor.migration_plan(executor.loader.graph.leaf_nodes())]
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),inet_server_addr()::text,inet_server_port()')
        database=cursor.fetchone()
    # Check IDs/levels only: messages, settings and runtime paths can contain secrets.
    findings=sorted([[r.id,r.level] for r in run_checks(tags=[Tags.security],include_deployment_checks=True)])
    return {'source_identity':build_identity(),'process_build_identity':settings.PROCESS_BUILD_IDENTITY,'database_vendor':connection.vendor,
        'schema_identity':schema_inventory(connection.connection),'schema_fingerprint_implementation':'postgres-definitions-v2','migration_identity':hashlib.sha256(json.dumps(migrations).encode()).hexdigest(),
        'database_identity':hashlib.sha256(json.dumps(database).encode()).hexdigest(),'pending_migrations':pending,
        'applied_migrations':len(migrations),'deployment_checks':findings,
        'debug_enabled':settings.DEBUG,'web_identity':'current preflight process source only',
        'worker_identity':'UNVERIFIED','storage_retention_monitoring':'UNVERIFIED',
        'sso_security_load_uat':'UNVERIFIED'}


def integration(actor,case,pk):
    from apps.workflows import readiness as d
    from apps.workflows.readiness_models import IntegrationContract,IntegrationAssessment,IntegrationObservation,IntegrationProbe,IntegrationSelection
    d.readable(actor,case,True)
    r=IntegrationContract.objects.filter(case=case,pk=pk).first()
    if not r:raise ValidationError('Selected integration is unavailable in this case')
    d.contract_access(actor,r)
    assessment=IntegrationAssessment.objects.filter(contract=r).order_by('-pk').first()
    result={'contract':r.pk,'sha256':r.sha256,'family':r.payload['family'],'kind':r.payload['kind'],
        'assessment':assessment.pk if assessment else None,'current_ready':False,'review_current':False,
        'source_target_contract_verified':False,'business_dispatch_verified':False,
        'operational_ready':False,'credential_revision_sha256':hashlib.sha256(json.dumps(r.payload['credential_revision']).encode()).hexdigest(),
        'target_contract_version_sha256':hashlib.sha256(json.dumps(r.payload['contract_version']).encode()).hexdigest()}
    # Do not export endpoint URLs, principal refs, credentials, provider messages or raw payloads.
    if assessment:
        report=d.report(actor,case.pk,assessment.pk)
        result.update({k:report[k] for k in ['current_ready','review_current']})
    classification=assessment.snapshot.get('binding',{}).get('classification') if assessment else None
    result['recorded_probe_classification']=classification if classification in ['native_database_session','synthetic_authenticated_http','authenticated_remote_claim'] else 'UNVERIFIED'
    result['real_model_evaluated']=False
    heads=[]
    for kind in ['health','receipt','evaluation']:
        head=IntegrationObservation.objects.filter(contract=r,payload__kind=kind).order_by('-pk').first()
        probe=IntegrationProbe.objects.filter(contract=r,intent__kind=kind).order_by('-pk').first()
        heads.append({'kind':kind,'observation':head.pk if head else None,'sha256':head.sha256 if head else None,
            'authenticated_transport':bool(head and head.job_id),
            'probe':probe.pk if probe else None,'status':probe.status if probe else None})
    selection=IntegrationSelection.objects.filter(case=case,family=r.payload['family']).order_by('-version').first()
    result['selection_head']=[selection.pk,selection.contract_id] if selection else None
    result['heads']=heads
    return result


def job(actor,case,family,pk):
    from .pilot_physical import FAMILIES,read
    if family in FAMILIES:return read(actor,case,family,pk)
    from apps.workflows.operator_inventory import family_access,source_query,job_access,readable_manifest
    require(actor,case,'ops.read');family_access(actor,case,family)
    j=source_query(case,family).filter(pk=pk).first()
    if not j:raise ValidationError('Selected job is unavailable in this case')
    job_access(actor,case,family,j)
    value={'family':family,'id':j.pk,'status':j.status,'fence':j.fence,'attempts':j.attempts,
        'lease_until':j.lease_until.isoformat() if j.lease_until else None,
        'receipt_verified':False,'replay_permitted':False,'recovery_evidence':None}
    if family=='protection':
        from apps.workflows.operator_models import RecoveryArtifact,RecoveryProof
        require(actor,case,'ops.proof.read');require(actor,case,'ops.artifact.read')
        artifact=RecoveryArtifact.objects.filter(job=j).first()
        if artifact:readable_manifest(actor,case,artifact.manifest)
        proof=RecoveryProof.objects.filter(plan=j.plan).order_by('-pk').first()
        value['recovery_evidence']={'kind':j.kind,'plan':j.plan_id,
            'artifact':artifact.pk if artifact else None,'artifact_sha256':artifact.sha256 if artifact else None,
            'proof':proof.pk if proof else None,'proof_sha256':proof.sha256 if proof else None,
            'native_restore_verified':False}
    value['follow_up']='Receipt-first source investigation required' if j.status in ['unknown','uncertain','leased'] else 'Use source-owned controls; preflight never retries'
    # A recorded job status alone is not proof of an effect. These three adapters
    # perform local database lookups only. Other receipt variants remain unknown.
    value['local_receipt_sha256']=None
    if family in ['handoff','invoice','publication']:
        from apps.workflows.readiness import lookup_source
        try:receipt=lookup_source(family,j)
        except (ValidationError,ValueError):
            value['receipt_finding']='native_local_receipt_conflict_requires_source_investigation'
            return value
        value['local_receipt_sha256']=hashlib.sha256(json.dumps(receipt,sort_keys=True,default=str).encode()).hexdigest()
        value['receipt_verified']=bool(receipt)
        value['receipt_meaning']='Native local inbox/issuance/publication only; customer-channel receipt not established'
    return value
