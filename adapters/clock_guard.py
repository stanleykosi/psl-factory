"""Exact-source base due reassessment; stored commitments and pause history remain unchanged."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.pmo.models import ActionState
from apps.pmo.clocks import calculate_action_due,aware
from apps.policy.services import active_component,reference_values,resolve
from apps.policy.impact import configuration,digest


def readable(actor,case,state_id):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current action-clock reader required')
    for action in ['case.read','meeting.read']:require(actor,case,action)
    return ActionState.objects.select_related('item').filter(item__case=case,pk=state_id).first()


def required(case):
    values=['D04.clock_anchor_pause_rules','D04.deadline_parameters']
    r=resolve('D04.deadline_parameters',case)
    if r.configuration and reference_values(r.configuration)[0].get('action',{}).get('unit')=='working_days':
        values+=['D04.iana_timezone','D04.working_calendar_ref']
    return values


def source_inputs(state):
    first=state.item.states.order_by('number').first();meta=first.clock_meta
    if meta.get('format')=='psl.action-clock-input/v1':
        meeting=aware(meta['meeting_at']) if meta.get('meeting_at') else None
        assignment=aware(meta['assignment_at']) if meta.get('assignment_at') else None
        if meta.get('meeting_version'):
            from apps.pmo.models import MeetingVersion
            version=MeetingVersion.objects.filter(pk=meta['meeting_version'],meeting__case=state.item.case).first()
            if not version or version.occurred_at!=meeting:raise ValidationError('Original exact meeting clock input is inconsistent')
        return meeting,assignment,None,'exact_recorded_inputs'
    pk=first.policies.get('D04.clock_anchor_pause_rules')
    from apps.policy.models import Configuration
    old=Configuration.objects.filter(case=state.item.case,pk=pk,component='D04.clock_anchor_pause_rules').first()
    if not old or not meta.get('anchor'):raise ValidationError('Legacy action lacks exact clock input evidence; use human source-backed deadline review')
    original=reference_values(old)[0].get('action_anchor')
    current=reference_values(active_component('D04.clock_anchor_pause_rules',state.item.case))[0].get('action_anchor')
    if original!=current:raise ValidationError('Legacy action lacks the newly selected anchor input; do not infer assignment time from row creation')
    value=aware(meta['anchor'])
    return value if current=='meeting_at' else None,value if current=='assignment_at' else None,old.pk,'legacy_selected_anchor_only'


def observer(actor,case,state_id):
    state=readable(actor,case,state_id)
    if state and state.due_basis=='calculated':
        first=state.item.states.order_by('number').first()
        if first.clock_meta.get('format')!='psl.action-clock-input/v1':
            pk=first.policies.get('D04.clock_anchor_pause_rules')
            if pk:configuration(actor,case.pk,pk)
    return state


def guard(actor,case,action_state_id):
    state=readable(actor,case,action_state_id)
    if not state or state.item.current_id!=state.pk or state.status in ['completed','cancelled'] or state.due_basis!='calculated':
        raise ValidationError('Exact current nonterminal calculated action state required')
    meeting,assignment,historical,quality=source_inputs(state)
    due,pins,meta=calculate_action_due(case,meeting,assignment)
    return state,{'policies':pins,'historical_policy':{'D04.clock_anchor_pause_rules':historical} if historical else {},'proposed_base_due_at':due.isoformat(),
        'input_sha256':digest(meta),'input_quality':quality,'scope':'base_due_reassessment_only',
        'operational_deadline_unchanged':True,'action_grants_evaluated':False,'business_approval':False},None


def head(actor,case,state_id):
    state=observer(actor,case,state_id)
    if not state:return None
    return {'state':state.pk,'item':state.item_id,'current':state.item.current_id,'status':state.status,
        'stored_due_at':state.due_at.isoformat() if state.due_at else None,'due_basis':state.due_basis,
        'clock_input_sha256':digest(state.clock_meta),'paused_at':state.paused_at.isoformat() if state.paused_at else None,
        'scope':'base_due_reassessment_only','operational_deadline_unchanged':True,'business_approval':False}
