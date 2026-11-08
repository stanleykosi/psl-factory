"""Direct immutable delivery prerequisites, not universal closure validity."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.pmo.models import DeliveryRecord

KEY='pmo.delivery_prerequisites'
KINDS={'D11.hypercare_criteria_ref':'hypercare','D11.template_storage_retention_rules':'archive'}

def readable(actor,case):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current delivery observer required')
    require(actor,case,'case.read');require(actor,case,'delivery.read')

def query(actor,config):
    readable(actor,config.case)
    rows=DeliveryRecord.objects.filter(dossier__case=config.case)
    if config.component not in KINDS:return rows.none()
    return rows.filter(kind=KINDS[config.component],snapshot__policy_id=config.pk).order_by('pk')

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.dossier.case_id!=case.pk:raise PermissionDenied('Select this case delivery metadata')

def project(row):
    from apps.pmo.delivery import dossier_for,latest
    from apps.pmo.delivery_closure import qualified_hypercare,current_archive
    from apps.documents.contracts import digest
    current=False
    try:
        d=dossier_for(row.dossier.case,row.dossier_id)
        native=qualified_hypercare(d) if row.kind=='hypercare' else current_archive(d)
        current=native.pk==row.pk
    except (ValidationError,PermissionDenied):pass
    head=latest(row.dossier,row.kind,False)
    return {'id':row.pk,'kind':KEY,'record_kind':row.kind,'metadata_only':True,'domain_route':'delivery',
        'dossier':row.dossier_id,'snapshot_sha256':digest({'snapshot':row.snapshot,'data':row.data}),
        'policy':row.snapshot['policy_id'],'head':head.pk if head else None,
        'native_closure_prerequisite_current':current,'state':'historical_prerequisite_requires_current_qualification',
        'closure_authorized':False,'deployment_authorized':False,'debt_waived':False,'effects_performed':False}
