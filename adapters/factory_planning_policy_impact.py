"""Direct planning work/profile metadata, never execution or source authority."""
from django.core.exceptions import PermissionDenied
from apps.workflows.models import FactoryWork
from apps.workflows import factory
from apps.pmo import planning
KEY='workflows.factory_planning_profiles'
COMPONENT='OPS.factory_planning_execution'
DEFINITION='planning/v1'

def readable(actor,case):
    if actor is None:raise PermissionDenied('Current planning factory observer required')
    factory.access(actor,case,'factory.read',DEFINITION)
    planning.readable(actor,case)

def query(actor,config):
    readable(actor,config.case)
    from apps.policy.impact import configuration
    configuration(actor,config.case_id,config.pk)
    rows=FactoryWork.objects.filter(case=config.case,definition=DEFINITION)
    if config.component!=COMPONENT:return rows.none()
    return rows.filter(policy_id=config.pk).only('id','case_id','definition','status','revision','policy_id').order_by('pk')

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.case_id!=case.pk or row.definition!=DEFINITION:raise PermissionDenied('Exact planning work metadata required')
    from apps.policy.impact import configuration
    if row.policy_id is None:raise PermissionDenied('Selected planning profile required')
    config=configuration(actor,case.pk,row.policy_id)
    if config.component!=COMPONENT:raise PermissionDenied('Exact planning profile required')

def project(row):
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'planning',
        'definition':row.definition,'status':row.status,'revision':row.revision,'policy':row.policy_id,
        'state':'observed_planning_work_profile','worker_started':False,'authority_rebound':False,'effects_performed':False}
