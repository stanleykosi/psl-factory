"""Immutable historical planning recovery configuration pins, not execution authority."""
from django.core.exceptions import PermissionDenied
from apps.workflows.models import FactoryExecutionBinding
from .factory_planning_policy_impact import readable
KEY='workflows.factory_planning_execution_bindings'
COMPONENT='OPS.factory_recovery_authority'
DEFINITION='planning/v1'

def query(actor,config):
    readable(actor,config.case)
    from apps.policy.impact import configuration
    configuration(actor,config.case_id,config.pk)
    rows=FactoryExecutionBinding.objects.filter(work__case=config.case,work__definition=DEFINITION)
    if config.component!=COMPONENT:return rows.none()
    return rows.filter(configuration_id=config.pk).select_related('work').only('id','sequence','configuration_id','work_id','work__id','work__case_id','work__definition').order_by('pk')

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.work.case_id!=case.pk or row.work.definition!=DEFINITION:raise PermissionDenied('Exact historical planning binding required')
    from apps.policy.impact import configuration
    config=configuration(actor,case.pk,row.configuration_id)
    if config.component!=COMPONENT:raise PermissionDenied('Exact planning recovery policy required')

def project(row):
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'planning',
        'sequence':row.sequence,'configuration':row.configuration_id,
        'state':'historical_planning_execution_binding','effects_performed':False}
