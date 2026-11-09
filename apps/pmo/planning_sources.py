"""Source-backed scope/estimate interpretation; never a version-number conversion.

Capture remains possible with unknowns. Only completeness consumes this contract.
Internal clarification is an action, not an additional baseline approval.
"""
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.models import Audit
from apps.core.services import event
from apps.documents.contracts import digest, validate
from apps.identity.services import require
import hashlib
from adapters.planning_packet import SOURCE_KINDS, CORRELATION_FIELDS as FIELDS, CORRELATIONS as SCHEMA



def pin(case, pk, kinds=None):
    from .planning import proof
    if type(pk) is not int or pk<1:
        raise ValidationError('Exact positive source evidence identity required')
    e = proof(case, pk, kinds)
    if hashlib.sha256(e.body.encode()).hexdigest()!=e.sha256:
        raise ValidationError('Source content does not match its immutable hash')
    return {'id': e.pk, 'kind': e.kind, 'version': e.version, 'sha256': e.sha256}


def context(case, payload):
    """Validate shape and pin supplied sources, not completeness or agreement."""
    rows = payload.get('source_correlations', [])
    validate(SCHEMA, rows)
    if len({r['key'] for r in rows}) != len(rows) or len({(r['source_field'], r['source_id']) for r in rows}) != len(rows):
        raise ValidationError('Distinct correlation keys and source/field pairs required')
    if any(r['key'].startswith(('missing.','binding.')) for r in rows):
        raise ValidationError('Correlation keys cannot use the reserved missing. or binding. prefixes')
    pins = {}
    for row in rows:
        value = {'source': pin(case, row['source_id'], SOURCE_KINDS[row['source_field']])}
        for field, kinds in [('target_prd_id', SOURCE_KINDS['prd_id']), ('target_scope_id', SOURCE_KINDS['scope_id']), ('evidence_id', None)]:
            value[field] = pin(case, row[field], kinds) if row[field] is not None else None
        if row['resolution_id'] is not None:
            if row['state']!='excluded':raise ValidationError('Only a retained excluded source may bind a disposition response')
            resolution = Audit.objects.filter(case=case, pk=row['resolution_id'], action='planning.source_resolved').first()
            if not resolution:
                raise ValidationError('Exact native clarification response required')
            value['resolution'] = {'id': resolution.pk, 'sha256': digest(resolution.data)}
        pins[row['key']] = value
    return pins


def current_resolution(case, row, payload):
    from .planning import readable
    from .models import ActionItem
    response = Audit.objects.filter(case=case, pk=row['resolution_id'], action='planning.source_resolved').first()
    if not response:
        raise ValidationError('Excluded source needs its exact owner clarification response')
    data = response.data
    keys={'packet_id','packet_sha256','key','action_id','source_field','source_id','source_sha256','disposition','evidence_id',
        'replacement_source_id','target_prd_id','target_scope_id','approval_granted','action_state_id'}
    if not isinstance(data,dict) or set(data)!=keys or data['approval_granted'] is not False:
        raise ValidationError('Closed non-approval clarification response required')
    if any(type(data[k]) is not int or data[k]<1 for k in ['packet_id','action_id','source_id','evidence_id','replacement_source_id','target_prd_id','target_scope_id','action_state_id']):
        raise ValidationError('Exact typed clarification/source identities required')
    from . import planning
    original=case.evidence.filter(pk=data['packet_id'],kind='planning_packet').first()
    original_value=planning.read(case,original,'packet','coordinate')
    original_row=row_for(original_value['payload'],data['key'])
    marker=Audit.objects.filter(case=case,action='planning.source_clarification',data__packet_id=data['packet_id'],
        data__packet_sha256=data['packet_sha256'],data__key=data['key'],data__action_id=data['action_id']).first()
    if not marker or original.sha256!=data['packet_sha256'] or (original_row['source_field'],original_row['source_id'])!=(data['source_field'],data['source_id']):
        raise ValidationError('Original exact source question and response provenance required')
    if pin(case,data['source_id'])['sha256']!=data['source_sha256']:
        raise ValidationError('Original source hash changed')
    item = ActionItem.objects.select_related('current').filter(case=case, pk=data['action_id']).first()
    if not item or item.current_id != data['action_state_id'] or item.current.status != 'completed' or item.current.owner_id != response.actor_id or item.current.actor_id != response.actor_id or item.current.evidence_id != data['evidence_id']:
        raise ValidationError('Clarification owner or response changed; capture a source-backed successor')
    readable(response.actor, case)
    for action in ['planning.participate', 'action.own', 'action.work']:
        require(response.actor, case, action)
    pin(case, data['evidence_id'])
    if (data['disposition'], data['source_field'], data['source_id'], data['replacement_source_id'], data['target_prd_id'], data['target_scope_id']) != (
            'exclude_in_successor', row['source_field'], row['source_id'], payload[row['source_field']], payload['prd_id'], payload['scope_id']):
        raise ValidationError('Clarification response must pin this exact retained source and selected replacement/PRD/scope')
    return response.pk


def assessment(case, payload):
    pins = context(case, payload)
    rows = payload.get('source_correlations', [])
    findings = []
    for field in SOURCE_KINDS:
        if payload[field] is None:
            findings.append({'key': 'missing.'+field, 'code': 'source_missing', 'source_ids': [],
                'detail': field.replace('_id', '').replace('_', ' ').capitalize() + ' source is missing; no zero or equivalence is assumed.'})
    for field in FIELDS:
        if payload[field] is not None and not any(r['source_field'] == field and r['source_id'] == payload[field] and r['state'] == 'current' for r in rows):
            findings.append({'key': 'binding.'+field, 'code': 'correlation_unknown', 'source_ids': [payload[field]],
                'detail': 'Declared target PRD/scope and source interpretation are missing for ' + field + '.'})
    resolutions = []
    for row in rows:
        detail = None
        if row['state'] == 'excluded':
            try:
                resolutions.append(current_resolution(case, row, payload))
            except (ValidationError, PermissionDenied):
                detail = 'Retained source exclusion lacks a current exact owner response; no scope selection is authorized.'
        elif row['state'] == 'conflicting':
            detail = 'Conflicting scope/estimate source remains unresolved: ' + row['detail']
        elif row['source_id'] != payload[row['source_field']]:
            detail = 'Additional current source conflicts with the explicitly selected ' + row['source_field'] + '.'
        elif any(row[k] is None for k in ['document_version', 'target_prd_id', 'target_scope_id', 'evidence_id']):
            detail = 'Source version, declared target PRD/scope or interpretation evidence remains unknown.'
        elif (row['target_prd_id'], row['target_scope_id']) != (payload['prd_id'], payload['scope_id']):
            detail = ('Declared target PRD ' + str(row['target_prd_id']) + '/scope ' + str(row['target_scope_id'])
                + ' differs from selected PRD ' + str(payload['prd_id']) + '/scope ' + str(payload['scope_id']) + '. No conversion or equivalence is assumed.')
        if detail:
            findings.append({'key': row['key'], 'code': 'source_conflict' if row['state'] == 'conflicting' else 'correlation_unresolved',
                'source_ids': list(dict.fromkeys([row['source_id']] + ([payload[row['source_field']]] if payload[row['source_field']] else []))),
                'document_version': row['document_version'], 'declared_target_prd_id': row['target_prd_id'],
                'declared_target_scope_id': row['target_scope_id'], 'detail': detail})
    return {'protocol': 'planning-source-correlation/v1', 'complete': not findings, 'findings': findings,
        'source_pins': pins, 'resolution_ids': resolutions, 'approval_granted': False}


def require_complete(case, payload):
    value = assessment(case, payload)
    if not value['complete']:
        raise ValidationError('Source correlation holds dependent readiness: ' + '; '.join(f['key'] + ': ' + f['detail'] for f in value['findings']))
    return value


def row_for(payload, key):
    row = next((r for r in payload.get('source_correlations', []) if r['key'] == key), None)
    if row is None:
        raise ValidationError('Choose an exact declared source correlation row')
    return row


@transaction.atomic
def clarify(actor, case_id, packet_id, key, owner_id=None):
    from . import planning
    from .meetings import create_action, scoped_person
    from .models import ActionItem
    case = planning.locked(actor, case_id, 'coordinate')
    require(actor, case, 'action.manage')
    packet, value = planning.packet(case, packet_id)
    finding = next((f for f in assessment(case, value['payload'])['findings'] if f['key'] == key), None)
    if finding is None:
        raise ValidationError('This source has no unresolved correlation finding')
    if owner_id is not None:
        owner = scoped_person(case, owner_id, 'action.own')
        planning.readable(owner, case)
        require(owner, case, 'planning.participate')
    old = Audit.objects.filter(case=case, action='planning.source_clarification', data__packet_id=packet.pk, data__key=key).first()
    if old:
        item = ActionItem.objects.get(case=case, pk=old.data['action_id'])
        if item.current.owner_id != owner_id:
            raise ValidationError('Existing clarification owner differs; use explicit native action reassignment')
        return item
    row = next((r for r in value['payload'].get('source_correlations', []) if r['key'] == key), None)
    source_id = row['source_id'] if row else (finding['source_ids'][0] if finding['source_ids'] else value['payload']['prd_id'])
    if source_id is None:
        from .engagement import current_capture
        source_id=current_capture(case).evidence_id
    pin(case,source_id)
    # The action queue contains bounded reference identifiers, not private scope text.
    description = 'Clarify planning packet ' + str(packet.pk) + ', ' + key + ': sources ' + ', '.join(map(str, finding['source_ids'])) + '. Review exact declared PRD/scope in the planning workspace; no baseline approval is granted.'
    item = create_action(actor, case.pk, 'PLANNING-SOURCE-' + str(packet.pk) + '-' + key, description, owner_id, None,
        source_id, 'Source correlation needs an evidenced internal owner response; no inferred deadline.', case.revision)
    event(actor, case, 'planning.source_clarification', packet_id=packet.pk, packet_sha256=packet.sha256,
        key=key, finding=finding, action_id=item.pk)
    return item


@transaction.atomic
def resolve(actor, case_id, packet_id, key, action_id, expected_action, disposition, evidence_id,
            replacement_source_id=None, target_prd_id=None, target_scope_id=None):
    from . import planning
    from .meetings import change_action
    from .models import ActionItem
    case = planning.locked(actor, case_id, 'participate')
    packet, value = planning.packet(case, packet_id)
    row = row_for(value['payload'], key)
    marker = Audit.objects.filter(case=case, action='planning.source_clarification', data__packet_id=packet.pk,
        data__key=key, data__action_id=action_id).first()
    item = ActionItem.objects.select_related('current').filter(case=case, pk=action_id).first()
    if not marker or not item or item.current.owner_id != actor.pk:
        raise PermissionDenied('Only the current explicitly assigned clarification owner can respond')
    for action in ['action.own', 'action.work']:
        require(actor, case, action)
    if disposition not in ['source_correction_required', 'exclude_in_successor']:
        raise ValidationError('Choose source correction or evidenced exclusion in a successor; equivalence cannot be invented')
    pin(case, evidence_id)
    if disposition == 'exclude_in_successor':
        if replacement_source_id == row['source_id']:
            raise ValidationError('An excluded source needs a distinct evidenced replacement')
        pin(case, replacement_source_id, SOURCE_KINDS[row['source_field']])
        pin(case, target_prd_id, SOURCE_KINDS['prd_id']); pin(case, target_scope_id, SOURCE_KINDS['scope_id'])
    elif any(x is not None for x in [replacement_source_id, target_prd_id, target_scope_id]):
        raise ValidationError('Correction request does not select or approve replacement sources')
    request = {'packet_id': packet.pk, 'packet_sha256': packet.sha256, 'key': key, 'action_id': item.pk,
        'source_field': row['source_field'], 'source_id': row['source_id'], 'source_sha256': pin(case, row['source_id'])['sha256'],
        'disposition': disposition, 'evidence_id': evidence_id, 'replacement_source_id': replacement_source_id,
        'target_prd_id': target_prd_id, 'target_scope_id': target_scope_id, 'approval_granted': False}
    previous = Audit.objects.filter(case=case, action='planning.source_resolved', data__action_id=item.pk).order_by('-pk').first()
    if previous and previous.actor_id == actor.pk and previous.data == dict(request, action_state_id=item.current_id):
        return previous
    state = change_action(actor, case.pk, item.pk, 'complete', evidence_id,
        'Source-backed clarification response: ' + disposition + '. A corrected successor and ordinary baseline decisions remain required.',
        case.revision, expected_action)
    return event(actor, case, 'planning.source_resolved', **request, action_state_id=state.pk)


def historical_predecessor(case):
    """Read immutable provenance for retention, never reuse historical authority.

    A generic evidence append cannot grant claims or hide the previous native
    alternatives. The new capture independently checks current actor and sources.
    """
    from .planning import PlanningPacketAdapter, INPUT
    skipped=[]
    for item in case.evidence.filter(kind='planning_packet').order_by('-version'):
        actual=hashlib.sha256(item.body.encode()).hexdigest()
        recorded=Audit.objects.filter(case=case,actor=item.created_by,action='planning.recorded',
            data={'kind':'packet','evidence_id':item.pk,'sha256':item.sha256}).exists()
        reason=None
        if not recorded:reason='untrusted_generic_head'
        elif actual!=item.sha256:reason='native_content_hash_mismatch'
        else:
            try:
                value=PlanningPacketAdapter.parse(item)
                keys={'protocol','engagement_id','engagement_hash','payload','action_heads'}
                if value.get('protocol')=='planning-packet/v2':keys.add('source_pins')
                if set(value)!=keys or value['protocol'] not in ['planning-packet/v1','planning-packet/v2']:
                    raise ValidationError('Invalid historical native shape')
                validate(INPUT,value['payload']);validate(SCHEMA,value['payload'].get('source_correlations',[]))
                return item,value,skipped
            except (ValidationError,KeyError,TypeError):reason='invalid_native_packet_shape'
        skipped.append({'evidence_id':item.pk,'version':item.version,'recorded_sha256':item.sha256,
            'content_sha256':actual,'reason':reason})
    return None,None,skipped


def validate_successor(case, old_payload, payload):
    """Retain declared unresolved alternatives and recorded dispositions.

    Historical comparisons intentionally do not resolve current source authority.
    The new payload and any future readiness are independently current-checked.
    """
    rows={(r['source_field'],r['source_id']):r for r in payload.get('source_correlations',[])}
    for old in old_payload.get('source_correlations',[]):
        unresolved=(old['state']!='current' or old['source_id']!=old_payload[old['source_field']]
            or any(old[k] is None for k in ['document_version','target_prd_id','target_scope_id','evidence_id'])
            or (old['target_prd_id'],old['target_scope_id'])!=(old_payload['prd_id'],old_payload['scope_id']))
        if not unresolved:continue
        new=rows.get((old['source_field'],old['source_id']))
        if new is None:
            raise ValidationError('Retain conflicting source '+old['key']+' in the successor with explicit correction or owner disposition')
        if new['state']=='current' and any(new[k]!=old[k] for k in ['target_prd_id','target_scope_id','state']):
            if new['evidence_id'] is None or new['evidence_id']==old['evidence_id']:
                raise ValidationError('New source-backed interpretation evidence is required to correct '+old['key'])


def clarifications(case, packet_id):
    from .models import ActionItem
    result=[]
    for marker in Audit.objects.filter(case=case,action='planning.source_clarification',data__packet_id=packet_id).order_by('pk'):
        item=ActionItem.objects.select_related('current').get(case=case,pk=marker.data['action_id'])
        response=Audit.objects.filter(case=case,action='planning.source_resolved',data__action_id=item.pk).order_by('-pk').first()
        owner_status='unassigned'
        if item.current.owner_id:
            try:
                from .planning import readable
                readable(item.current.owner,case);require(item.current.owner,case,'planning.participate');require(item.current.owner,case,'action.own')
                owner_status='assigned'
            except (ValidationError,PermissionDenied):owner_status='source_access_held'
        result.append({'key':marker.data['key'],'action_id':item.pk,'action_version':item.current.number,
            'owner_id':item.current.owner_id,'owner_status':owner_status,
            'status':item.current.status,'response_id':response.pk if response else None,'approval_granted':False})
    return result
