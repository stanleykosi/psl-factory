"""Current audience disclosure is independent of broad case/document access."""
from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.core.workbench import active
from apps.policy.services import active_component,reference_values
from apps.policy.project_view_validators import COMPONENT,SOURCE_ACTIONS
from adapters.project_view import ProjectMetadataAdapter

def context(actor,case,key):
    active(actor);require(actor,case,'project.view')
    if case.kind!='project':raise ValidationError('Project view required')
    policy=active_component(COMPONENT,case);value=reference_values(policy)[0]
    profile=next((p for p in value['profiles'] if p['key']==key and actor.pk in p['recipient_ids']),None)
    if not profile:raise PermissionDenied('Current exact audience membership required')
    source=get_user_model().objects.filter(pk=value['discloser_id'],is_active=True).first()
    if not source:raise PermissionDenied('Current active disclosure principal required')
    for action in {'case.read','project.share',*[SOURCE_ACTIONS[g] for g in profile['groups']]}:require(source,case,action)
    return policy,profile,source

@transaction.atomic
def projection(actor,case_id,key):
    case=Case.objects.select_for_update().get(pk=case_id)
    policy,profile,source=context(actor,case,key)
    list(get_user_model().objects.select_for_update().filter(pk__in={actor.pk,source.pk}).order_by('pk'))
    list(Grant.objects.select_for_update().filter(case=case,user_id__in={actor.pk,source.pk}).order_by('pk'))
    policy,profile,source=context(actor,case,key)
    groups=ProjectMetadataAdapter().read(case,profile['groups'],profile['max_records']);now=timezone.now()
    for name,group in groups.items():
        if not group['items'] and profile['missing_behavior']=='hold':raise ValidationError('Configured source group has no recorded facts: '+name)
        for item in group['items']:
            age=(now-datetime.fromisoformat(item['source_at'])).total_seconds()
            item['freshness']='within_recorded_age' if 0<=age<=profile['max_age_seconds'] else 'outside_recorded_age'
            if item['freshness']=='outside_recorded_age' and profile['stale_behavior']=='hold':raise ValidationError('Configured source-age threshold exceeded: '+name)
        group['coverage']='recorded_facts' if group['items'] else 'unknown_no_recorded_source'
    return {'case_id':str(case.pk),'synthetic':case.synthetic,'audience':key,'configuration_id':policy.pk,'adapter':ProjectMetadataAdapter.name,'observed_at':now.isoformat(),'groups':groups,
        'semantics':'Recorded source facts only; age does not certify current approval, phase, completeness or execution readiness. No broad case/document access is granted.',
        'effect_tools':[]}

def discover(actor):
    active(actor);rows=[]
    cases=Case.objects.filter(kind='project',grant__user=actor,grant__active=True,grant__action='project.view').distinct().order_by('-created_at','-pk')
    for case in cases[:100]:
        try:
            policy=active_component(COMPONENT,case)
            profiles=reference_values(policy)[0]['profiles']
        except (ValidationError,PermissionDenied):continue
        for profile in profiles:
            if actor.pk not in profile['recipient_ids']:continue
            try:context(actor,case,profile['key'])
            except (ValidationError,PermissionDenied):continue
            rows.append({'case_id':str(case.pk),'audience':profile['key'],'synthetic':case.synthetic})
    return rows
