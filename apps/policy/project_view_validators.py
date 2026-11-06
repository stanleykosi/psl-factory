from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj
from .document_validators import typed

COMPONENT='D11.shared_project_view'
GROUPS=['identifiers','milestones','actions','delivery_events']
SOURCE_ACTIONS={'identifiers':'engagement.read','milestones':'case.read','actions':'meeting.read','delivery_events':'delivery.read'}
SCHEMA='schema:psl/shared-project-view/v1'
ID={'type':'integer','minimum':1}
VALUE=obj({'discloser_id':ID,'allow_synthetic':{'type':'boolean'},'profiles':{'type':'array','minItems':1,'maxItems':30,'items':obj({
    'key':{'type':'string','pattern':'^[a-zA-Z0-9_-]{1,60}$'},
    'recipient_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},
    'groups':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'enum':GROUPS}},
    'max_records':{'type':'integer','minimum':1,'maximum':100},
    'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},
    'stale_behavior':{'enum':['hold','mark_recorded_facts']},
    'missing_behavior':{'enum':['hold','mark_unknown']}})}})

def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA,VALUE)
    if case.kind!='project' or value['allow_synthetic']!=case.synthetic:raise ValidationError('Exact project/classification view criteria required')
    if len({p['key'] for p in value['profiles']})!=len(value['profiles']):raise ValidationError('Distinct explicit audience keys required')
    if not runtime:
        from apps.identity.services import require
        try:
            source=get_user_model().objects.get(pk=value['discloser_id'],is_active=True)
            for action in {'case.read','project.share',*[SOURCE_ACTIONS[g] for p in value['profiles'] for g in p['groups']]}:require(source,case,action)
            for pk in {pk for p in value['profiles'] for pk in p['recipient_ids']}:
                require(get_user_model().objects.get(pk=pk,is_active=True),case,'project.view')
        except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Actual current disclosure/source grants and recipient view grants required') from None
    return value
