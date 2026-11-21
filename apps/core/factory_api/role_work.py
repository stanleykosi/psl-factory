from apps.identity import role_work as domain
from apps.identity.role_work_views import page_number
from apps.identity.teams import FOCUS, MODE_LABELS

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj


ROLE = choice(*FOCUS)
REASON = {**TEXT, 'maxLength': 1000}
TOKEN = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
CARD = obj({'id': ID, 'case_id': UUID, 'workspace': TEXT, 'role': ROLE, 'owner': TEXT, 'mine': BOOLEAN,
            'title': TEXT, 'due': nullable(DATETIME), 'state': TEXT, 'url': TEXT, 'line': nullable(TEXT)})
PACKET = obj({'title': TEXT, 'version': nullable(ID), 'role': TEXT,
              'sections': array(obj({'heading': TEXT, 'text': {'type': 'string'}})),
              'verdicts': array(choice(*domain.DECISIONS)), 'token': TOKEN})
PINS = {'expected': REVISION, 'case_expected': REVISION}


@endpoint(response=obj({
    'positions': array(obj({'role': ROLE, 'mode': choice(*MODE_LABELS), 'name': TEXT, 'area': TEXT,
                           'focus': TEXT, 'workspace': TEXT, 'team': nullable(TEXT)}), limit=50),
    'actions': array(CARD, limit=domain.SIZE), 'decisions': array(CARD, limit=domain.SIZE),
    'team_decisions': array(CARD, limit=domain.SIZE), 'limited': BOOLEAN,
    'has_teams': BOOLEAN, 'page': ID, 'has_next': BOOLEAN, 'as_of': DATETIME,
}), query={'page': {'type': 'integer', 'minimum': 1, 'maximum': 9999}},
    summary='Read role dashboards and exact current work and decision assignments')
def dashboard(request):
    return domain.dashboard(request.user, page_number(request.GET.get('page')))


@endpoint(response=obj({**CARD['properties'], 'revision': REVISION, 'case_revision': REVISION,
                        'action_revision': REVISION, 'review': nullable(PACKET),
                        'operations': array(choice('start','complete')), 'conclusion': nullable(TEXT)},
                       optional=('action_revision',)), summary='Read one assigned native action or decision')
def detail(request, assignment_id):
    return domain.detail(request.user, domain.entry_for(request.user, assignment_id))


@endpoint(method='POST', request=obj({**PINS, 'operation': choice('start','complete'), 'reason': REASON,
                                     'action_revision': REVISION}), response=obj({'state': TEXT, 'action_revision': REVISION}),
          summary='Update the exact native action assigned to you')
def action(request, assignment_id, *, body):
    result = domain.act(request.user, assignment_id, **body)
    return {'state': result.status, 'action_revision': result.number}


@endpoint(method='POST', request=obj({**PINS, 'verdict': choice(*domain.DECISIONS), 'note': REASON, 'token': TOKEN}),
          response=obj({'review_id': ID, 'verdict': choice(*domain.DECISIONS)}),
          summary='Record a currently authorised decision on its exact assigned document')
def decide(request, assignment_id, *, body):
    return domain.decide(request.user, assignment_id, **body)
