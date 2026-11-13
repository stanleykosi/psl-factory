"""Builds architecture/model.json for the PSL frontend redesign data API.

The canonical model is authored here as compact tables so it stays reviewable; the
factory compiler (packages/architecture/arch.py) validates it and generates the package.
Run: python3 architecture/build_model.py
"""
import hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {
    'S-SCOPE': ('Approved scope v2 (early start by exception)', 'sources/scope-v2.md', '2', 'private'),
    'S-SCREENS': ('Approved screen list (design approval 13 Nov 2026)', 'sources/screens-approved.md', '2026-11-13', 'private'),
    'S-AUDIT': ('End-to-end flow audit and decisions', 'sources/flow-audit.md', '2026-11-13', 'private'),
    'S-BACKEND': ('Observed backend inventory', 'sources/backend-inventory.md', '2026-11-13', 'private'),
    'S-DECISIONS': ('Decisions relayed 13 Nov 2026', 'sources/decisions-2026-11-13.md', '2026-11-13', 'private'),
}
def sha(p): return hashlib.sha256(open(os.path.join(HERE, p), 'rb').read()).hexdigest()
sources = [{'id': k, 'title': t, 'path': p, 'version': v, 'classification': c, 'sha256': sha(p)} for k, (t, p, v, c) in SRC.items()]

# ---------------------------------------------------------------- payload helpers
S = lambda **kw: dict({'type': 'string', 'minLength': 1}, **kw)
I = lambda **kw: dict({'type': 'integer', 'minimum': 0}, **kw)
B = {'type': 'boolean'}
def O(props, req=None, extra=False):
    return {'type': 'object', 'properties': props, 'required': req if req is not None else list(props), 'additionalProperties': extra}
def A(item): return {'type': 'array', 'items': item}
NULLABLE_STR = {'type': 'string', 'description': 'Empty string is never used for unknown; the field is omitted and "unknown" listed instead.'}
ERROR = O({'code': S(), 'message': S()})
STATE = S(enum=['ready', 'processing', 'waiting', 'owner_needed', 'setup_needed', 'action_needed', 'effect_uncertain', 'awaiting_reconciliation', 'verified', 'cancelled', 'followup_needed'])
WORK_ROW = O({'id': S(), 'title': S(), 'line': S(), 'reference': S(), 'kind': S(enum=['decide', 'do', 'fix', 'started']), 'state': STATE,
              'station': O({'index': I(minimum=1), 'count': I(minimum=1), 'name': S()}), 'waiting_on': S(), 'age_seconds': I(), 'sample': B})
FACT = O({'name': S(enum=['drafted', 'reviewed', 'approved', 'sent', 'receipt_recorded', 'verified']), 'status': S(enum=['earned', 'current', 'not_yet', 'unknown']), 'at': S(format='date-time')}, ['name', 'status'])
MONEY = O({'amount': S(pattern='^-?[0-9]+\\.[0-9]{2}$', description='Decimal string; absent when unknown'), 'currency': S(pattern='^[A-Z]{3}$'), 'unknown': B}, ['currency', 'unknown'])
ok = lambda d, s: {'status': '200', 'description': d, 'schema': s}
created = lambda d, s: {'status': '201', 'description': d, 'schema': s}
err = lambda st, d: {'status': st, 'description': d, 'schema': ERROR}
STD_READ = [err('401', 'Not signed in'), err('403', 'No grant for this record'), err('404', 'Not found or not visible')]
STD_WRITE = STD_READ + [err('409', 'Stale revision: the record changed; reload and act on the current version'), err('422', 'Validation failed; fields named in message')]
P = lambda name, where='path', req=True, schema=None: {'name': name, 'in': where, 'required': req, 'schema': schema or S()}
EXPECTED = {'expected_revision': I(minimum=1)}

# ---------------------------------------------------------------- requirements (cite scope IDs)
REQ = [
    ('R-SESSION', 'Sign in once and see only what the role allows', 'endpoint', 'confirmed', 'C-05, R-04, U-01..U-08', 'E-ME / A-ME'),
    ('R-MYWORK', 'My work: three queues with Decide, Do or Fix on each row', 'endpoint', 'confirmed', 'J-01, J-02, G-01', 'E-WORK-LIST / A-MYWORK'),
    ('R-WORKITEM', 'Work item: stations, separate facts, state, agent steps, history', 'endpoint', 'confirmed', 'J-01, S-04, R-01, R-02, R-03', 'E-WORK-ITEM, E-WORK-HISTORY / A-WORKITEM, A-HISTORY'),
    ('R-DECIDE', 'Approve, return, reject or withdraw one exact version', 'endpoint', 'confirmed', 'J-02, G-04, R-04', 'E-TASK-CLAIM, E-TASK-DECIDE / A-DECIDE, A-STALE'),
    ('R-START', 'Start work on any line the person may start', 'endpoint', 'confirmed', 'J-01, S-03', 'E-LINES, E-WORK-START / A-START'),
    ('R-RESPONSE', 'Record an outside response or team input with proof', 'endpoint', 'confirmed', 'J-03, S-07, U-09', 'E-EVIDENCE-UPLOAD, E-RESPONSE / A-RESPONSE'),
    ('R-EXCEPTION', 'Deal with effect uncertain, owner needed and setup needed', 'endpoint', 'confirmed', 'J-05, J-07, R-07', 'E-WORK-ACTION, E-EXCEPTIONS / A-RECONCILE, A-RESUME'),
    ('R-PROJECT', 'Project journey, milestones, documents, money, registers and actions', 'endpoint', 'confirmed', 'J-08, J-04, R-05', 'E-PROJECTS, E-PROJECT, E-PROJECT-TAB, E-DOCUMENT / A-PROJECT'),
    ('R-OVERVIEW', 'Factory floor and everyone\'s exceptions for Leads', 'endpoint', 'confirmed', 'S-05, J-05', 'E-OVERVIEW, E-EXCEPTIONS / A-OVERVIEW'),
    ('R-FINANCE', 'Month-end, imports, Finance back-office lines and payroll (restricted)', 'endpoint', 'confirmed', 'J-04, J-06', 'E-MONTH-END, E-IMPORT, E-PAYROLL-MATCH / A-MONTHEND, A-PAYROLL'),
    ('R-SETUP', 'Setup: people, rules (Not set), delegation and templates', 'endpoint', 'confirmed', 'J-07, U-02, U-04, U-06', 'E-SETUP-RULES, E-SETUP-RULE-SAVE, E-PEOPLE, E-DELEGATION, E-TEMPLATES / A-SETUP'),
    ('R-ALERTS', 'Notification centre and own alert preferences', 'endpoint', 'confirmed', 'J-09, S-06, I-03', 'E-NOTIFICATIONS, E-ALERT-PREFS / A-ALERTS'),
    ('R-ASSISTANT', 'Assistant answers with sources and makes drafts that start their normal line', 'endpoint', 'confirmed', 'J-10, J-11, S-10, R-08', 'E-CONVERSATION-NEW, E-MESSAGE, E-CONVERSATION / A-ASSISTANT'),
    ('R-REPORTS', 'Leadership and project reports with drill-down to records', 'endpoint', 'confirmed', 'S-03', 'E-REPORT / A-REPORT'),
    ('R-FRONTEND', 'Next.js frontend in frontend/ built from the approved design system', 'non_endpoint', 'confirmed', 'S-01, S-08, G-03, C-05', 'Covered by T-FRONTEND-SHELL and V-DEPLOY; acceptance A-ACCESSIBILITY'),
    ('R-DEVICES', 'Phone, tablet and desktop; WCAG 2.2 AA; latest two browser versions', 'non_endpoint', 'confirmed', 'C-01, C-02, C-03', 'Covered by T-FRONTEND-SHELL acceptance A-ACCESSIBILITY'),
    ('R-MOTION', 'Factory floor 3D and motion; reduced motion respected', 'non_endpoint', 'confirmed', 'S-05, C-04', 'Covered by T-FLOOR acceptance A-OVERVIEW'),
    ('R-SAMPLE', 'Sample, test and mock data visibly labelled', 'non_endpoint', 'confirmed', 'R-06, S-09', 'Every list payload carries sample; INV-SAMPLE; A-MYWORK'),
    ('R-VOLUME', 'High volume: many projects, invoices and decisions at once', 'non_endpoint', 'confirmed', 'C-06', 'Paged list endpoints (limit 50, cursor); D-PAGING; A-MYWORK'),
    ('R-ROLES', 'Role decisions from 13 Nov: PMO Lead is Head of PMO; approvals PM, PMO Lead, CEO; CEO and CTO may start any line', 'non_endpoint', 'confirmed', 'U-02, U-07, U-08', 'Covered by T-BACKEND-ROLES and decisions D-ROLE-PMO, D-APPROVAL-ORDER, D-LEADERS-START'),
]
requirements = [{'id': i, 'title': t + ' (' + cite + ')', 'refs': [], 'evidence': ['S-SCOPE', 'S-SCREENS'] + (['S-DECISIONS'] if i == 'R-ROLES' else []), 'status': st, 'kind': k, 'coverage': cov} for i, t, k, st, cite, cov in REQ]

# ---------------------------------------------------------------- decisions
def dec(i, title, owner, scope, status, choice, rationale, alts, refs, ev=('S-BACKEND',)):
    return {'id': i, 'title': title, 'refs': refs, 'evidence': list(ev), 'owner': owner, 'scope': scope,
            'revisions': [{'revision': 1, 'status': status, 'choice': choice, 'rationale': rationale, 'alternatives': alts, 'evidence': list(ev)}]}
decisions = [
    dec('D-API-STYLE', 'How the data API is built', 'technical reviewer', 'All /api/v1 endpoints', 'proposed',
        'Plain Django JSON views under /api/v1 in a new apps/api package that call the existing service functions; no new framework.',
        'Every write already goes through service functions with expected revisions; a thin JSON layer reuses them and adds no dependency.',
        ['Add Django REST framework', 'Separate API service'], ['R-SESSION']),
    dec('D-AUTH', 'Sign-in and session for the frontend', 'technical reviewer', 'All endpoints', 'proposed',
        'Same-origin deployment: the Next.js app and /api/v1 are served behind one host; the Django session cookie authenticates; writes send the CSRF token header.',
        'C-05 says people sign in once and Django keeps login; same origin avoids CORS and token storage in the browser.',
        ['Separate origins with CORS and credentials', 'Token or JWT login'], ['R-SESSION'], ('S-BACKEND', 'S-SCOPE')),
    dec('D-HOSTING', 'Where the frontend and API run', 'release authority', 'Deployment', 'open',
        'Not chosen. Needed before the first release, not before local development.',
        'No deployment is authorised in this phase.', ['Node server behind the same reverse proxy as Django', 'Static export served by Django'], ['R-FRONTEND'], ('S-SCOPE',)),
    dec('D-UPDATES', 'How screens stay current', 'technical reviewer', 'My work, work item, overview', 'proposed',
        'Polling: lists every 15 seconds while visible, an open work item every 5 seconds while an agent is working; no push channel in v1.',
        'Simple and works with session auth and the existing request model; push can follow if volume demands it.',
        ['Server-sent events', 'WebSockets'], ['R-MYWORK', 'R-WORKITEM']),
    dec('D-PAGING', 'List paging', 'technical reviewer', 'All list endpoints', 'proposed',
        'Cursor paging, 50 rows per page, newest activity first; counts per queue returned separately.',
        'C-06 high volume; matches the "Show more" pattern in the design.', ['Offset paging'], ['R-VOLUME']),
    dec('D-NOTIFY-MODEL', 'Store notifications and alert preferences', 'technical reviewer', 'Alerts', 'proposed',
        'Add Notification (per person, per work item event) and AlertPreference (channel WhatsApp/email/both, frequency) records; sends go through the existing outbox to a mock adapter until I-03 is connected.',
        'No notification or preference model exists; the outbox pattern already handles uncertain sends.', ['In-app only for v1'], ['R-ALERTS']),
    dec('D-ALERT-PROVIDERS', 'WhatsApp and email providers', 'business owner', 'I-WHATSAPP, I-EMAIL', 'open',
        'Not chosen; PSL owns the accounts (I-03). Built against a mock adapter until chosen.',
        'Accounts, templates and opt-in belong to PSL.', ['WhatsApp Business via a provider such as Meta Cloud API', 'Email via an SMTP or API provider'], ['R-ALERTS'], ('S-SCOPE',)),
    dec('D-CONVERSATION-MODEL', 'Store assistant conversations', 'technical reviewer', 'Assistant', 'proposed',
        'Add Conversation and Message records per person; each assistant answer stores the records it cited and the agent run it came from; drafts are created only through the normal line start.',
        'No conversation model exists; R-08 requires sources on every answer and drafts in their normal line.', ['Stateless assistant'], ['R-ASSISTANT']),
    dec('D-AGENT-PROVIDER', 'Language model provider for agents and the assistant', 'business owner', 'I-AGENT', 'open',
        'Not chosen. Real cases refuse unapproved providers today; the synthetic provider is used until approval.',
        'Live AI activation is not authorised in this phase.', ['Anthropic Claude via API'], ['R-ASSISTANT'], ('S-BACKEND', 'S-SCOPE')),
    dec('D-ROLE-PMO', 'Head of PMO is the PMO Lead', 'business owner', 'Closure decisions, commercial approvals, escalations', 'approved',
        'One role, PMO Lead. Backend lookups of a separate "Head of PMO" role map to PMO Lead.',
        'Confirmed by PSL through the design engineer on 13 Nov 2026.', ['Two separate roles'], ['R-ROLES'], ('S-DECISIONS', 'S-AUDIT')),
    dec('D-APPROVAL-ORDER', 'Commercial approval order', 'business owner', 'Costing and commercial line', 'approved',
        'PM, then PMO Lead, then CEO; the CEO approves last. Replaces PM, Head of PMO, CEO, PMO Lead.',
        'Confirmed by PSL through the design engineer on 13 Nov 2026.', ['Four approvals'], ['R-ROLES'], ('S-DECISIONS',)),
    dec('D-LEADERS-START', 'CEO and CTO may start every line', 'business owner', 'Start work', 'approved',
        'Grant the CEO and CTO the start permission on every line; their Start work opens the full menu. No approval step is added for anyone else.',
        'Decided by the design engineer on 13 Nov 2026.', ['Hide Start work for leaders'], ['R-ROLES'], ('S-DECISIONS',)),
    dec('D-RETURN', 'What "return" does on each line', 'business owner', 'Decisions on all lines', 'open',
        'Proposed for review: every return creates a "correct and resubmit" task for the preparer. Today accounts, the shared engine and schedules differ.',
        'Raised in the Finance audit.', ['Keep per-line behaviour'], ['R-DECIDE'], ('S-DECISIONS', 'S-AUDIT')),
    dec('D-FIRST-FEATURE', 'First feature to deliver', 'delivery owner', 'Delivery order', 'proposed',
        'My work and one decision end to end (J-01 view, J-02): session and identity, the three queues, the work item with history, claim and decide with stale-version handling; desktop and phone.',
        'Smallest slice that exercises the API seam, permissions, revisions and the design system on real records.',
        ['Start work first', 'Factory floor first'], ['R-MYWORK', 'R-DECIDE'], ('S-SCREENS', 'S-SCOPE')),
]

# ---------------------------------------------------------------- components
def comp(i, t, kind, tb, resp, owner, ev=('S-BACKEND',)):
    return {'id': i, 'title': t, 'refs': [], 'evidence': list(ev), 'kind': kind, 'trust_boundary': tb, 'responsibilities': resp, 'owner': owner}
components = [
    comp('C-STAFF', 'PSL staff (PMO, Finance, HR, Leads, CEO, CTO)', 'actor', 'Untrusted browser or phone', 'Use the factory through the frontend; sign in once.', 'operator', ('S-SCOPE',)),
    comp('C-FRONTEND', 'Next.js frontend (frontend/)', 'application', 'Untrusted browser; same-origin', 'Render the approved screens with the design system, GSAP motion and the three.js floor; call /api/v1 only; hold no business rules.', 'developer', ('S-SCOPE', 'S-SCREENS')),
    comp('C-API', 'Data API (apps/api, /api/v1)', 'module', 'Django application boundary; session + CSRF', 'Translate requests to existing service calls; check grants per record and action; shape JSON for screens.', 'developer'),
    comp('C-SERVICES', 'Domain services (workflows, pmo, finance, documents, identity, policy)', 'module', 'Django application boundary', 'Own every business rule, revision check, approval and audit event.', 'developer'),
    comp('C-WORKERS', 'Job workers (work_* commands)', 'application', 'Private server', 'Run factory steps, agent work, publications and the outbox from leased job tables.', 'developer'),
    comp('C-DB', 'PostgreSQL', 'store', 'Private persistence', 'Records, append-only audit, job tables.', 'developer'),
    comp('C-ALERTS', 'Alert adapter (mock until providers chosen)', 'module', 'Private server; provider secrets server-only', 'Send WhatsApp and email alerts from the outbox; record receipts and uncertain sends.', 'developer', ('S-SCOPE',)),
    comp('C-AGENTS', 'Agent coordinator (Tola, Chidi, Zainab)', 'module', 'Private server; provider credentials server-only', 'Run agent steps and assistant answers on records the requester may see; never approve, send or pay.', 'developer'),
]

# ---------------------------------------------------------------- records
def rec(i, t, fields, cons, owner, rel=()):
    return {'id': i, 'title': t, 'refs': [], 'evidence': ['S-BACKEND'], 'fields': fields, 'relationships': list(rel), 'constraints': cons, 'owner': owner}
records = [
    rec('REC-CASE', 'Case (project or support)', ['id: uuid', 'kind: project|support', 'title', 'revision'], ['Visible only with a case.read grant'], 'core'),
    rec('REC-GRANT', 'Grant (case, user, action)', ['case', 'user', 'action', 'active'], ['UNIQUE(case, user, action) while active'], 'identity', ['REC-CASE']),
    rec('REC-WORK', 'Factory work item', ['id', 'case', 'key', 'definition (line/version)', 'request', 'status', 'revision', 'cancel_requested'], ['revision increases on every change', 'status in the factory state set'], 'workflows', ['REC-CASE']),
    rec('REC-TASK', 'Human task (decision or recording)', ['id', 'factory_key', 'kind', 'required_role', 'claimed_by', 'revision', 'status'], ['A decision names one exact document version', 'Preparer cannot decide own work where separation applies'], 'workflows', ['REC-WORK']),
    rec('REC-EVIDENCE', 'Evidence (proof, response, upload)', ['id', 'case', 'kind', 'body', 'source', 'sha256'], ['Append-only'], 'core', ['REC-CASE']),
    rec('REC-AUDIT', 'Audit event', ['id', 'case', 'actor', 'action', 'at', 'detail'], ['Append-only; corrections are new events'], 'core', ['REC-CASE']),
    rec('REC-AGENTRUN', 'Agent run', ['id', 'agent', 'work', 'steps', 'records_read', 'status'], ['Never records an approval'], 'agents', ['REC-WORK']),
    rec('REC-DOCUMENT', 'Document and version', ['id', 'case', 'template', 'version', 'status'], ['Decisions bind to a version'], 'documents', ['REC-CASE']),
    rec('REC-MONEY', 'Invoice, receipt and allocation', ['invoice: amount, status, issue, delivery', 'receipt: amount, date', 'allocation'], ['Stages, invoices, receipts and allocations are separate', 'Unknown amounts are not zero'], 'finance', ['REC-CASE']),
    rec('REC-CONFIG', 'Versioned configuration (rules)', ['case', 'component', 'revision', 'envelope'], ['A missing value is Not set, never a default'], 'policy', ['REC-CASE']),
    rec('REC-NOTIFICATION', 'Notification (new)', ['id', 'person', 'work', 'event', 'created_at', 'read_at', 'channel_status'], ['One per person per event', 'Carries no amounts or client details'], 'apps/api (new)', ['REC-WORK']),
    rec('REC-ALERT-PREF', 'Alert preference (new)', ['person', 'channel: whatsapp|email|both|none', 'frequency: immediate|daily'], ['One per person'], 'apps/api (new)', []),
    rec('REC-CONVERSATION', 'Assistant conversation and message (new)', ['id', 'person', 'messages: role, text, sources[], agent_run'], ['Every assistant message lists its sources', 'Drafts link to a started work item, never a finished one'], 'agents (new)', ['REC-AGENTRUN']),
]

# ---------------------------------------------------------------- invariants
def inv(i, t, rule, scope, refs): return {'id': i, 'title': t, 'refs': refs, 'evidence': ['S-SCOPE', 'S-BACKEND'], 'rule': rule, 'scope': scope}
invariants = [
    inv('INV-ACCESS', 'Every record and action is checked by the backend', 'Each endpoint resolves the case and calls require(actor, case, action) or the line\'s authority check before reading or writing; lists filter by grants.', 'All endpoints', ['REC-GRANT', 'A-ME', 'A-MYWORK', 'A-PAYROLL']),
    inv('INV-REVISION', 'Act only on the current version', 'Writes carry expected_revision; a mismatch returns 409 and changes nothing.', 'All writes', ['REC-WORK', 'REC-TASK', 'A-STALE', 'A-SETUP']),
    inv('INV-FACTS', 'Facts are never merged', 'Payloads return drafted, reviewed, approved, sent, receipt recorded and verified as separate facts; paid is separate Finance data.', 'Work item, money', ['REC-WORK', 'REC-MONEY', 'A-WORKITEM', 'A-PROJECT']),
    inv('INV-UNKNOWN', 'Unknown is not zero', 'Amounts and dates that are not known are returned with unknown=true and no value.', 'All payloads with amounts or dates', ['REC-MONEY', 'A-WORKITEM', 'A-MONTHEND', 'A-REPORT']),
    inv('INV-AGENT', 'Agents never decide', 'Agent runs can draft, read and explain; decision, send and pay endpoints reject agent actors.', 'Decisions, assistant', ['REC-AGENTRUN', 'REC-TASK', 'A-WORKITEM', 'A-ASSISTANT']),
    inv('INV-RESEND', 'Check before resending', 'A send with an unknown outcome blocks any new send until reconciled.', 'Deliveries, alerts', ['REC-WORK', 'REC-NOTIFICATION', 'A-RECONCILE']),
    inv('INV-AUDIT', 'History is append-only', 'Every write adds an audit event; nothing edits or deletes one.', 'All writes', ['REC-AUDIT', 'A-HISTORY', 'A-DECIDE']),
    inv('INV-RESTRICTED', 'Payroll rows stay with HR', 'Individual payroll rows are returned only to roles with payroll private read; others get totals.', 'Payroll, BU totals', ['REC-GRANT', 'A-PAYROLL', 'A-ASSISTANT']),
    inv('INV-SAMPLE', 'Sample data is labelled', 'Records from synthetic or demo cases carry sample=true in every payload.', 'All payloads', ['REC-CASE', 'A-MYWORK']),
]

# ---------------------------------------------------------------- endpoints
# (id, method, path, title, trigger, permission, handler, service, requirement, records, invariants, decisions, task, scenario, params, request, ok-response)
LIST = lambda item, extra=None: O(dict({'items': A(item), 'next_cursor': {'type': 'string'}, 'as_of': S(format='date-time')}, **(extra or {})), ['items', 'as_of'])
QUEUE_COUNTS = O({'needs_me': I(), 'waiting_on_others': I(), 'done': I(), 'unassigned': I()}, ['needs_me', 'waiting_on_others', 'done'])
EP = [
 ('E-ME', 'GET', '/api/v1/me', 'Who I am and what I may use', 'App load', 'Signed in.', 'api.me.read', 'identity.services', 'R-SESSION', ['REC-GRANT'], ['INV-ACCESS'], ['D-AUTH', 'D-API-STYLE'], 'T-FOUNDATION', 'A-ME', [], None,
  O({'name': S(), 'roles': A(S()), 'destinations': A(S(enum=['my_work', 'projects', 'overview', 'assistant', 'setup'])), 'startable_lines': A(S()), 'csrf_token': S()})),
 ('E-WORK-LIST', 'GET', '/api/v1/work', 'My work queue', 'My work page, queue tab, search, filter', 'Signed in; rows filtered by grants.', 'api.work.list', 'workflows.factory.snapshot', 'R-MYWORK', ['REC-WORK', 'REC-TASK'], ['INV-ACCESS', 'INV-SAMPLE'], ['D-PAGING', 'D-UPDATES'], 'T-MYWORK', 'A-MYWORK',
  [P('queue', 'query', True, S(enum=['needs_me', 'waiting_on_others', 'done', 'unassigned'])), P('q', 'query', False), P('line', 'query', False), P('state', 'query', False), P('cursor', 'query', False)], None,
  LIST(WORK_ROW, {'counts': QUEUE_COUNTS})),
 ('E-WORK-ITEM', 'GET', '/api/v1/work/{work_id}', 'One work item', 'Open a row or an alert link', 'case.read plus the line\'s read permission.', 'api.work.read', 'workflows.factory.snapshot', 'R-WORKITEM', ['REC-WORK', 'REC-TASK', 'REC-AGENTRUN', 'REC-DOCUMENT'], ['INV-ACCESS', 'INV-FACTS', 'INV-UNKNOWN', 'INV-AGENT', 'INV-SAMPLE'], ['D-UPDATES'], 'T-WORKITEM', 'A-WORKITEM', [P('work_id')], None,
  O({'id': S(), 'title': S(), 'line': S(), 'reference': S(), 'state': STATE, 'revision': I(minimum=1), 'stations': A(O({'name': S(), 'status': S(enum=['done', 'current_person', 'current_agent', 'waiting', 'stopped', 'not_started', 'verified'])})),
     'facts': A(FACT), 'tasks': A(O({'id': S(), 'kind': S(), 'title': S(), 'required_role': S(), 'you_can_act': B, 'revision': I(minimum=1)})), 'agent': O({'name': S(), 'status': S(enum=['working', 'done', 'waiting', 'stopped', 'none']), 'steps': A(O({'text': S(), 'status': S(), 'source': {'type': 'string'}}, ['text', 'status']))}, ['status']),
     'next_step': S(), 'sample': B}, ['id', 'title', 'line', 'reference', 'state', 'revision', 'stations', 'facts', 'tasks', 'agent', 'next_step', 'sample'])),
 ('E-WORK-HISTORY', 'GET', '/api/v1/work/{work_id}/history', 'Work item history', 'History tab', 'Same as reading the work item; restricted entries returned as Restricted.', 'api.work.history', 'core.Audit query', 'R-WORKITEM', ['REC-AUDIT', 'REC-TASK'], ['INV-ACCESS', 'INV-AUDIT', 'INV-RESTRICTED'], [], 'T-WORKITEM', 'A-HISTORY', [P('work_id'), P('kind', 'query', False, S(enum=['all', 'decisions', 'agent_work', 'evidence'])), P('cursor', 'query', False)], None,
  LIST(O({'at': S(format='date-time'), 'actor_kind': S(enum=['person', 'agent', 'factory']), 'actor': S(), 'event': S(), 'version': {'type': 'string'}, 'detail': {'type': 'string'}, 'restricted': B}, ['at', 'actor_kind', 'actor', 'event', 'restricted']))),
 ('E-TASK-CLAIM', 'POST', '/api/v1/tasks/{task_id}/claim', 'Claim a task', 'Open a decision you are eligible for', 'Eligible role for the task; not the preparer where separation applies.', 'api.tasks.claim', 'workflows.factory.claim_task', 'R-DECIDE', ['REC-TASK'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], [], 'T-DECIDE', 'A-DECIDE', [P('task_id')], O(EXPECTED),
  O({'task_id': S(), 'revision': I(minimum=1), 'claimed_by': S()})),
 ('E-TASK-DECIDE', 'POST', '/api/v1/tasks/{task_id}/decision', 'Decide one exact version', 'Approve, Return, Reject or Withdraw approval', 'Claimed eligible role; agents rejected.', 'api.tasks.decide', 'workflows.factory.decide', 'R-DECIDE', ['REC-TASK', 'REC-WORK', 'REC-EVIDENCE'], ['INV-ACCESS', 'INV-REVISION', 'INV-AGENT', 'INV-AUDIT'], [], 'T-DECIDE', 'A-DECIDE', [P('task_id')],
  O(dict(EXPECTED, verdict=S(enum=['approve', 'return', 'reject', 'revoke']), note={'type': 'string', 'description': 'Up to 2000 characters; required to return, reject or withdraw'}, evidence_id={'type': 'string'}), ['expected_revision', 'verdict']),
  O({'task_id': S(), 'verdict': S(), 'decided_by': S(), 'decided_at': S(format='date-time'), 'work_state': STATE})),
 ('E-LINES', 'GET', '/api/v1/lines', 'Lines I can start and their intake', 'Start work menu', 'Signed in; only lines with factory.start for the person.', 'api.lines.list', 'workflows.factory_definitions', 'R-START', ['REC-GRANT'], ['INV-ACCESS'], ['D-LEADERS-START'], 'T-START', 'A-START', [], None,
  LIST(O({'key': S(), 'title': S(), 'group': S(), 'intake': A(O({'name': S(), 'label': S(), 'type': S(), 'required': B}))}))),
 ('E-WORK-START', 'POST', '/api/v1/work', 'Start a line', 'Start work drawer submit', 'factory.start on the case and the line\'s start permission.', 'api.work.start', 'workflows.factory.start', 'R-START', ['REC-WORK', 'REC-EVIDENCE'], ['INV-ACCESS', 'INV-AUDIT', 'INV-REVISION'], ['D-LEADERS-START'], 'T-START', 'A-START', [],
  O({'line': S(), 'case_id': S(), 'case_revision': I(minimum=1), 'intake': {'type': 'object', 'additionalProperties': True}, 'idempotency_key': S()}),
  {'type': 'object', 'properties': {'work_id': S(), 'state': STATE}, 'required': ['work_id', 'state'], 'additionalProperties': False}),
 ('E-EVIDENCE-UPLOAD', 'POST', '/api/v1/cases/{case_id}/evidence', 'Upload proof', 'File drop in a form', 'evidence.add on the case.', 'api.evidence.upload', 'core.services.add_evidence', 'R-RESPONSE', ['REC-EVIDENCE'], ['INV-ACCESS', 'INV-AUDIT'], [], 'T-RESPONSE', 'A-RESPONSE', [P('case_id')],
  O({'kind': S(), 'filename': S(), 'content_base64': S(), 'case_revision': I(minimum=1)}),
  O({'evidence_id': S(), 'sha256': S(pattern='^[0-9a-f]{64}$')})),
 ('E-RESPONSE', 'POST', '/api/v1/tasks/{task_id}/response', 'Record an outside response', 'Record a response form', 'Task recording role (PMO for client and team responses).', 'api.tasks.response', 'workflows.factory.provide_information', 'R-RESPONSE', ['REC-TASK', 'REC-EVIDENCE'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], [], 'T-RESPONSE', 'A-RESPONSE', [P('task_id')],
  O(dict(EXPECTED, who=S(), action=S(enum=['approved', 'changes_requested', 'signed', 'rejected', 'estimate', 'input']), responded_at=S(format='date-time'), evidence_id=S(), attested=B)),
  O({'task_id': S(), 'work_state': STATE})),
 ('E-WORK-ACTION', 'POST', '/api/v1/work/{work_id}/actions', 'Resume, cancel or reconcile', 'Exception actions', 'Operator authority on the line; reconcile needs the line\'s recovery authority.', 'api.work.action', 'workflows.factory.manage / reconcile', 'R-EXCEPTION', ['REC-WORK', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-RESEND', 'INV-AUDIT'], [], 'T-EXCEPTIONS', 'A-RECONCILE', [P('work_id')],
  O(dict(EXPECTED, action=S(enum=['resume', 'cancel', 'reconcile']), outcome={'type': 'string', 'enum': ['delivered', 'not_delivered', 'unknown']}, evidence_id={'type': 'string'}), ['expected_revision', 'action']),
  O({'work_id': S(), 'state': STATE, 'revision': I(minimum=1)})),
 ('E-EXCEPTIONS', 'GET', '/api/v1/exceptions', 'All exceptions', 'Overview and All exceptions page', 'Leads; filtered by grants.', 'api.exceptions.list', 'workflows.factory.snapshot', 'R-EXCEPTION', ['REC-WORK'], ['INV-ACCESS'], ['D-PAGING'], 'T-EXCEPTIONS', 'A-RESUME', [P('cursor', 'query', False)], None,
  LIST(O({'work_id': S(), 'what': S(enum=['effect_uncertain', 'owner_needed', 'setup_needed', 'blocked', 'followup_needed']), 'title': S(), 'doing': S(), 'who_acts': S(), 'since': S(format='date-time')}))),
 ('E-PROJECTS', 'GET', '/api/v1/projects', 'Projects list', 'Projects page', 'case.read.', 'api.projects.list', 'identity.services.visible_cases', 'R-PROJECT', ['REC-CASE'], ['INV-ACCESS', 'INV-SAMPLE'], ['D-PAGING'], 'T-PROJECTS', 'A-PROJECT', [P('q', 'query', False), P('cursor', 'query', False)], None,
  LIST(O({'case_id': S(), 'title': S(), 'pm': S(), 'stage': S(), 'sample': B}))),
 ('E-PROJECT', 'GET', '/api/v1/projects/{case_id}', 'Project journey', 'Open a project', 'case.read.', 'api.projects.read', 'pmo services', 'R-PROJECT', ['REC-CASE', 'REC-WORK'], ['INV-ACCESS', 'INV-FACTS'], [], 'T-PROJECTS', 'A-PROJECT', [P('case_id')], None,
  O({'case_id': S(), 'title': S(), 'lines': A(O({'line': S(), 'state': STATE, 'work_id': S()})), 'next': S()})),
 ('E-PROJECT-TAB', 'GET', '/api/v1/projects/{case_id}/{tab}', 'Project tab', 'Milestones, Documents, Money, Registers, Actions tabs', 'case.read plus the tab\'s read permission (finance.read for Money).', 'api.projects.tab', 'pmo / finance / documents services', 'R-PROJECT', ['REC-CASE', 'REC-MONEY', 'REC-DOCUMENT'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-FACTS'], ['D-PAGING'], 'T-PROJECTS', 'A-PROJECT',
  [P('case_id'), P('tab', 'path', True, S(enum=['milestones', 'documents', 'money', 'registers', 'actions']))], None,
  LIST({'type': 'object', 'additionalProperties': True, 'description': 'Row shape per tab, documented in handoff'})),
 ('E-DOCUMENT', 'GET', '/api/v1/documents/{document_id}/versions/{version}', 'Read a document version', 'Document review', 'case.read and document read.', 'api.documents.read', 'documents services', 'R-PROJECT', ['REC-DOCUMENT'], ['INV-ACCESS', 'INV-SAMPLE'], [], 'T-PROJECTS', 'A-PROJECT', [P('document_id'), P('version')], None,
  O({'document_id': S(), 'version': S(), 'title': S(), 'status': S(), 'template': S(), 'body_url': S(), 'test_template': B})),
 ('E-OVERVIEW', 'GET', '/api/v1/overview', 'Factory floor', 'Overview page', 'Leads, CEO, CTO; counts from visible records.', 'api.overview.read', 'workflows.factory.snapshot', 'R-OVERVIEW', ['REC-WORK'], ['INV-ACCESS'], ['D-UPDATES'], 'T-FLOOR', 'A-OVERVIEW', [], None,
  O({'as_of': S(format='date-time'), 'totals': O({'in_progress': I(), 'need_a_person': I(), 'stopped': I(), 'verified_this_month': I()}), 'lines': A(O({'line': S(), 'stations': A(O({'name': S(), 'count': I(), 'needs_person': B})), 'note': S()}))})),
 ('E-MONTH-END', 'GET', '/api/v1/finance/month-end', 'Month-end checklist', 'Month-end page', 'finance.read.', 'api.finance.month_end', 'finance services', 'R-FINANCE', ['REC-MONEY', 'REC-WORK'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-RESTRICTED'], [], 'T-FINANCE', 'A-MONTHEND', [P('period', 'query', True, S(pattern='^[0-9]{4}-[0-9]{2}$'))], None,
  O({'period': S(), 'tasks': A(O({'line': S(), 'state': STATE, 'where': S(), 'work_id': {'type': 'string'}}, ['line', 'state', 'where'])), 'cash_received': MONEY})),
 ('E-IMPORT', 'POST', '/api/v1/cases/{case_id}/finance/imports', 'Submit an accounting or bank file', 'Import and reconcile, accounts start form', 'finance.import, finance.validate, evidence.add.', 'api.finance.import', 'workflows.factory_accounting_intake', 'R-FINANCE', ['REC-EVIDENCE', 'REC-WORK'], ['INV-ACCESS', 'INV-AUDIT', 'INV-UNKNOWN'], [], 'T-FINANCE', 'A-MONTHEND', [P('case_id')],
  O({'evidence_id': S(), 'period': S(pattern='^[0-9]{4}-[0-9]{2}$'), 'currency': S(pattern='^[A-Z]{3}$'), 'completeness': S(enum=['complete', 'partial', 'unknown']), 'submission_key': S()}),
  O({'receipt': S(enum=['started', 'quarantined', 'configuration_needed', 'source_units_needed', 'followup_needed']), 'work_id': {'type': 'string'}, 'findings': A(S())}, ['receipt', 'findings'])),
 ('E-PAYROLL-MATCH', 'GET', '/api/v1/payroll/{work_id}/match', 'Payroll staff match (restricted)', 'Payroll match screen', 'payroll.read and payroll.private.read; HR roles only.', 'api.payroll.match', 'finance payroll services', 'R-FINANCE', ['REC-WORK'], ['INV-ACCESS', 'INV-RESTRICTED'], [], 'T-PAYROLL', 'A-PAYROLL', [P('work_id')], None,
  O({'matched': I(), 'unmatched': I(), 'conflicts': I(), 'rows': A(O({'staff': S(), 'payroll': MONEY, 'hr_record': S(), 'business_unit': S(), 'result': S()}))})),
 ('E-SETUP-RULES', 'GET', '/api/v1/setup/rules', 'Rules and their values', 'Setup rules, Finance rules', 'policy read for the area; Leads.', 'api.setup.rules', 'policy.services.resolve', 'R-SETUP', ['REC-CONFIG'], ['INV-ACCESS'], [], 'T-SETUP', 'A-SETUP', [P('area', 'query', False)], None,
  LIST(O({'component': S(), 'name': S(), 'value': {'type': 'object', 'additionalProperties': True}, 'set': B, 'revision': I()}, ['component', 'name', 'set', 'revision']))),
 ('E-SETUP-RULE-SAVE', 'PUT', '/api/v1/setup/rules/{component}', 'Save a rule as a new version', 'Setup rule form', 'policy.activate for the area.', 'api.setup.rule_save', 'policy.services.transition', 'R-SETUP', ['REC-CONFIG', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], [], 'T-SETUP', 'A-SETUP', [P('component')],
  O(dict(EXPECTED, value={'type': 'object', 'additionalProperties': True})), O({'component': S(), 'revision': I(minimum=1)})),
 ('E-PEOPLE', 'GET', '/api/v1/setup/people', 'People and roles', 'Setup people', 'Admin.', 'api.setup.people', 'identity services', 'R-SETUP', ['REC-GRANT'], ['INV-ACCESS'], ['D-PAGING'], 'T-SETUP', 'A-SETUP', [], None,
  LIST(O({'person': S(), 'roles': A(S()), 'active': B}))),
 ('E-DELEGATION', 'PUT', '/api/v1/setup/delegation', 'Set a delegate', 'Delegation form', 'Leads for their own authority.', 'api.setup.delegation', 'policy.role_assignments', 'R-SETUP', ['REC-CONFIG', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], [], 'T-SETUP', 'A-SETUP', [],
  O(dict(EXPECTED, delegate=S(), starts=S(format='date'), ends=S(format='date'))), O({'revision': I(minimum=1)})),
 ('E-TEMPLATES', 'GET', '/api/v1/setup/templates', 'Document templates', 'Setup templates', 'documents read.', 'api.setup.templates', 'documents services', 'R-SETUP', ['REC-DOCUMENT'], ['INV-ACCESS', 'INV-SAMPLE'], [], 'T-SETUP', 'A-SETUP', [], None,
  LIST(O({'line': S(), 'name': S(), 'version': S(), 'test_template': B}))),
 ('E-NOTIFICATIONS', 'GET', '/api/v1/notifications', 'Notification centre', 'Bell and notifications page', 'Own notifications only.', 'api.notifications.list', 'api notifications (new)', 'R-ALERTS', ['REC-NOTIFICATION'], ['INV-ACCESS'], ['D-NOTIFY-MODEL', 'D-PAGING'], 'T-ALERTS', 'A-ALERTS', [P('cursor', 'query', False)], None,
  LIST(O({'id': S(), 'work_id': S(), 'agent': S(), 'text': S(), 'at': S(format='date-time'), 'read': B}))),
 ('E-ALERT-PREFS', 'PUT', '/api/v1/me/alert-preferences', 'My alert preferences', 'Notification settings', 'Own preferences only.', 'api.me.alert_prefs', 'api notifications (new)', 'R-ALERTS', ['REC-ALERT-PREF', 'REC-AUDIT'], ['INV-ACCESS', 'INV-AUDIT'], ['D-NOTIFY-MODEL', 'D-ALERT-PROVIDERS'], 'T-ALERTS', 'A-ALERTS', [],
  O({'channel': S(enum=['whatsapp', 'email', 'both', 'none']), 'frequency': S(enum=['immediate', 'daily'])}), O({'channel': S(), 'frequency': S()})),
 ('E-CONVERSATION-NEW', 'POST', '/api/v1/assistant/conversations', 'Start a conversation', 'Assistant page, choose Tola, Chidi or Zainab', 'Signed in; the agent must serve the person\'s role.', 'api.assistant.new', 'agents (new)', 'R-ASSISTANT', ['REC-CONVERSATION'], ['INV-ACCESS', 'INV-AGENT'], ['D-CONVERSATION-MODEL'], 'T-ASSISTANT', 'A-ASSISTANT', [],
  O({'agent': S(enum=['tola', 'chidi', 'zainab'])}), O({'conversation_id': S()})),
 ('E-MESSAGE', 'POST', '/api/v1/assistant/conversations/{conversation_id}/messages', 'Ask the assistant', 'Send a message', 'Own conversation; answers use only records the person may read.', 'api.assistant.message', 'agents coordinator', 'R-ASSISTANT', ['REC-CONVERSATION', 'REC-AGENTRUN'], ['INV-ACCESS', 'INV-AGENT', 'INV-SAMPLE'], ['D-CONVERSATION-MODEL', 'D-AGENT-PROVIDER'], 'T-ASSISTANT', 'A-ASSISTANT', [P('conversation_id')],
  O({'text': S(description='Up to 4000 characters')}), O({'message_id': S(), 'agent_run_id': S(), 'status': S(enum=['working', 'answered', 'cannot_answer'])})),
 ('E-CONVERSATION', 'GET', '/api/v1/assistant/conversations/{conversation_id}', 'Read a conversation', 'Assistant page, polling while working', 'Own conversation.', 'api.assistant.read', 'agents (new)', 'R-ASSISTANT', ['REC-CONVERSATION', 'REC-AGENTRUN'], ['INV-ACCESS', 'INV-AGENT'], ['D-CONVERSATION-MODEL', 'D-UPDATES'], 'T-ASSISTANT', 'A-ASSISTANT', [P('conversation_id')], None,
  O({'conversation_id': S(), 'messages': A(O({'role': S(enum=['person', 'agent']), 'text': S(), 'steps': A(S()), 'sources': A(O({'kind': S(), 'reference': S(), 'restricted': B})), 'draft_work_id': {'type': 'string'}}, ['role', 'text', 'steps', 'sources']))})),
 ('E-REPORT', 'GET', '/api/v1/reports/{report_id}', 'Report with drill-down', 'Leadership and project reports', 'Report read; figures limited to visible records.', 'api.reports.read', 'pmo reporting services', 'R-REPORTS', ['REC-DOCUMENT', 'REC-MONEY'], ['INV-ACCESS', 'INV-UNKNOWN'], [], 'T-PROJECTS', 'A-REPORT', [P('report_id')], None,
  O({'report_id': S(), 'title': S(), 'figures': A(O({'label': S(), 'value': MONEY, 'sources': A(S())}))})),
]
endpoints = []
for (i, m, path, t, trig, perm, h, svc, req, recs, invs, decs, task, scen, params, reqbody, resp) in EP:
    write = m != 'GET'
    endpoints.append({'id': i, 'title': t, 'refs': [req] + recs + invs + decs + [task, scen], 'evidence': ['S-SCREENS', 'S-BACKEND'],
        'method': m, 'path': path, 'trigger': trig, 'security': ['Session', 'Csrf'] if write else ['Session'], 'permission': perm, 'parameters': params,
        'request': reqbody,
        'responses': [(created if i == 'E-WORK-START' else ok)(t, resp)] + (STD_WRITE if write else STD_READ),
        'handler': h, 'service': svc, 'local_work': 'Resolve the record, check grants and authority, call ' + svc + ('; write one audit event' if write else '') + '.',
        'integration_calls': [], 'failure_recovery': ('409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.' if write else 'Read-only; 404 hides records the person may not see.'),
        'implementation': 'unimplemented'})
# integration calls: alerts and agents
for e in endpoints:
    if e['id'] == 'E-NOTIFICATIONS': e['integration_calls'] = [{'integration': 'I-ALERTS', 'operation': 'queue_alert'}]
    if e['id'] == 'E-MESSAGE': e['integration_calls'] = [{'integration': 'I-AGENT', 'operation': 'run_assistant'}]

# ---------------------------------------------------------------- integrations and jobs
integrations = [
    {'id': 'I-ALERTS', 'title': 'WhatsApp and email alerts', 'refs': ['D-NOTIFY-MODEL', 'D-ALERT-PROVIDERS', 'T-ALERTS', 'JOB-ALERTS'], 'evidence': ['S-SCOPE', 'S-BACKEND'], 'provider': 'Not chosen (mock adapter)', 'selection': 'unresolved',
     'purpose': 'Tell people what is waiting for them (I-03).', 'data': 'Agent name, one line, work reference, app link; no amounts or client details.', 'secret_boundary': 'Provider credentials server-only; never in the frontend.',
     'failure_recovery': 'Outbox retries up to 3 times; an unknown send outcome is reconciled before any resend.',
     'operations': [{'name': 'queue_alert', 'relationship': 'queued_work', 'contract': 'From T-ALERTS on, decision and state changes (E-TASK-DECIDE, E-WORK-ACTION) write Notification rows and an outbox entry; E-NOTIFICATIONS lists them; JOB-ALERTS sends per preference.', 'authentication': 'Internal; no external call at queue time.', 'evidence': ['S-BACKEND']}]},
    {'id': 'I-AGENT', 'title': 'Agent language model provider', 'refs': ['D-AGENT-PROVIDER', 'T-ASSISTANT', 'JOB-ASSISTANT'], 'evidence': ['S-BACKEND', 'S-SCOPE'], 'provider': 'Not chosen (synthetic provider)', 'selection': 'unresolved',
     'purpose': 'Agent steps and assistant answers (S-10).', 'data': 'Only records the requesting person may read; payroll private rows never leave HR scope.', 'secret_boundary': 'Provider key server-only.',
     'failure_recovery': 'Agent run marked stopped with a reason; the person sees "cannot answer"; no record changes.',
     'operations': [{'name': 'run_assistant', 'relationship': 'queued_work', 'contract': 'E-MESSAGE stores the message and queues JOB-ASSISTANT; the worker calls the provider and stores the answer with sources.', 'authentication': 'Internal queue; provider call authenticated server-side when chosen.', 'evidence': ['S-BACKEND']}]},
]
jobs = [
    {'id': 'JOB-ALERTS', 'title': 'Send alerts', 'refs': ['REC-NOTIFICATION', 'REC-ALERT-PREF', 'INV-RESEND', 'I-ALERTS', 'T-ALERTS'], 'evidence': ['S-BACKEND'], 'trigger': 'Outbox entry from a notification', 'consumer': 'work_outbox (alert adapter)', 'retry_limit': 3,
     'recovery': 'After the limit, park and show the send as uncertain; reconcile before any resend.'},
    {'id': 'JOB-ASSISTANT', 'title': 'Answer an assistant message', 'refs': ['REC-CONVERSATION', 'REC-AGENTRUN', 'INV-AGENT', 'I-AGENT', 'T-ASSISTANT'], 'evidence': ['S-BACKEND'], 'trigger': 'Message stored by E-MESSAGE', 'consumer': 'agents coordinator worker', 'retry_limit': 2,
     'recovery': 'Mark the run stopped with a reason; the conversation shows cannot answer; the person may ask again.'},
]

# ---------------------------------------------------------------- journeys, views, scenarios, runbooks
J = lambda i, t, refs, ok_, bad: {'id': i, 'title': t, 'refs': refs, 'evidence': ['S-SCOPE', 'S-SCREENS'], 'success': ok_, 'failure': bad}
journeys = [
    J('JR-01', 'Start work to verified (J-01)', ['E-LINES', 'E-WORK-START', 'E-WORK-ITEM'], ['Open Start work', 'Fill intake', 'Line starts; follow it to verified'], ['Missing field: 422 names it', 'No permission: line not offered']),
    J('JR-02', 'Decide from an alert (J-02)', ['E-NOTIFICATIONS', 'E-WORK-ITEM', 'E-TASK-CLAIM', 'E-TASK-DECIDE'], ['Open alert link', 'Read the exact version', 'Approve, return or reject'], ['Version changed: 409, reload newer version', 'Not eligible: read-only view names the role']),
    J('JR-03', 'Record an outside response (J-03)', ['E-EVIDENCE-UPLOAD', 'E-RESPONSE'], ['Upload proof', 'Record who, what, when, attest'], ['No proof: 422']),
    J('JR-05', 'Clear an exception (J-05, J-07)', ['E-EXCEPTIONS', 'E-WORK-ACTION', 'E-SETUP-RULE-SAVE'], ['See exception', 'Reconcile or set the missing rule', 'Resume'], ['Outcome still unknown: stays held']),
    J('JR-06', 'Restricted payroll (J-06)', ['E-PAYROLL-MATCH'], ['HR reviews the match', 'Totals published'], ['Finance user: 403 on rows']),
    J('JR-08', 'Project journey (J-08)', ['E-PROJECTS', 'E-PROJECT', 'E-PROJECT-TAB'], ['Open project', 'See every line and what is next'], ['No grant: 404']),
    J('JR-10', 'Assistant (J-10, J-11)', ['E-CONVERSATION-NEW', 'E-MESSAGE', 'E-CONVERSATION'], ['Ask', 'See steps and sources', 'Start the drafted line'], ['No access to a record: cannot answer, says why']),
]
V = lambda i, t, kind, nodes, edges, notes: {'id': i, 'title': t, 'refs': nodes, 'evidence': ['S-BACKEND', 'S-SCOPE'], 'kind': kind, 'nodes': nodes, 'edges': [{'from': a, 'to': b, 'label': l} for a, b, l in edges], 'notes': notes}
views = [
    V('V-CONTEXT', 'System context', 'context', ['C-STAFF', 'C-FRONTEND', 'C-API'], [('C-STAFF', 'C-FRONTEND', 'Browser or phone'), ('C-FRONTEND', 'C-API', 'JSON over same-origin session')], 'People who do not log in are recorded by PMO (U-09).'),
    V('V-APP', 'Applications and stores', 'application', ['C-FRONTEND', 'C-API', 'C-SERVICES', 'C-WORKERS', 'C-DB'], [('C-FRONTEND', 'C-API', '/api/v1'), ('C-API', 'C-SERVICES', 'service calls with expected revision'), ('C-SERVICES', 'C-DB', 'records + audit'), ('C-WORKERS', 'C-DB', 'leased jobs')], 'Business rules stay in services (C-05).'),
    V('V-MODULE', 'API module', 'module', ['C-API', 'C-SERVICES', 'C-AGENTS', 'C-ALERTS'], [('C-API', 'C-SERVICES', 'grants and authority checks'), ('C-SERVICES', 'C-AGENTS', 'agent runs'), ('C-SERVICES', 'C-ALERTS', 'outbox')], 'apps/api is new; no business logic in it.'),
    V('V-DEPLOY', 'Logical deployment', 'deployment', ['C-FRONTEND', 'C-API', 'C-DB', 'C-WORKERS'], [('C-FRONTEND', 'C-API', 'same host, /api/v1 proxied'), ('C-API', 'C-DB', 'private network')], 'Hosting is open (D-HOSTING).'),
    V('V-DATA', 'Records', 'data', ['REC-CASE', 'REC-WORK', 'REC-TASK', 'REC-AUDIT', 'REC-NOTIFICATION', 'REC-CONVERSATION'], [('REC-WORK', 'REC-CASE', 'belongs to'), ('REC-TASK', 'REC-WORK', 'belongs to'), ('REC-AUDIT', 'REC-CASE', 'history of')], 'New records: notification, alert preference, conversation.'),
]
SC = lambda i, t, req, g, w, th: {'id': i, 'title': t, 'refs': [req], 'evidence': ['S-SCREENS'], 'given': g, 'when': w, 'then': th, 'status': 'not_run', 'result_evidence': None}
scenarios = [
    SC('A-ME', 'Identity and destinations by role', 'R-SESSION', 'A PM and a Finance Lead with sample grants', 'Each calls /api/v1/me', 'Each gets only their destinations and startable lines; signed-out gets 401'),
    SC('A-MYWORK', 'Three queues with kinds and counts', 'R-MYWORK', 'Sample work: one decision, one exception, one waiting, one verified', 'Request each queue', 'Needs me holds Decide/Do/Fix rows only; counts match; sample=true on sample cases; payroll rows never reach a Finance Lead'),
    SC('A-WORKITEM', 'Work item shows separate facts and agent steps', 'R-WORKITEM', 'An invoice approved but not sent, amount of a later stage unknown', 'Read the work item', 'Facts approved=earned, sent=not_yet; unknown amount has unknown=true and no value; agent steps carry no approval'),
    SC('A-HISTORY', 'History is complete and read-only', 'R-WORKITEM', 'A work item with a return and an approval', 'Read history', 'Every event in order with actor kind; restricted entries say Restricted; no edit endpoint exists'),
    SC('A-DECIDE', 'Approve one exact version', 'R-DECIDE', 'A Finance Lead eligible for invoice v2, prepared by someone else', 'Claim and approve with the current revision', '200; work moves on; one audit event; an alert is queued; the preparer cannot claim the same task'),
    SC('A-STALE', 'Stale version is refused', 'R-DECIDE', 'Invoice replaced by v3 after the page loaded', 'Approve with the old revision', '409; nothing changes; the client shows the newer version'),
    SC('A-START', 'Start a line', 'R-START', 'A PM with factory.start on a project', 'Start the weekly report with valid intake', '201 with work id; missing field returns 422; a line without permission is absent from /lines'),
    SC('A-RESPONSE', 'Record a client response with proof', 'R-RESPONSE', 'A task waiting for the client UAT response', 'Upload proof, record approved with attestation', 'Task completes; evidence hash stored; without proof 422'),
    SC('A-RECONCILE', 'Reconcile an uncertain send', 'R-EXCEPTION', 'A delivery with unknown outcome', 'Record delivered with evidence', 'State moves on; no resend happened before reconciliation'),
    SC('A-RESUME', 'Resume after setup', 'R-EXCEPTION', 'Work held at setup needed', 'Set the rule and resume', 'Work continues from the held step'),
    SC('A-PROJECT', 'Project journey and money tab', 'R-PROJECT', 'A project with four stages, one amount unknown', 'Read project and money tab', 'Unknown stage amount is unknown, not 0; invoices and receipts separate'),
    SC('A-OVERVIEW', 'Floor counts from visible records', 'R-OVERVIEW', 'A PMO Lead with sample work', 'Read overview', 'Counts match visible work; reduced motion shows the flat view'),
    SC('A-MONTHEND', 'Month-end and import', 'R-FINANCE', 'October with one missing bank statement', 'Read month-end; submit a file with a wrong period row', 'Cash received shows known amount plus Unknown; import is quarantined with findings'),
    SC('A-PAYROLL', 'Payroll rows stay with HR', 'R-FINANCE', 'HR Lead and Finance Lead', 'Each reads the match', 'HR Lead gets rows; Finance Lead gets 403'),
    SC('A-SETUP', 'Rules are versioned and Not set is explicit', 'R-SETUP', 'A Finance rule not set', 'Read and save the rule', 'Read shows set=false; save creates a new revision; stale revision 409'),
    SC('A-ALERTS', 'Preferences and notification centre', 'R-ALERTS', 'A person with immediate WhatsApp', 'Change to daily email; trigger a decision', 'Preference saved; notification listed; mock adapter records the send'),
    SC('A-ASSISTANT', 'Assistant answers with sources and drafts', 'R-ASSISTANT', 'A Finance user and a restricted payroll record', 'Ask about a project; ask for payroll figures; ask for an invoice draft', 'Answer cites records; payroll: cannot answer, says why; draft links to a started line, not approved'),
    SC('A-REPORT', 'Report figures link to records', 'R-REPORTS', 'Monthly report with an unknown figure', 'Read the report', 'Each figure lists its sources; unknown is unknown'),
    SC('A-ACCESSIBILITY', 'Frontend meets devices and WCAG 2.2 AA', 'R-FRONTEND', 'The first feature built', 'Run automated accessibility checks and test on phone and desktop', 'No AA violations; focus ring and reduced motion work; layouts at 390px and 1440px'),
]
runbooks = [
    {'id': 'O-STALE', 'title': 'People report "this version changed" repeatedly', 'refs': ['E-TASK-DECIDE', 'REC-TASK'], 'evidence': ['S-BACKEND'], 'trigger': 'Repeated 409 responses on one task',
     'steps': ['Read the work item history for revisions', 'Check whether an agent keeps redrafting', 'Never bypass the revision check'], 'recovery': 'Stop the redrafting cause; the person reloads and decides the current version.', 'owner': 'developer'},
    {'id': 'O-UNCERTAIN', 'title': 'A send outcome is unknown', 'refs': ['E-WORK-ACTION', 'REC-WORK'], 'evidence': ['S-BACKEND'], 'trigger': 'Work shows effect uncertain',
     'steps': ['Check the provider or recipient for receipt', 'Record delivered, not delivered or still unknown with evidence', 'Resend only after not delivered is recorded'], 'recovery': 'Reconcile through E-WORK-ACTION.', 'owner': 'operator'},
]

# ---------------------------------------------------------------- tasks and milestones
def T(i, t, eps, reqs, gates, deps, acc, role='developer'):
    return {'id': i, 'title': t, 'refs': eps + reqs + gates, 'evidence': ['S-SCREENS', 'S-SCOPE'], 'owner_role': role, 'status': 'planned', 'depends_on': deps, 'gate_ids': gates, 'acceptance': acc, 'estimate': None, 'assignee': None, 'due_date': None}
by_task = {}
for e in endpoints:
    by_task.setdefault([r for r in e['refs'] if r.startswith('T-')][0], []).append(e['id'])
tasks = [
    T('T-FOUNDATION', 'API foundation: apps/api, session and CSRF, error shape, /me', by_task['T-FOUNDATION'], ['R-SESSION'], [], [], ['A-ME']),
    T('T-FRONTEND-SHELL', 'Frontend shell: Next.js app, design system tokens and components, top bar, phone bar', [], ['R-FRONTEND', 'R-DEVICES', 'R-SAMPLE'], ['D-AUTH'], ['T-FOUNDATION'], ['A-ACCESSIBILITY']),
    T('T-MYWORK', 'My work: three queues, Decide/Do/Fix, search and filter', by_task['T-MYWORK'], ['R-MYWORK', 'R-VOLUME'], [], ['T-FRONTEND-SHELL'], ['A-MYWORK']),
    T('T-WORKITEM', 'Work item: stations, facts, agent checklist, history', by_task['T-WORKITEM'], ['R-WORKITEM'], [], ['T-MYWORK'], ['A-WORKITEM', 'A-HISTORY']),
    T('T-DECIDE', 'Decisions: claim and decide one exact version, desktop and phone', by_task['T-DECIDE'], ['R-DECIDE'], [], ['T-WORKITEM'], ['A-DECIDE', 'A-STALE']),
    T('T-START', 'Start work: lines menu and every line\'s intake drawer', by_task['T-START'], ['R-START'], ['D-LEADERS-START'], ['T-WORKITEM'], ['A-START']),
    T('T-RESPONSE', 'Record a response with proof', by_task['T-RESPONSE'], ['R-RESPONSE'], [], ['T-WORKITEM'], ['A-RESPONSE']),
    T('T-EXCEPTIONS', 'Exceptions: reconcile, resume, cancel; All exceptions', by_task['T-EXCEPTIONS'], ['R-EXCEPTION'], ['D-RETURN'], ['T-DECIDE'], ['A-RECONCILE', 'A-RESUME']),
    T('T-PROJECTS', 'Projects, project tabs, documents and reports', by_task['T-PROJECTS'], ['R-PROJECT', 'R-REPORTS'], [], ['T-WORKITEM'], ['A-PROJECT', 'A-REPORT']),
    T('T-FLOOR', 'Overview: factory floor (flat and 3D) with exceptions', by_task['T-FLOOR'], ['R-OVERVIEW', 'R-MOTION'], [], ['T-EXCEPTIONS'], ['A-OVERVIEW']),
    T('T-FINANCE', 'Finance: month-end, imports and back-office lines', by_task['T-FINANCE'], ['R-FINANCE'], [], ['T-START'], ['A-MONTHEND']),
    T('T-PAYROLL', 'Payroll (restricted) and HR corrections', by_task['T-PAYROLL'], ['R-FINANCE'], [], ['T-FINANCE'], ['A-PAYROLL']),
    T('T-SETUP', 'Setup: rules, people, delegation, templates', by_task['T-SETUP'], ['R-SETUP'], [], ['T-FOUNDATION', 'T-FRONTEND-SHELL'], ['A-SETUP']),
    T('T-ALERTS', 'Notifications and alert preferences (mock adapter)', by_task['T-ALERTS'], ['R-ALERTS'], ['D-ALERT-PROVIDERS'], ['T-DECIDE'], ['A-ALERTS']),
    T('T-ASSISTANT', 'Assistant conversations with sources and drafts', by_task['T-ASSISTANT'], ['R-ASSISTANT'], ['D-AGENT-PROVIDER'], ['T-START'], ['A-ASSISTANT']),
    T('T-BACKEND-ROLES', 'Backend: PMO Lead for Head of PMO, three-step approvals, leaders may start every line', [], ['R-ROLES'], [], [], ['A-START']),
]
for t in tasks:
    if t['id'] == 'T-ALERTS': t['refs'] += ['I-ALERTS', 'JOB-ALERTS']
    if t['id'] == 'T-ASSISTANT': t['refs'] += ['I-AGENT', 'JOB-ASSISTANT']
milestones = [
    {'id': 'M-1', 'title': 'First feature: My work and one decision, end to end', 'refs': ['T-FOUNDATION', 'T-FRONTEND-SHELL', 'T-MYWORK', 'T-WORKITEM', 'T-DECIDE', 'D-FIRST-FEATURE'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-ME, A-MYWORK, A-WORKITEM, A-HISTORY, A-DECIDE and A-STALE pass on PostgreSQL with sample data', 'A-ACCESSIBILITY passes for these screens on phone and desktop', 'Design review against the approved canvas'], 'gate_ids': ['D-API-STYLE', 'D-AUTH', 'D-FIRST-FEATURE']},
    {'id': 'M-2', 'title': 'Start, respond and recover', 'refs': ['T-START', 'T-RESPONSE', 'T-EXCEPTIONS', 'T-BACKEND-ROLES'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-START, A-RESPONSE, A-RECONCILE, A-RESUME pass'], 'gate_ids': ['D-RETURN']},
    {'id': 'M-3', 'title': 'Projects, overview, Finance, payroll and setup', 'refs': ['T-PROJECTS', 'T-FLOOR', 'T-FINANCE', 'T-PAYROLL', 'T-SETUP'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-PROJECT, A-REPORT, A-OVERVIEW, A-MONTHEND, A-PAYROLL, A-SETUP pass'], 'gate_ids': []},
    {'id': 'M-4', 'title': 'Alerts and assistant', 'refs': ['T-ALERTS', 'T-ASSISTANT'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-ALERTS and A-ASSISTANT pass on mock and synthetic providers'], 'gate_ids': ['D-ALERT-PROVIDERS', 'D-AGENT-PROVIDER', 'D-NOTIFY-MODEL', 'D-CONVERSATION-MODEL']},
]

model = {
    'schema_version': '1.0', 'pins': {'skill': '0.1.0', 'generator': '0.1.0'},
    'project': {'id': 'psl-factory-frontend', 'title': 'PSL operations factory — frontend and data API', 'scope': 'Scope v2: new Next.js frontend in frontend/ on a data API added to the existing Django backend (S-08, I-02).',
                'stage': 'existing', 'roles': ['operator', 'developer', 'technical reviewer', 'business owner', 'delivery owner', 'release authority'],
                'constraints': ['Django keeps login, permissions and every business rule (C-05).', 'No deployment, live AI or external connections authorised in this phase.', 'Never invent financial rules or real approvers.']},
    'security_schemes': {
        'Session': {'type': 'apiKey', 'name': 'sessionid', 'in': 'cookie', 'description': 'Django session cookie from the existing sign-in (D-AUTH, proposed).'},
        'Csrf': {'type': 'apiKey', 'name': 'X-CSRFToken', 'in': 'header', 'description': 'Django CSRF token, required on every write together with the session.'}},
    'sources': sources, 'requirements': requirements, 'decisions': decisions, 'components': components, 'records': records, 'invariants': invariants,
    'endpoints': endpoints, 'integrations': integrations, 'jobs': jobs, 'journeys': journeys, 'views': views, 'scenarios': scenarios, 'runbooks': runbooks,
    'tasks': tasks, 'milestones': milestones}
json.dump(model, open(os.path.join(HERE, 'model.json'), 'w'), indent=2, ensure_ascii=False)
print(len(endpoints), 'endpoints,', len(tasks), 'tasks,', len(decisions), 'decisions')
