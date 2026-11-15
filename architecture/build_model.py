"""Builds architecture/model.json for the PSL frontend redesign data API.

The canonical model is authored here as compact tables so it stays reviewable; the
factory compiler (packages/architecture/arch.py) validates it and generates the package.
Run: python3 architecture/build_model.py
"""
import copy, hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {
    'S-SCOPE': ('Approved scope v2 (early start by exception)', 'sources/scope-v2.md', '2', 'private'),
    'S-SCREENS': ('Approved screen list (design approval 13 Nov 2026)', 'sources/screens-approved.md', '2026-11-13', 'private'),
    'S-AUDIT': ('End-to-end flow audit and decisions', 'sources/flow-audit.md', '2026-11-13', 'private'),
    'S-BACKEND': ('Observed backend inventory', 'sources/backend-inventory.md', '2026-11-13', 'private'),
    'S-DECISIONS': ('Decisions relayed 13 Nov 2026', 'sources/decisions-2026-11-13.md', '2026-11-13', 'private'),
    'S-DECISIONS-V2': ('Frontend decisions and role boundary, 13 Nov 2026', 'sources/decisions-2026-11-13-v2.md', '2026-11-13b', 'private'),
    'S-DECISIONS-V3': ('Contract fields for the approved boards; decision variants parked, 13 Nov 2026', 'sources/decisions-2026-11-13-v3.md', '2026-11-13c', 'private'),
    'S-DECISIONS-V4': ('Sample tag hidden; remaining frontend screens split to build in parallel, 14 Nov 2026', 'sources/decisions-2026-11-14.md', '2026-11-14', 'private'),
    'S-DECISIONS-V5': ('Build in parallel, split where the contract is missing, frontend drafts contract proposals, 14 Nov 2026', 'sources/decisions-2026-11-14-v2.md', '2026-11-14b', 'private'),
    'S-DECISIONS-V6': ('Boards are the spec with a fidelity gate; overnight contract proposals and screen-family splits, 14-15 Nov 2026', 'sources/decisions-2026-11-15.md', '2026-11-15', 'private'),
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
    # ---- v4 (13 Nov 2026): fields the approved SCR-01/02/03 boards show; drafted by the frontend, confirmed by the backend developer (S-DECISIONS-V3)
    dec('D-TASK-DECISION-VIEW', 'Where a human task\'s decision content is read', 'backend developer', 'E-WORK-ITEM tasks[]; SCR-03 standard decision', 'proposed',
        'PROPOSAL for the backend developer to confirm: each E-WORK-ITEM tasks[] entry gains optional fields: decision (exact version label and number, amount as money that may be unknown, basis, recipient, changes since the previous version, preparer, approval chain with "your step n of m"), cannot_act_reason (not_your_role, prepared_by_you, already_decided, not_your_turn) and asked (who was asked instead, when alerted, by which channel). No new endpoint; the backend composes every value from its records and the line\'s configured approval order; the frontend shows only what is returned.',
        'Smallest change: the decision screen already loads the work item, reuses its read permission and revision, and existing v3 fields and fixtures stay valid because every new field is optional. Unknown amounts use unknown=true with no value, never 0 (INV-UNKNOWN). Approvers and their order come from the backend (D-APPROVAL-ORDER), never from the frontend.',
        ['New GET /api/v1/tasks/{task_id} returning the decision view (separate read permission and handler; a second request per screen)', 'Extend the E-TASK-CLAIM response (only available after a claim, so not-yours and own-work views would have nothing)'],
        ['R-DECIDE', 'D-APPROVAL-ORDER'], ('S-DECISIONS-V3', 'S-SCREENS')),
    dec('D-WORKITEM-DETAIL', 'Work item detail the SCR-02 boards show', 'backend developer', 'E-WORK-ITEM', 'proposed',
        'PROPOSAL for the backend developer to confirm: E-WORK-ITEM gains optional amount (money, unknown form), started_by and started_at; each station gains optional started_at, finished_at and held_by (who or what holds it, and whether that is you); the agent gains optional started_at and each agent step an optional at.',
        'The approved SCR-02 boards show "Started by <person> (<role>) · <date>", station times ("Done · Mon 14:05", "Waiting 2h · you"), agent step times and the agent start time; A-WORKITEM needs an unknown amount. All additions are optional so v3 payloads stay valid.',
        ['Leave the values off the screen (the readiness fallback)'], ['R-WORKITEM'], ('S-DECISIONS-V3', 'S-SCREENS')),
    dec('D-WORKLIST-FILTERS', 'My work filters and agent marker', 'backend developer', 'E-WORK-LIST', 'proposed',
        'PROPOSAL for the backend developer to confirm: E-WORK-LIST accepts project (a case_id) and waiting_on (me, someone_else, agent, outside_party, no_owner) as optional filters; line takes the line key, never the display title; the response gains optional filters.lines[{key, title}] (lines the person can see work on); rows gain optional line_key and agent (the agent whose avatar the row shows).',
        'The approved filter panel (SCR-01-*-filter) offers Line, Project, State and Waiting on, and rows show an agent avatar (CMP-18) when an agent drafted or is working on the item. The waiting_on categories are an engineering proposal read from the board rows, not a business rule. Project options come from E-PROJECTS.',
        ['Drop the Project and Waiting-on filters from the screen', 'A separate /api/v1/work/filters endpoint'], ['R-MYWORK'], ('S-DECISIONS-V3', 'S-SCREENS')),
    dec('D-DECISION-VARIANTS', 'Payment exception, CEO final costing and CTO emergency decisions', 'business owner with the backend developer', 'SCR-03 variants: payment exception, CEO costing, CTO emergency', 'open',
        'Not designed. Parked until PSL and the backend developer settle the payment-exception rule: what "Keep owed", "Exception" and "Reject" record, which fields and figures (invoiced, received, owed, rule) each variant returns and sends, who holds the authority, and whether the short payment is decided through E-TASK-DECIDE or an exception action. No verdict, rule or approver is assumed here.',
        'A payment exception needs configured human authority and never erases debt (AGENTS.md product invariants); inventing its verdicts would invent a financial rule. The design engineer parked the variants on 13 Nov 2026.',
        ['New verdicts on E-TASK-DECIDE', 'Move the short payment to E-WORK-ACTION or E-EXCEPTIONS (FE-M2)'], ['R-DECIDE'], ('S-DECISIONS-V3', 'S-SCREENS')),
]

# ---- v2 (13 Nov 2026): the design engineer works on the frontend only; backend and agent choices belong to the backend developer
def add_rev(i, status, choice, rationale, alts, ev):
    d = next(x for x in decisions if x['id'] == i)
    d['revisions'].append({'revision': len(d['revisions']) + 1, 'status': status, 'choice': choice, 'rationale': rationale, 'alternatives': alts, 'evidence': ev})
    d['evidence'] = sorted(set(d['evidence']) | set(ev))
add_rev('D-PAGING', 'approved', 'Cursor paging with a rows-per-page choice of 10, 20 or 50 on every list (default 20); newest activity first; counts per queue returned separately.',
        'Design engineer, 13 Nov 2026: users choose 10, 20 or 50 rows per page. Default 20 is a proposal within that choice.', ['Fixed 50 rows'], ['S-DECISIONS-V2'])
add_rev('D-UPDATES', 'approved', 'Polling: lists every 15 seconds while visible, an open work item every 5 seconds while an agent is working; no push channel in v1.',
        'Accepted as proposed by the design engineer, 13 Nov 2026 (frontend behaviour).', ['Server-sent events', 'WebSockets'], ['S-DECISIONS-V2'])
add_rev('D-FIRST-FEATURE', 'approved', 'My work and one decision end to end (J-01 view, J-02): identity, the three queues, the work item with history, claim and decide with stale-version handling; desktop and phone. The frontend is built against the API contract with a mock server and connected to each real endpoint as the backend delivers it.',
        'Accepted by the design engineer, 13 Nov 2026, who builds the frontend only.', ['Start work first', 'Factory floor first'], ['S-DECISIONS-V2'])
for d in decisions:
    new_owner = 'backend developer' if d['id'] in ('D-API-STYLE', 'D-AUTH', 'D-NOTIFY-MODEL', 'D-CONVERSATION-MODEL') else ('business owner with the backend developer' if d['id'] in ('D-AGENT-PROVIDER', 'D-ALERT-PROVIDERS', 'D-RETURN') else None)
    if new_owner:
        last = d['revisions'][-1]
        d['owner'] = new_owner
        add_rev(d['id'], last['status'], last['choice'], 'Unchanged choice; the decision now belongs to the ' + new_owner + '. The frontend builds against it as a working assumption (design engineer, 13 Nov 2026).', last['alternatives'], ['S-DECISIONS-V2'])

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
  [P('queue', 'query', True, S(enum=['needs_me', 'waiting_on_others', 'done', 'unassigned'])), P('q', 'query', False), P('line', 'query', False), P('state', 'query', False), P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
  LIST(WORK_ROW, {'counts': QUEUE_COUNTS})),
 ('E-WORK-ITEM', 'GET', '/api/v1/work/{work_id}', 'One work item', 'Open a row or an alert link', 'case.read plus the line\'s read permission.', 'api.work.read', 'workflows.factory.snapshot', 'R-WORKITEM', ['REC-WORK', 'REC-TASK', 'REC-AGENTRUN', 'REC-DOCUMENT'], ['INV-ACCESS', 'INV-FACTS', 'INV-UNKNOWN', 'INV-AGENT', 'INV-SAMPLE'], ['D-UPDATES'], 'T-WORKITEM', 'A-WORKITEM', [P('work_id')], None,
  O({'id': S(), 'title': S(), 'line': S(), 'reference': S(), 'state': STATE, 'revision': I(minimum=1), 'stations': A(O({'name': S(), 'status': S(enum=['done', 'current_person', 'current_agent', 'waiting', 'stopped', 'not_started', 'verified'])})),
     'facts': A(FACT), 'tasks': A(O({'id': S(), 'kind': S(), 'title': S(), 'required_role': S(), 'you_can_act': B, 'revision': I(minimum=1)})), 'agent': O({'name': S(), 'status': S(enum=['working', 'done', 'waiting', 'stopped', 'none']), 'steps': A(O({'text': S(), 'status': S(), 'source': {'type': 'string'}}, ['text', 'status']))}, ['status']),
     'next_step': S(), 'sample': B}, ['id', 'title', 'line', 'reference', 'state', 'revision', 'stations', 'facts', 'tasks', 'agent', 'next_step', 'sample'])),
 ('E-WORK-HISTORY', 'GET', '/api/v1/work/{work_id}/history', 'Work item history', 'History tab', 'Same as reading the work item; restricted entries returned as Restricted.', 'api.work.history', 'core.Audit query', 'R-WORKITEM', ['REC-AUDIT', 'REC-TASK'], ['INV-ACCESS', 'INV-AUDIT', 'INV-RESTRICTED'], [], 'T-WORKITEM', 'A-HISTORY', [P('work_id'), P('kind', 'query', False, S(enum=['all', 'decisions', 'agent_work', 'evidence'])), P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
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
 ('E-EXCEPTIONS', 'GET', '/api/v1/exceptions', 'All exceptions', 'Overview and All exceptions page', 'Leads; filtered by grants.', 'api.exceptions.list', 'workflows.factory.snapshot', 'R-EXCEPTION', ['REC-WORK'], ['INV-ACCESS'], ['D-PAGING'], 'T-EXCEPTIONS', 'A-RESUME', [P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
  LIST(O({'work_id': S(), 'what': S(enum=['effect_uncertain', 'owner_needed', 'setup_needed', 'blocked', 'followup_needed']), 'title': S(), 'doing': S(), 'who_acts': S(), 'since': S(format='date-time')}))),
 ('E-PROJECTS', 'GET', '/api/v1/projects', 'Projects list', 'Projects page', 'case.read.', 'api.projects.list', 'identity.services.visible_cases', 'R-PROJECT', ['REC-CASE'], ['INV-ACCESS', 'INV-SAMPLE'], ['D-PAGING'], 'T-PROJECTS', 'A-PROJECT', [P('q', 'query', False), P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
  LIST(O({'case_id': S(), 'title': S(), 'pm': S(), 'stage': S(), 'sample': B}))),
 ('E-PROJECT', 'GET', '/api/v1/projects/{case_id}', 'Project journey', 'Open a project', 'case.read.', 'api.projects.read', 'pmo services', 'R-PROJECT', ['REC-CASE', 'REC-WORK'], ['INV-ACCESS', 'INV-FACTS'], [], 'T-PROJECTS', 'A-PROJECT', [P('case_id')], None,
  O({'case_id': S(), 'title': S(), 'lines': A(O({'line': S(), 'state': STATE, 'work_id': S()})), 'next': S()})),
 ('E-PROJECT-TAB', 'GET', '/api/v1/projects/{case_id}/{tab}', 'Project tab', 'Milestones, Documents, Money, Registers, Actions tabs', 'case.read plus the tab\'s read permission (finance.read for Money).', 'api.projects.tab', 'pmo / finance / documents services', 'R-PROJECT', ['REC-CASE', 'REC-MONEY', 'REC-DOCUMENT'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-FACTS'], ['D-PAGING'], 'T-PROJECTS', 'A-PROJECT',
  [P('case_id'), P('tab', 'path', True, S(enum=['milestones', 'documents', 'money', 'registers', 'actions'])), P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
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
 ('E-PEOPLE', 'GET', '/api/v1/setup/people', 'People and roles', 'Setup people', 'Admin.', 'api.setup.people', 'identity services', 'R-SETUP', ['REC-GRANT'], ['INV-ACCESS'], ['D-PAGING'], 'T-SETUP', 'A-SETUP', [P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
  LIST(O({'person': S(), 'roles': A(S()), 'active': B}))),
 ('E-DELEGATION', 'PUT', '/api/v1/setup/delegation', 'Set a delegate', 'Delegation form', 'Leads for their own authority.', 'api.setup.delegation', 'policy.role_assignments', 'R-SETUP', ['REC-CONFIG', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], [], 'T-SETUP', 'A-SETUP', [],
  O(dict(EXPECTED, delegate=S(), starts=S(format='date'), ends=S(format='date'))), O({'revision': I(minimum=1)})),
 ('E-TEMPLATES', 'GET', '/api/v1/setup/templates', 'Document templates', 'Setup templates', 'documents read.', 'api.setup.templates', 'documents services', 'R-SETUP', ['REC-DOCUMENT'], ['INV-ACCESS', 'INV-SAMPLE'], [], 'T-SETUP', 'A-SETUP', [], None,
  LIST(O({'line': S(), 'name': S(), 'version': S(), 'test_template': B}))),
 ('E-NOTIFICATIONS', 'GET', '/api/v1/notifications', 'Notification centre', 'Bell and notifications page', 'Own notifications only.', 'api.notifications.list', 'api notifications (new)', 'R-ALERTS', ['REC-NOTIFICATION'], ['INV-ACCESS'], ['D-NOTIFY-MODEL', 'D-PAGING'], 'T-ALERTS', 'A-ALERTS', [P('cursor', 'query', False), P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})], None,
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
def make_endpoint(i, m, path, t, trig, perm, h, svc, req, recs, invs, decs, task, scen, params, reqbody, resp):
    write = m != 'GET'
    return {'id': i, 'title': t, 'refs': [req] + recs + invs + decs + [task, scen], 'evidence': ['S-SCREENS', 'S-BACKEND'],
        'method': m, 'path': path, 'trigger': trig, 'security': ['Session', 'Csrf'] if write else ['Session'], 'permission': perm, 'parameters': params,
        'request': reqbody,
        'responses': [(created if i == 'E-WORK-START' else ok)(t, resp)] + (STD_WRITE if write else STD_READ),
        'handler': h, 'service': svc, 'local_work': 'Resolve the record, check grants and authority, call ' + svc + ('; write one audit event' if write else '') + '.',
        'integration_calls': [], 'failure_recovery': ('409 on stale revision: the client reloads and shows the newer version; 422 names the fields; nothing is partially written.' if write else 'Read-only; 404 hides records the person may not see.'),
        'implementation': 'unimplemented'}
for row in EP:
    endpoints.append(make_endpoint(*row))
# integration calls: alerts and agents
for e in endpoints:
    if e['id'] == 'E-NOTIFICATIONS': e['integration_calls'] = [{'integration': 'I-ALERTS', 'operation': 'queue_alert'}]
    if e['id'] == 'E-MESSAGE': e['integration_calls'] = [{'integration': 'I-AGENT', 'operation': 'run_assistant'}]

# ---- v4 PROPOSAL (backend developer to confirm; S-DECISIONS-V3): fields the approved boards show.
# Every addition is optional, so every v3 field, payload and fixture stays valid.
EP_BY_ID = {e['id']: e for e in endpoints}
DT = S(format='date-time')
AGENT_KEY = S(enum=['tola', 'chidi', 'zainab'])
def MONEY_OR_UNKNOWN(what): return dict(MONEY, description=what + ' When the value is not known: unknown=true and no amount, never 0 (INV-UNKNOWN).')
def add_props(schema, props):
    for k, v in props.items():
        assert k not in schema['properties'], k
        schema['properties'][k] = v
HOLDER = O({'kind': S(enum=['person', 'role', 'agent', 'outside_party', 'factory']), 'name': S(description='Person, role, agent or outside party name as recorded'), 'is_you': B}, ['kind', 'name', 'is_you'])
CHAIN_STEP = O({'position': I(minimum=1), 'role': S(), 'person': S(description='Absent until a person is assigned'), 'status': S(enum=['approved', 'returned', 'rejected', 'withdrawn', 'current', 'not_yet']),
                'decided_at': DT, 'is_you': B}, ['position', 'role', 'status', 'is_you'])
DECISION_VIEW = O({
    'version': O({'label': S(description='As shown on the board, e.g. "Invoice v2"'), 'number': I(minimum=1), 'document_id': S(), 'drafted_at': DT}, ['label', 'number']),
    'amount': MONEY_OR_UNKNOWN('Amount of the exact version being decided; absent when the decision carries no amount.'),
    'basis': S(description='Plain-language basis composed by the backend from contract terms, e.g. "Contract stage 2 of 4 · terms v1"'),
    'recipient': S(description='Who the output goes to when sent, e.g. a billing email; absent when nothing is sent'),
    'changes': O({'previous_label': S(), 'items': A(S())}, ['previous_label', 'items']),
    'prepared_by': O({'name': S(), 'role': S(), 'is_you': B, 'with_agent': AGENT_KEY}, ['name', 'is_you']),
    'chain': O({'steps': A(CHAIN_STEP), 'your_step': I(minimum=1), 'step_count': I(minimum=1)}, ['steps', 'step_count']),
}, ['version', 'chain'])
DECISION_VIEW['description'] = 'PROPOSAL (D-TASK-DECISION-VIEW). Present on decision tasks. Every value comes from backend records and the line\'s configured approval order; the frontend shows only what is returned. your_step is absent when the person has no step.'
# E-WORK-ITEM: SCR-02 detail and SCR-03 decision content (F-03 PMO-0-1/0-2, F-04 PMO-0-1/0-2)
wi = EP_BY_ID['E-WORK-ITEM']['responses'][0]['schema']
add_props(wi, {'amount': MONEY_OR_UNKNOWN('Amount of the work item (e.g. the invoice); absent when the line carries no amount.'),
               'started_by': O({'name': S(), 'role': S(), 'is_you': B}, ['name', 'is_you']), 'started_at': DT})
add_props(wi['properties']['stations']['items'], {'started_at': DT, 'finished_at': DT, 'held_by': HOLDER})
add_props(wi['properties']['agent'], {'started_at': DT})
add_props(wi['properties']['agent']['properties']['steps']['items'], {'at': DT})
add_props(wi['properties']['tasks']['items'], {
    'decision': DECISION_VIEW,
    'cannot_act_reason': S(enum=['not_your_role', 'prepared_by_you', 'already_decided', 'not_your_turn'], description='Present only when you_can_act is false'),
    'asked': A(O({'name': S(), 'role': S(), 'alerted_at': DT, 'channels': A(S(enum=['whatsapp', 'email']))}, ['name', 'role']))})
wi['properties']['tasks']['items']['properties']['asked']['description'] = 'Who was asked to act on this task (shown when you cannot act); empty when nobody is assigned yet.'
# E-WORK-LIST: Project and Waiting-on filters, line options by key, agent avatar (F-02 PMO-0-1..0-3)
wl = EP_BY_ID['E-WORK-LIST']
for p in wl['parameters']:
    if p['name'] == 'line': p['schema'] = S(description='Line key (filters.lines[].key or a row\'s line_key), never the display title')
wl['parameters'][3:3] = [P('project', 'query', False, S(description='Project case_id, from E-PROJECTS')),
                         P('waiting_on', 'query', False, S(enum=['me', 'someone_else', 'agent', 'outside_party', 'no_owner'], description='PROPOSAL (D-WORKLIST-FILTERS)'))]
wl_resp = wl['responses'][0]['schema']
add_props(wl_resp, {'filters': O({'lines': A(O({'key': S(), 'title': S()}))})})
add_props(wl_resp['properties']['items']['items'], {'line_key': S(), 'agent': AGENT_KEY})
for eid, decs in (('E-WORK-ITEM', ['D-WORKITEM-DETAIL', 'D-TASK-DECISION-VIEW']), ('E-WORK-LIST', ['D-WORKLIST-FILTERS'])):
    e = EP_BY_ID[eid]; e['refs'] = e['refs'] + decs; e['evidence'] = e['evidence'] + ['S-DECISIONS-V3']
EP_BY_ID['E-WORK-ITEM']['refs'].append('A-NOT-YOURS')

# ---- v6 PROPOSAL (backend developer to confirm; S-DECISIONS-V5): Start work, record a response, reconcile,
# RFP outcome and project tabs. Every addition to an existing payload is optional and every v5 required list is kept,
# so built screens and their fixtures keep validating. Values that are business rules (allowed actions, response
# options, who may record, amounts) are supplied by the backend; the contract only carries them.
V6_EV = ['S-DECISIONS-V5', 'S-SCREENS']
LABELLED = O({'value': S(), 'label': S()})
DATE = S(format='date')
PAGE_LIMIT = P('limit', 'query', False, {'type': 'integer', 'enum': [10, 20, 50], 'description': 'Rows per page chosen by the person; default 20'})
# -- Start work (SCR-04; F-05 PMO-0-1..0-5) -> D-START-INTAKE
FIELD_KINDS = ['text', 'long_text', 'date', 'date_range', 'period', 'datetime', 'integer', 'money', 'choice', 'record', 'records', 'evidence', 'display']
lines_ep = EP_BY_ID['E-LINES']
lines_resp = lines_ep['responses'][0]['schema']
line_row = lines_resp['properties']['items']['items']
field = line_row['properties']['intake']['items']
field['properties']['type']['description'] = ('PROPOSAL (D-START-INTAKE): one of ' + ', '.join(FIELD_KINDS) + '. The submitted intake value per kind: '
    'text/long_text a string; date YYYY-MM-DD; date_range {from, to}; period YYYY-MM; datetime ISO 8601; integer a number; money {amount, currency, unknown} '
    '(left blank = unknown=true with no amount, never 0); choice one options[].value; record one option value from E-LINE-OPTIONS; records a list of them; '
    'evidence an evidence_id returned by E-EVIDENCE-UPLOAD on the line\'s case; display is shown, never sent.')
add_props(field, {
    'help': S(description='Hint under the field as composed by the backend, e.g. "Only milestones marked complete, with proof, are listed."'),
    'placeholder': S(),
    'options': A(LABELLED),
    'options_source': S(enum=['line_options'], description='Present on record/records fields: read the options from E-LINE-OPTIONS for this line and field'),
    'depends_on': S(description='Name of the field whose value narrows these options (e.g. milestone depends on project); sent as parent to E-LINE-OPTIONS'),
    'evidence_kind': S(description='Kind to send to E-EVIDENCE-UPLOAD for an evidence field'),
    'multiple': B,
    'value': S(description='For display fields: the value shown, e.g. "Client weekly report · test template v1"'),
    'restricted': B,
})
field['properties']['options']['description'] = 'Fixed choices for a choice field (e.g. Audience: Internal or Client), listed by the backend.'
add_props(line_row, {
    'subtitle': S(description='One line under the title in the chooser, e.g. "From a completed milestone"'),
    'case_scope': S(enum=['project', 'fixed'], description='project: the case is the project chosen in the intake field named by case_field; fixed: start on case_id below'),
    'case_field': S(description='Name of the record field whose chosen option carries case_id and case_revision (case_scope project)'),
    'case_id': S(description='Case to start on when case_scope is fixed (e.g. the Finance back-office case)'),
    'case_revision': I(minimum=1),
    'next': O({'station_count': I(minimum=1), 'agent': AGENT_KEY, 'decided_by': A(S(description='Role that decides, as configured on the line')), 'summary': S(), 'journey_url': S()}, []),
    'start_via': S(enum=['work_start', 'finance_import'], description='Which endpoint starts the line: E-WORK-START, or E-IMPORT for a file import line'),
})
line_row['properties']['next']['description'] = 'The "What happens next" block. Absent fields are not shown; the frontend derives none of it from roles.'
add_props(lines_resp, {'default_line': S(description='Line key the main Start work button opens directly. Absent: the button opens the menu (e.g. CEO and CTO, D-LEADERS-START).')})
EP_BY_ID['E-ME']['responses'][0]['schema']['properties']['startable_lines']['description'] = 'PROPOSAL (D-START-INTAKE): line keys, the same as E-LINES items[].key, never display titles. Start work shows when the list is not empty.'
ws = EP_BY_ID['E-WORK-START']
ws['request']['properties']['intake']['description'] = 'Field name to value, one entry per E-LINES intake field the person filled; value shapes per field type (D-START-INTAKE). Evidence values are evidence_ids uploaded to the same case before the start.'
ws['responses'] = [r if r['status'] != '422' else {'status': '422', 'description': 'Validation failed; fields named', 'schema': O({'code': S(), 'message': S(), 'fields': A(O({'name': S(), 'message': S()}))}, ['code', 'message'])} for r in ws['responses']]
eu = EP_BY_ID['E-EVIDENCE-UPLOAD']
add_props(eu['responses'][0]['schema'], {'case_revision': I(minimum=1, description='The case revision after the upload; send it as case_revision on the start, response or action that follows')})
eu['trigger'] = 'File drop in a form (record a response, reconcile, Start work proof fields)'
# -- Record a response (SCR-16) and reconcile (SCR-02 awaiting reconciliation; F-06 PMO-0-1..0-5) -> D-RESPONSE-VIEW, D-WORK-ACTIONS-VIEW
wi = EP_BY_ID['E-WORK-ITEM']['responses'][0]['schema']
add_props(wi, {
    'case_id': S(description='Case the work belongs to; the path for E-EVIDENCE-UPLOAD'),
    'case_revision': I(minimum=1),
    'allowed_actions': A(S(enum=['resume', 'cancel', 'reconcile'])),
    'reconcile': O({'what': S(description='What was sent, e.g. "Invoice INV-0412 v2 to the billing contact"'), 'sent_at': DT,
                    'checks': O({'count': I(), 'first_at': DT, 'last_at': DT, 'agent': AGENT_KEY}, ['count']),
                    'outcomes': A(S(enum=['delivered', 'not_delivered', 'unknown'])), 'evidence_kind': S(),
                    'resend': S(description='What a not-delivered answer allows, as the backend states it, e.g. "one resend of the same version"')}, ['outcomes']),
    'rfp_outcome': O({'submission': O({'id': S(), 'label': S(), 'sent_at': DT, 'delivery': S()}, ['id', 'label']),
                      'results': A(S(enum=['won', 'lost', 'pending', 'unknown'])), 'reasons': A(LABELLED), 'record_as': A(LABELLED), 'evidence_kind': S(),
                      'recorded': O({'result': S(enum=['won', 'lost', 'pending', 'unknown']), 'at': DT, 'by': S()}, ['result'])}, ['submission', 'results', 'record_as']),
})
wi['properties']['allowed_actions']['description'] = 'PROPOSAL (D-WORK-ACTIONS-VIEW): the E-WORK-ACTION actions this person may take now, decided by the backend. Absent or empty: offer none.'
wi['properties']['reconcile']['description'] = 'PROPOSAL (D-WORK-ACTIONS-VIEW): present when the state is awaiting_reconciliation or effect_uncertain.'
wi['properties']['rfp_outcome']['description'] = 'PROPOSAL (D-RFP-OUTCOME): present on an RFP when the backend lets this person record its outcome. results, reasons and record_as come from the backend.'
task_item = wi['properties']['tasks']['items']
task_item['properties']['kind']['description'] = 'Task kind as named by the backend. A task with a response block is a recorded response (open the response form); one with a decision block is a decision.'
add_props(task_item, {'response': O({
    'variant': S(enum=['client_response', 'sow_signature', 'team_input'], description='Which SCR-16 form to show'),
    'responders': A(O({'id': S(), 'name': S(), 'role': S(), 'organisation': S()}, ['id', 'name'])),
    'actions': A(O({'value': S(enum=['approved', 'changes_requested', 'signed', 'rejected', 'estimate', 'input']), 'label': S()}, ['value'])),
    'versions': A(O({'id': S(), 'label': S(), 'note': S(description='e.g. "the version sent for UAT"'), 'sent_at': DT}, ['id', 'label'])),
    'teams': A(O({'key': S(), 'name': S(), 'given': B, 'estimate_needed': B}, ['key', 'name', 'given'])),
    'blocking': S(description='Plain sentence on who holds review, e.g. "Security and Product haven\'t given input yet."'),
    'evidence_kind': S(), 'claim_required': B,
}, ['actions', 'responders'])})
task_item['properties']['response']['description'] = ('PROPOSAL (D-RESPONSE-VIEW): present on tasks a person records for someone who does not log in. Which actions a task accepts and who may have responded are '
    'backend rules; the frontend offers only what is listed. claim_required true: call E-TASK-CLAIM before E-RESPONSE.')
rs = EP_BY_ID['E-RESPONSE']
add_props(rs['request'], {'case_revision': I(minimum=1), 'version_id': S(), 'team': S(), 'estimate_person_days': {'type': 'number', 'minimum': 0},
                          'what': S(description='What they gave (team input)'), 'evidence_ids': A(S(description='Further proof files beyond evidence_id ("Add another file")')),
                          'note': {'type': 'string', 'description': 'Up to 2000 characters'}})
# -- Project tabs (SCR-38, SCR-12, SCR-11, SCR-29; F-07 PMO-0-1) -> D-PROJECT-TAB-ROWS
REF_LINK = O({'reference': S(), 'title': S(), 'work_id': S(), 'state': STATE, 'at': DT}, ['reference'])
PAID = O({'status': S(enum=['paid', 'part_paid', 'not_paid', 'not_due', 'finance_tracks', 'unknown']), 'owed': MONEY_OR_UNKNOWN('Amount still owed as recorded by Finance.')}, ['status'])
PAID['description'] = 'Paid is Finance data, separate from the invoice (INV-FACTS). Composed by the backend from receipts and allocations; never derived by the frontend.'
OWNER = O({'name': S(), 'role': S(), 'recorded_by_pm': B, 'outside_party': B}, ['name'])
MILESTONE_ROW = O({'position': I(minimum=1), 'name': S(), 'contract_amount': MONEY_OR_UNKNOWN('From the signed SOW.'), 'amount_note': S(description='e.g. "amount set at go-live"'),
                   'completion': O({'status': S(enum=['done', 'not_yet']), 'at': DT, 'proof': S(description='Proof label, e.g. "client UAT sign-off"'), 'evidence_id': S()}, ['status']),
                   'invoice': REF_LINK, 'paid': PAID,
                   'changes': A(O({'reference': S(), 'title': S(), 'amount': MONEY_OR_UNKNOWN('Change amount; unknown until a SOW amendment with it is signed.'), 'work_id': S()}, ['reference', 'amount']))}, ['position', 'name', 'contract_amount', 'completion'])
DOCUMENT_ROW = O({'document_id': S(), 'title': S(), 'kind': S(), 'version': S(), 'status': S(), 'updated_at': DT, 'test_template': B, 'work_id': S(), 'sample': B}, ['document_id', 'title', 'version', 'status'])
MONEY_ROW = O({'position': I(minimum=1), 'stage': S(), 'amount': MONEY_OR_UNKNOWN('Stage amount.'), 'amount_note': S(), 'invoice': REF_LINK, 'invoice_status': S(description='As composed by the backend, e.g. "Verified 03 Nov", "Held · owner needed"'),
               'paid': PAID, 'figure_id': S(description='Figure in E-REPORT whose sources explain this amount')}, ['position', 'stage', 'amount'])
REGISTER_ROW = O({'register': S(enum=['issues', 'changes', 'emergencies', 'rfps']), 'reference': S(), 'title': S(), 'severity': S(enum=['high', 'medium', 'low'], description='Set by the PM'),
                  'owner': OWNER, 'state': S(description='State text as composed by the backend'), 'age_seconds': I(), 'work_id': S(), 'sample': B}, ['register', 'reference', 'title'])
ACTION_ROW = O({'action_id': S(), 'title': S(), 'from': O({'meeting': S(), 'at': DATE}, ['meeting']), 'owner': OWNER, 'due': O({'date': DATE, 'unknown': B}, ['unknown']),
                'state': S(enum=['open', 'overdue', 'done']), 'work_id': S()}, ['action_id', 'title', 'state'])
for name, row in (('milestones', MILESTONE_ROW), ('documents', DOCUMENT_ROW), ('money', MONEY_ROW), ('registers', REGISTER_ROW), ('actions', ACTION_ROW)):
    row['description'] = 'Row on the ' + name + ' tab (D-PROJECT-TAB-ROWS, proposal); present only when that tab is requested.'
pt = EP_BY_ID['E-PROJECT-TAB']
pt_resp = pt['responses'][0]['schema']
pt_resp['properties']['items']['description'] = 'v5 untyped rows, kept for compatibility. PROPOSAL (D-PROJECT-TAB-ROWS): read the typed array named by the tab instead (milestones, documents, money, registers or actions); items holds the same rows.'
add_props(pt_resp, {'milestones': A(MILESTONE_ROW), 'documents': A(DOCUMENT_ROW), 'money': A(MONEY_ROW), 'registers': A(REGISTER_ROW), 'actions': A(ACTION_ROW)})
add_props(pt_resp, {'summary': O({'registers': O({'issues': I(), 'changes': I(), 'emergencies': I(), 'rfps': I()}, []), 'actions': O({'total': I(), 'overdue': I(), 'without_owner': I()}, []),
                                  'report_id': S(description='Money tab: E-REPORT id for the drill-down')}, [])})
pt['parameters'][2:2] = [P('register', 'query', False, S(enum=['issues', 'changes', 'emergencies', 'rfps'], description='Registers tab only')), P('q', 'query', False)]
pr = EP_BY_ID['E-PROJECT']['responses'][0]['schema']
add_props(pr, {'revision': I(minimum=1, description='Case revision, for starts from the project page'),
               'tab_counts': O({'milestones': I(), 'documents': I(), 'registers': I(), 'actions': I()}, [])})
rp = EP_BY_ID['E-REPORT']['responses'][0]['schema']
add_props(rp['properties']['figures']['items'], {'id': S(), 'source_details': A(O({'label': S(), 'reference': S(), 'kind': S(enum=['document', 'rule', 'record', 'evidence']), 'document_id': S(), 'work_id': S()}, ['label', 'reference', 'kind']))})
add_props(rp, {'agent': AGENT_KEY})
# -- new endpoints
EP_V6 = [
 ('E-LINE-OPTIONS', 'GET', '/api/v1/lines/{line_key}/fields/{field}/options', 'Options for a Start work field', 'Open a record choice in a Start work drawer', 'factory.start on the line; each option filtered by the person\'s grants.', 'api.lines.options', 'workflows.factory_definitions + domain services', 'R-START', ['REC-CASE', 'REC-GRANT'], ['INV-ACCESS', 'INV-SAMPLE'], ['D-START-INTAKE', 'D-PAGING'], 'T-START', 'A-START-INTAKE',
  [P('line_key'), P('field'), P('parent', 'query', False, S(description='Value chosen in the field named by depends_on')), P('q', 'query', False), P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(O({'value': S(), 'label': S(), 'hint': S(), 'case_id': S(), 'case_revision': I(minimum=1), 'disabled_reason': S(), 'sample': B}, ['value', 'label']))),
 ('E-RFP-OUTCOME', 'POST', '/api/v1/work/{work_id}/rfp-outcome', 'Record an RFP outcome', 'Record the outcome form (won, lost, pending, unknown)', 'rfp.outcome on the case, as the backend allows; lessons use rfp.dispose.', 'api.rfp.outcome', 'pmo.rfp.outcome / dispose', 'R-RESPONSE', ['REC-WORK', 'REC-EVIDENCE', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT', 'INV-UNKNOWN'], ['D-RFP-OUTCOME'], 'T-RESPONSE', 'A-RFP-OUTCOME', [P('work_id')],
  O(dict(EXPECTED, case_revision=I(minimum=1), submission_id=S(), result=S(enum=['won', 'lost', 'pending', 'unknown']), learned_at=DT, record_as=S(description='One of rfp_outcome.record_as[].value'),
         evidence_id=S(), note={'type': 'string', 'description': 'Up to 2000 characters'}, reason=S(description='One of rfp_outcome.reasons[].value'), lessons={'type': 'string', 'description': 'Lost: what we would do differently'},
         awarded_amount=MONEY_OR_UNKNOWN('Won: as stated in the award letter.'), expected_decision_on=DATE, remind_at=DT), ['expected_revision', 'case_revision', 'submission_id', 'result', 'learned_at', 'record_as', 'evidence_id']),
  O({'work_id': S(), 'result': S(enum=['won', 'lost', 'pending', 'unknown']), 'state': STATE, 'revision': I(minimum=1), 'engagement_work_id': S()}, ['work_id', 'result', 'state', 'revision'])),
]
for row in EP_V6:
    e = make_endpoint(*row); e['evidence'] = e['evidence'] + ['S-DECISIONS-V5']; endpoints.append(e); EP_BY_ID[e['id']] = e
for eid, decs in (('E-LINES', ['D-START-INTAKE']), ('E-ME', ['D-START-INTAKE']), ('E-WORK-START', ['D-START-INTAKE']), ('E-EVIDENCE-UPLOAD', ['D-START-INTAKE', 'D-RESPONSE-VIEW']),
                  ('E-WORK-ITEM', ['D-RESPONSE-VIEW', 'D-WORK-ACTIONS-VIEW', 'D-RFP-OUTCOME']), ('E-RESPONSE', ['D-RESPONSE-VIEW']), ('E-WORK-ACTION', ['D-WORK-ACTIONS-VIEW']),
                  ('E-PROJECT-TAB', ['D-PROJECT-TAB-ROWS']), ('E-PROJECT', ['D-PROJECT-TAB-ROWS']), ('E-REPORT', ['D-PROJECT-TAB-ROWS'])):
    e = EP_BY_ID[eid]; e['refs'] = e['refs'] + decs; e['evidence'] = sorted(set(e['evidence']) | {'S-DECISIONS-V5'})
EP_BY_ID['E-LINES']['refs'].append('A-START-INTAKE'); EP_BY_ID['E-WORK-ITEM']['refs'] += ['A-RESPONSE', 'A-RECONCILE']; EP_BY_ID['E-PROJECT-TAB']['refs'].append('A-PROJECT-TABS')
decisions += [
    dec('D-START-INTAKE', 'What Start work needs from the contract', 'backend developer', 'E-LINES, E-LINE-OPTIONS, E-WORK-START, E-EVIDENCE-UPLOAD, E-ME; SCR-04', 'proposed',
        'PROPOSAL for the backend developer to confirm: (1) each E-LINES line says which case it starts on: case_scope project (the case and its revision come from the chosen option of the field named by case_field) or fixed (case_id and case_revision on the line, e.g. the Finance back-office lines with no Project field); (2) intake[].type takes a defined kind (text, long_text, date, date_range, period, datetime, integer, money, choice, record, records, evidence, display) with help, placeholder, fixed options, depends_on, evidence_kind, display value and restricted; (3) record fields read their options from a new E-LINE-OPTIONS endpoint, filtered by grants on the backend and narrowed by parent; (4) proof is uploaded first with E-EVIDENCE-UPLOAD on the line\'s case, which now returns the case revision after the upload, and the evidence_id is the intake value; (5) lines carry an optional subtitle, a "what happens next" block (station count, agent, deciding role, summary) and start_via (E-WORK-START, or E-IMPORT for an import line); (6) E-LINES returns default_line for the main button, absent for people whose button opens the menu; (7) /me startable_lines holds line keys; (8) a 422 on E-WORK-START names each field with its message.',
        'The approved SCR-04 drawers (16 lines, desktop and phone, plus validation) show choice lists from records, proof files, money and period fields and a "What happens next" block; v5 gives only key, title, group and name/label/type/required, and requires a case revision no read returns. All additions are optional, so v5 payloads stay valid. Field kinds, options, deciding roles and the default line come from the backend; the frontend derives none of them from roles. A blank money value is unknown, never 0 (INV-UNKNOWN). Whether the management accounts drawer starts through E-WORK-START or E-IMPORT, and E-IMPORT\'s missing entity, basis, extracted-at and control total, are for the backend developer.',
        ['Options inline in E-LINES (grows with records, cannot filter by parent)', 'One start endpoint per line', 'Read project options from E-PROJECTS (no revision, ties Start work to the projects feature)'],
        ['R-START', 'D-LEADERS-START'], ('S-DECISIONS-V5', 'S-SCREENS', 'S-BACKEND')),
    dec('D-RESPONSE-VIEW', 'What Record a response needs from the work item', 'backend developer', 'E-WORK-ITEM tasks[].response, case_id, case_revision; E-RESPONSE; SCR-16', 'proposed',
        'PROPOSAL for the backend developer to confirm: E-WORK-ITEM gains optional case_id and case_revision (so proof can be uploaded from the work item) and each task an optional response block: the SCR-16 variant (client response, SOW signature, team input), the responders the backend allows, the actions this task accepts with their labels, the versions being answered, the teams with given or missing input, a blocking sentence, the evidence kind and claim_required. E-RESPONSE gains optional case_revision, version_id, team, estimate_person_days, what, evidence_ids and note. When claim_required is true the frontend calls E-TASK-CLAIM before E-RESPONSE.',
        'The approved SCR-16 boards show a who-responded picker, per-variant action choices, a version picker, several proof files and the team-input status; v5 tasks[] carry none of it. Which actions a task accepts and who may have responded are backend business rules, so the contract only carries what the backend allows. For the backend developer: workflows.factory.provide_information requires a factory_information task claimed by the actor, an evidence kind listed in context["missing"] and a case revision, while E-RESPONSE had no claim step and a different action vocabulary; claim_required, evidence_kind and case_revision are proposed to bridge that, and the API maps actions to the backend vocabulary.',
        ['E-RESPONSE takes the file directly (one write, but no reuse of E-EVIDENCE-UPLOAD)', 'Frontend lists fixed actions per task kind (a business rule in the frontend)'],
        ['R-RESPONSE'], ('S-DECISIONS-V5', 'S-SCREENS', 'S-BACKEND')),
    dec('D-WORK-ACTIONS-VIEW', 'Which work actions a person may take, and what reconcile shows', 'backend developer', 'E-WORK-ITEM allowed_actions, reconcile; E-WORK-ACTION; SCR-02 awaiting reconciliation', 'proposed',
        'PROPOSAL for the backend developer to confirm: E-WORK-ITEM gains optional allowed_actions (resume, cancel, reconcile: what this person may do now, decided by the backend from the line\'s operator and recovery authority) and a reconcile block (what was sent and when, the agent\'s checks, the outcomes the backend accepts, the evidence kind and the resend the backend allows after not delivered). The frontend offers an action only when it is listed.',
        'The approved SCR-02 awaiting-reconciliation board offers "It arrived / It didn\'t arrive, allow one resend / I can\'t tell yet"; a not-delivered answer authorises a resend to a client (INV-RESEND). Offering actions the API did not grant would put recovery authority in the frontend. The resend allowance is stated by the backend; none is assumed here.',
        ['Try the action and show the 403', 'Separate GET for allowed actions'], ['R-EXCEPTION'], ('S-DECISIONS-V5', 'S-SCREENS')),
    dec('D-RFP-OUTCOME', 'Recording an RFP outcome', 'backend developer', 'New E-RFP-OUTCOME; E-WORK-ITEM rfp_outcome; SCR-16 RFP outcome boards', 'proposed',
        'PROPOSAL for the backend developer to confirm: a separate POST /api/v1/work/{work_id}/rfp-outcome records won, lost, pending or unknown against one submission, with when it was learned, the role recorded as, proof and a note; optional reason and lessons (lost), awarded amount (won, may be unknown), expected decision date and reminder (pending). E-WORK-ITEM gains an optional rfp_outcome block with the submission, the results, reasons and record-as roles the backend allows, and any outcome already recorded. Lessons map to the backend dispose step.',
        'Eight approved SCR-16 states record an RFP outcome; E-RESPONSE\'s actions cannot carry it and stretching rejected or input would misrecord it. The backend already has pmo.rfp.outcome (submission, result won/lost/pending/unknown, observed_at, role, evidence, note, case revision) and dispose (lessons); reason, awarded amount, expected decision date and reminder have no backend field today and stay optional until the backend developer confirms them. Who may record outcomes is a PSL rule the backend holds ("only roles PSL allows").',
        ['New actions on E-RESPONSE', 'Leave the RFP outcome states unbuilt'], ['R-RESPONSE'], ('S-DECISIONS-V5', 'S-SCREENS', 'S-BACKEND', 'S-AUDIT')),
    dec('D-PROJECT-TAB-ROWS', 'Row shapes for the five project tabs', 'backend developer', 'E-PROJECT-TAB, E-PROJECT tab counts, E-REPORT sources; SCR-38, SCR-12, SCR-11, SCR-29', 'proposed',
        'PROPOSAL for the backend developer to confirm: E-PROJECT-TAB rows are typed per tab, in an optional array named by the tab (the untyped v5 items stays and holds the same rows): milestones (position, name, contract amount, completion with proof, invoice, paid, changes with their own amount), documents (document, version, status, test template), money (stage, amount, invoice and its status, paid, the E-REPORT figure that explains it), registers (register, reference, title, severity, owner, state, age; filtered by register and q) and actions (title, from which meeting, owner, due date or unknown, open/overdue/done); a summary carries register and action counts and the money report id. E-PROJECT gains optional revision and tab counts; E-REPORT figures gain an id and source details (document, rule, record, evidence).',
        'The approved project tab boards show these columns; v5 rows are untyped ("documented in handoff", never documented). Every amount uses the money form with unknown=true and no value when unknown, never 0, and paid is Finance data separate from the invoice (INV-UNKNOWN, INV-FACTS). Paid status categories and owed amounts are composed by the backend from receipts and allocations, not by the frontend. The documents tab has no approved list board, so its row is an engineering proposal.',
        ['Keep untyped rows documented in prose', 'One endpoint per tab'], ['R-PROJECT', 'R-REPORTS'], ('S-DECISIONS-V5', 'S-SCREENS')),
]

# ---- v7 PROPOSAL (backend developer to confirm; S-DECISIONS-V6, under S-DECISIONS-V5 item (g)): the fields, parameters and
# endpoints the remaining approved boards need. Every addition to an existing payload is optional and every v6 required list,
# enum value and parameter is kept, so built screens and their fixtures keep validating. Business rules (which steps, actions,
# events, responders or authorities exist, who may act, every amount) stay with the backend; the contract only carries them.
# Where the rule itself is undecided the screen gets display fields only and the decision stays open.
V7_EV = ['S-DECISIONS-V6', 'S-SCREENS']
B_CANVAS = 'design/canvas/project/'; F_CANVAS = 'design/canvas/finance/project/'
TONE = S(enum=['neutral', 'person', 'agent', 'stopped', 'uncertain', 'verified', 'restricted'], description='Display tone the backend assigns; the frontend maps it to the design-system tag colour and never derives it from state names')
TAG = O({'label': S(), 'tone': TONE}, ['label'])
LINK = O({'label': S(), 'reference': S(), 'work_id': S(), 'document_id': S(), 'case_id': S(), 'evidence_id': S()}, [])
AGENT_NOTE = O({'agent': AGENT_KEY, 'lines': A(S())}, ['agent', 'lines'])
PERSON = O({'name': S(), 'role': S(), 'is_you': B}, ['name'])
DUE = O({'date': DATE, 'unknown': B}, ['unknown'])
CASE_REF = O({'case_id': S(), 'title': S()}, ['case_id', 'title'])
def described(schema, text):
    schema['description'] = text; return schema
def add_param(e, *params):
    names = {p['name'] for p in e['parameters']}
    for p in params:
        assert p['name'] not in names, p['name']
        e['parameters'].append(p)
def link_eps(pairs, scen=None):
    for eid, decs in pairs:
        e = EP_BY_ID[eid]; e['refs'] = e['refs'] + [d for d in decs if d not in e['refs']]; e['evidence'] = sorted(set(e['evidence']) | {'S-DECISIONS-V6'})
        if scen and scen not in e['refs']: e['refs'].append(scen)
FIELDS_422 = {'status': '422', 'description': 'Validation failed; fields named', 'schema': O({'code': S(), 'message': S(), 'fields': A(O({'name': S(), 'message': S()}))}, ['code', 'message'])}

# -- All exceptions (SCR-10; F-06 round 2 build) -> D-EXCEPTIONS-LIST
ex = EP_BY_ID['E-EXCEPTIONS']
add_param(ex, P('q', 'query', False, S(description='PROPOSAL (D-EXCEPTIONS-LIST): free-text search over title, reference, what is being done and who acts, across every row the person may see')),
          P('what', 'query', False, S(enum=['effect_uncertain', 'owner_needed', 'setup_needed', 'blocked', 'followup_needed'], description='PROPOSAL (D-EXCEPTIONS-LIST): one kind')))
add_props(ex['responses'][0]['schema'], {'open_count': I(description='PROPOSAL (D-EXCEPTIONS-LIST): every row matching q/what the person may see, across pages ("4 OPEN", "Exceptions · 4"); absent when not counted, never guessed')})
add_props(ex['responses'][0]['schema']['properties']['items']['items'], {'ref': S(description='The work\'s business reference shown under the title, e.g. INV-0412')})

# -- Record a response r2 (SCR-16 client response, SOW, success; F-09 PMO-0-1) and team input (F-09B) -> D-RESPONSE-VIEW r2
wi = EP_BY_ID['E-WORK-ITEM']['responses'][0]['schema']
task_item = wi['properties']['tasks']['items']
resp_block = task_item['properties']['response']
resp_block['properties']['variant']['enum'] += ['go_live_acceptance', 'support_handover']
RECORDED = O({'by': PERSON, 'at': DT, 'responded_at': DT, 'received_via': S(description='One of response.channels[].value'), 'proof_count': I(), 'summary': S()}, ['by', 'at'])
add_props(resp_block, {
    'intro': S(description='Sentence above the form as composed by the backend, e.g. "Lagoon Health\'s client contact doesn\'t log in… The release waits for this."'),
    'proof_hint': S(description='Hint under the proof field, e.g. "Signed PDF, e-signature record, or the client\'s email saved as PDF"'),
    'agent_note': AGENT_NOTE,
    'channels': A(LABELLED),
    'context': O({'project': CASE_REF, 'document': O({'reference': S(), 'label': S(), 'document_id': S()}, ['reference'])}, []),
    'next': A(S(description='"What happens next" lines, e.g. "the SOW\'s 4 stages become the project\'s milestones"')),
    'recorded': RECORDED,
})
resp_block['properties']['channels']['description'] = 'How the response may have been received (e.g. email, letter, in person), as the backend lists them; sent back as received_via'
resp_block['properties']['recorded']['description'] = 'Present once the response is recorded (success board): who recorded it, when, how it was received and how many proof files'
rs = EP_BY_ID['E-RESPONSE']
add_props(rs['request'], {'received_via': S(description='One of response.channels[].value')})
add_props(rs['responses'][0]['schema'], {'revision': I(minimum=1), 'recorded': copy.deepcopy(RECORDED), 'next': A(S())})

# -- Reconcile r2 (SCR-02 awaiting reconciliation; F-09 PMO-0-1, PMO-0-5) -> D-WORK-ACTIONS-VIEW r2
add_props(wi['properties']['reconcile'], {
    'unknown_note': S(description='What "I can\'t tell yet" does, as the backend states it, e.g. "Keep it held and remind me tomorrow"'),
    'resend_note': S(description='What a resend reuses, e.g. "A resend reuses the same invoice number"')})
add_props(EP_BY_ID['E-WORK-ACTION']['request'], {'case_revision': I(minimum=1, description='Case revision returned by the proof upload, when evidence_id is sent')})

# -- RFP frame, outcome boards and drafted follow-up (SCR-16 rfp-*; F-09 PMO-0-2) -> D-RFP-OUTCOME r2
add_props(wi, {'rfp': O({
    'reference': S(), 'title': S(), 'client': S(),
    'status': O({'kind': S(enum=['deadline', 'submitted', 'won', 'lost', 'pending', 'unknown']), 'label': S(description='e.g. "DEADLINE 28 NOV · 16 DAYS", "WON · 04 DEC"'), 'at': DT, 'days_left': I()}, ['kind', 'label']),
    'pm': PERSON,
    'tabs': A(O({'key': S(enum=['requirements', 'team_input', 'pricing', 'submission', 'outcome']), 'label': S(), 'count': I(), 'of': I(), 'work_id': S(), 'current': B}, ['key', 'label'])),
}, ['reference', 'status'])})
wi['properties']['rfp']['description'] = 'PROPOSAL (D-RFP-OUTCOME r2): the RFP frame on every RFP board and on team input. Counts are composed by the backend; absent counts are not shown.'
ro = wi['properties']['rfp_outcome']
add_props(ro['properties']['recorded'], {
    'rows': A(O({'label': S(), 'value': S(), 'at': DT}, ['label', 'value'])),
    'reminder': O({'holder': PERSON, 'at': DT}, ['holder', 'at']),
    'lessons': A(O({'category': LABELLED, 'text': S()}, ['text'])),
    'lessons_by': PERSON,
    'debrief': LINK,
    'archive_reference': S(description='e.g. ARC-0117'),
    'engagement': O({'reference': S(), 'work_id': S()}, ['reference']),
    'next': A(S()),
})
add_props(ro, {
    'lesson_categories': A(LABELLED),
    'followup': O({
        'to': S(description='Recipient address exactly as the backend returns it'),
        'body': S(), 'version': I(minimum=1), 'agent': AGENT_KEY,
        'checks': A(O({'text': S(), 'source': S(), 'status': S(enum=['done', 'now', 'next'])}, ['text', 'status'])),
        'status': S(enum=['drafted', 'sending', 'sent', 'effect_uncertain']), 'sent_at': DT,
        'note': S(description='e.g. "It goes only if you send it"'), 'can_send': B, 'can_edit': B}, ['to', 'body', 'version', 'status']),
})
ro['properties']['followup']['description'] = 'PROPOSAL (D-RFP-OUTCOME r2): a follow-up drafted by the agent. It is sent only by a person through E-RFP-FOLLOWUP; an uncertain send is reconciled before any resend (INV-RESEND).'
ror = EP_BY_ID['E-RFP-OUTCOME']
add_props(ror['request'], {'lessons_items': A(O({'category': S(description='One of rfp_outcome.lesson_categories[].value'), 'text': S()}, ['text']))})

# -- Month-end (SCR-36; F-10 PMO-0-1) -> D-MONTH-END-VIEW
me_ep = EP_BY_ID['E-MONTH-END']
me_resp = me_ep['responses'][0]['schema']
add_props(me_resp, {
    'as_of': DT, 'coverage': S(description='e.g. "FROM RECORDS YOU CAN SEE"'),
    'summary': O({'done': I(), 'waiting': I(), 'in_progress': I(), 'total': I()}, []),
    'cash_received_detail': O({'known': MONEY_OR_UNKNOWN('The part of cash received that is known.'), 'has_unknown': B, 'unknown_note': S()}, ['has_unknown']),
    'agent_note': O({'agent': AGENT_KEY, 'text': S()}, ['agent', 'text']),
    'next_action': O({'label': S(), 'work_id': S()}, ['label']),
})
me_resp['properties']['summary']['description'] = 'Counts composed by the backend; the frontend never buckets task states itself'
me_resp['properties']['cash_received_detail']['description'] = 'Known part plus an Unknown marker ("₦4.7M + Unknown"); has_unknown true means some cash is not yet known, never 0 (INV-UNKNOWN)'
add_props(me_resp['properties']['tasks']['items'], {'title': S(), 'detail': S(), 'status_label': S(), 'tone': TONE, 'restricted': B, 'restricted_label': S(description='e.g. "HR only"; restricted rows carry no work_id')})

# -- Line workspace (27 unassigned screens and the Finance line screens; screen-coverage.md) -> D-LINE-WORKSPACE
FIELD_DESC = copy.deepcopy(field)
FIELD_DESC['description'] = 'Same descriptor as an E-LINES intake field (D-START-INTAKE): kind, label, help, options, evidence kind'
CELL = O({'column': S(), 'text': S(), 'money': MONEY_OR_UNKNOWN('Cell amount.'), 'date': DUE, 'tag': TAG, 'link': LINK, 'restricted': B}, ['column'])
WS_ITEM = O({
    'id': S(), 'text': S(), 'detail': S(), 'label': S(), 'value': S(),
    'money': MONEY_OR_UNKNOWN('Item amount.'), 'cells': A(CELL),
    'status': S(enum=['done', 'now', 'next', 'not_yet', 'held', 'blocked', 'unknown', 'not_applicable']),
    'tag': TAG, 'severity': S(enum=['high', 'medium', 'low', 'info']),
    'owner': OWNER, 'due': DUE, 'held_by': HOLDER, 'agent': AGENT_KEY, 'at': DT,
    'cites': A(LINK), 'cite_label': S(description='e.g. "2 RECORDS"'),
    'channel': S(), 'receipt': S(enum=['received', 'not_yet', 'uncertain', 'failed', 'unknown']),
    'restricted': B, 'steps': A(S(description='Keys of workspace.steps that act on this item'))}, ['id'])
WS_SECTION = O({
    'key': S(), 'kind': S(enum=['facts', 'table', 'checklist', 'findings', 'suggestions', 'recipients', 'figures', 'text', 'timeline']),
    'title': S(), 'note': S(), 'agent': AGENT_KEY, 'as_of': DT, 'coverage': S(), 'restricted': B, 'restricted_label': S(),
    'columns': A(O({'key': S(), 'label': S(), 'kind': S(enum=['text', 'money', 'date', 'tag', 'reference', 'integer'])}, ['key', 'label'])),
    'items': A(WS_ITEM), 'total': I(), 'filters': A(LABELLED), 'next_cursor': S()}, ['key', 'kind', 'items'])
WS_STEP = O({
    'key': S(), 'label': S(), 'emphasis': S(enum=['primary', 'secondary', 'danger']), 'applies_to': S(enum=['workspace', 'item', 'items']),
    'fields': A(FIELD_DESC), 'confirm': S(), 'consequence': S(description='Plain sentence on what the step does, e.g. "Approving sends this exact version to Lagoon Health."'),
    'task_id': S(description='Present when the step is a decision: use E-TASK-CLAIM/E-TASK-DECIDE on this task instead of E-WORK-STEP'),
    'claim_required': B, 'sends': B, 'disabled_reason': S()}, ['key', 'label'])
WORKSPACE = O({
    'line_key': S(), 'screen': S(description='Approved screen id, e.g. SCR-25'), 'view': S(description='Board state, e.g. review'),
    'title': S(), 'subtitle': S(), 'status': TAG, 'byline': S(description='e.g. "Report v1 · written by Tunde Bello, assembled by Tola"'),
    'version': O({'label': S(), 'number': I(minimum=1), 'document_id': S()}, ['label']),
    'context': O({'project': CASE_REF, 'crumbs': A(LABELLED)}, []),
    'agent_note': AGENT_NOTE, 'sections': A(WS_SECTION), 'steps': A(WS_STEP), 'next': A(S()), 'revision': I(minimum=1)}, ['line_key', 'sections'])
WORKSPACE['description'] = ('PROPOSAL (D-LINE-WORKSPACE): the line-specific content of the work item, one typed block for every line, rendered by section kind. '
    'Which sections and steps exist, their values and who may take each step are composed by the backend; the frontend shows only what is returned. '
    'Restricted sections carry restricted=true and no rows for people without the grant (INV-RESTRICTED); unknown amounts and dates use the unknown form, never 0.')
add_props(wi, {'workspace': WORKSPACE})

# -- Assign the accountable person (SCR-24) -> D-RFP-INTAKE
add_props(wi, {'assign': O({'role': S(), 'candidates': A(O({'person_id': S(), 'name': S(), 'role': S(), 'hint': S(description='e.g. current load, as the backend states it')}, ['person_id', 'name'])), 'note_required': B}, ['candidates'])})
wi['properties']['assign']['description'] = 'PROPOSAL (D-RFP-INTAKE): present when this person may assign the accountable person (e.g. an Unassigned RFP); candidates come from the backend\'s configured rule'

# -- Setup rules (SCR-13 rules, finance-rules, delivery-rules; F-11 PMO-0-1..0-3) and payroll visibility (SCR-13 fields) -> D-SETUP-RULES-VIEW, D-PAYROLL-VISIBILITY
sr = EP_BY_ID['E-SETUP-RULES']
sr_resp = sr['responses'][0]['schema']
add_props(sr_resp['properties']['items']['items'], {
    'area': S(), 'area_label': S(), 'group': S(), 'group_label': S(), 'used_by': A(S()), 'display_value': S(description='Current value as text; absent when not set (the screen shows Not set)'),
    'link': S(description='Screen the rule is edited on instead, e.g. costing-rule'), 'holds_work': B, 'effective_from': DT, 'can_change': B, 'restricted': B,
    'editor': O({'kind': S(enum=['role_set', 'read_only']), 'options': A(O({'role': S(), 'label': S()}, ['role', 'label'])), 'selected': A(S())}, ['kind'])})
add_props(sr_resp, {'not_set_count': I(), 'roles_missing_count': I()})
srs = EP_BY_ID['E-SETUP-RULE-SAVE']
srs['request']['properties']['expected_revision'] = I(minimum=0, description='PROPOSAL (D-SETUP-RULES-VIEW): the revision exactly as read; 0 saves the first version of a rule that is Not set (fixes the v6 minimum of 1, which made a first save impossible)')
add_props(srs['request'], {'starts': DATE, 'reason': S(), 'evidence_id': S()})

# -- Delegation (SCR-13 delegation; F-11B) -> D-DELEGATION-VIEW
dl = EP_BY_ID['E-DELEGATION']
add_props(dl['request'], {'authority': S(description='One of E-DELEGATIONS authorities[].value'), 'reason': S()})
# -- People and staff accounts (SCR-13, SCR-21; F-11C) -> D-PEOPLE-VIEW (writes gated by D-ADMIN-AUTHORITY)
pp = EP_BY_ID['E-PEOPLE']['responses'][0]['schema']
add_props(pp['properties']['items']['items'], {'person_id': S(), 'email': S(description='As the backend returns it'), 'scopes': A(S()), 'state': S(enum=['active', 'invited', 'deactivated']),
                                               'last_signed_in_at': DT, 'open_items': I(), 'can_change': B, 'revision': I(minimum=1)})
add_props(pp, {'roles_missing': A(O({'role': S(), 'label': S(), 'held_work': I()}, ['role', 'label'])), 'role_options': A(O({'role': S(), 'label': S(), 'scope_needed': B}, ['role', 'label']))})
# -- Templates (SCR-34; F-11D) -> D-TEMPLATES-VIEW
tp = EP_BY_ID['E-TEMPLATES']['responses'][0]['schema']
add_props(tp['properties']['items']['items'], {'template_id': S(), 'kind': S(), 'updated_at': DT, 'updated_by': S(), 'versions': I(), 'revision': I(minimum=1), 'can_upload': B})

# -- Alerts (SCR-15, SCR-15 settings; F-12 PMO-0-1) -> D-NOTIFY-MODEL r3, D-ALERT-PREFS-VIEW
PREF_EVENT = O({'key': S(), 'label': S(), 'whatsapp': B, 'email': B, 'timing': S(enum=['immediate', 'daily_digest']), 'timing_label': S(), 'locked_reason': S()}, ['key', 'label', 'whatsapp', 'email'])
PREFS_VIEW = {
    'revision': I(minimum=1), 'events': A(PREF_EVENT),
    'digest_at': O({'value': S(pattern='^[0-2][0-9]:[0-5][0-9]$'), 'options': A(LABELLED)}, ['options']),
    'quiet_hours': O({'value': S(), 'options': A(LABELLED)}, ['options']),
    'whatsapp': O({'masked_number': S(description='e.g. "+234 803 *** 4412"; never unmasked'), 'verified': B}, ['verified']),
    'note': S(description='e.g. "Alerts never include amounts or client details beyond the name."')}
ap = EP_BY_ID['E-ALERT-PREFS']
add_props(ap['request'], {'expected_revision': I(minimum=0), 'events': A(O({'key': S(), 'whatsapp': B, 'email': B}, ['key'])), 'digest_at': S(pattern='^[0-2][0-9]:[0-5][0-9]$'), 'quiet_hours': S()})
ap['request']['properties']['channel']['description'] = 'v6 summary field, kept: the backend derives per-event values from it only when events is absent'
add_props(ap['responses'][0]['schema'], copy.deepcopy(PREFS_VIEW))
nt = EP_BY_ID['E-NOTIFICATIONS']
add_param(nt, P('q', 'query', False, S(description='PROPOSAL (D-ALERT-PREFS-VIEW): search over the alert text and reference')),
          P('agent', 'query', False, AGENT_KEY), P('unread', 'query', False, {'type': 'boolean'}))
add_props(nt['responses'][0]['schema'], {'total': I(), 'unread_count': I()})
add_props(nt['responses'][0]['schema']['properties']['items']['items'], {
    'reference': S(), 'delivered_via': A(S(enum=['whatsapp', 'email', 'in_app'])), 'delivered_at': DT, 'digest_at': DT,
    'in_app_reason': S(description='e.g. "you are not HR": why this alert was shown in the app only')})

# -- Assistant (SCR-05; F-12 PMO-0-2) -> D-CONVERSATION-MODEL r3, D-ASSISTANT-VIEW
cv = EP_BY_ID['E-CONVERSATION']['responses'][0]['schema']
CONV_STATUS = S(enum=['working', 'answered', 'cannot_answer', 'drafted'])
add_props(cv, {'agent': AGENT_KEY, 'title': S(), 'status': CONV_STATUS, 'context': O({'project': CASE_REF, 'access': A(S(description='"Your access" lines as the backend states them'))}, [])})
msg = cv['properties']['messages']['items']
add_props(msg, {
    'at': DT,
    'step_details': A(O({'text': S(), 'state': S(enum=['done', 'now', 'next']), 'reference': LINK}, ['text', 'state'])),
    'handoff': O({'from_agent': AGENT_KEY, 'to': S(), 'note': S()}, ['note']),
    'source_details': A(O({'kind': S(), 'label': S(), 'reference': S(), 'restricted': B, 'link': LINK}, ['kind', 'label', 'restricted'])),
    'cannot_reason': S(),
    'draft': O({'title': S(), 'status_label': S(description='e.g. "DRAFTED · NOT REVIEWED"'), 'rows': A(O({'label': S(), 'value': S(), 'money': MONEY_OR_UNKNOWN('Drafted amount.')}, ['label'])),
                'start': O({'line_key': S(), 'case_id': S(), 'case_revision': I(minimum=1), 'intake': {'type': 'object', 'additionalProperties': True, 'description': 'Prefill for the line\'s E-LINES intake fields; the person reviews it in the normal Start work drawer'}, 'label': S()}, ['line_key', 'label']),
                'next': S(), 'started': O({'work_id': S(), 'reference': S()}, ['work_id'])}, ['title', 'rows']),
})
msg['properties']['draft']['description'] = 'PROPOSAL (D-ASSISTANT-VIEW): a draft is started only through the normal E-WORK-START of its line (D-CONVERSATION-MODEL); started is present once it has been'
add_props(EP_BY_ID['E-MESSAGE']['request'], {'mentions': A(O({'kind': S(enum=['project', 'work', 'document', 'person']), 'id': S()}, ['kind', 'id']))})
add_props(EP_BY_ID['E-ME']['responses'][0]['schema'], {'assistant_agents': A(AGENT_KEY)})
EP_BY_ID['E-ME']['responses'][0]['schema']['properties']['assistant_agents']['description'] = 'PROPOSAL (D-ASSISTANT-VIEW): the agents this person may talk to, as the backend allows'

# -- Projects list and journey (SCR-22, SCR-07, SCR-43; F-07 round 1 left-out elements) -> D-PROJECTS-VIEW
pl = EP_BY_ID['E-PROJECTS']
add_param(pl, P('status', 'query', False, S(enum=['active', 'closed', 'all'], description='PROPOSAL (D-PROJECTS-VIEW): the Active / Closed / All I can see tabs')))
add_props(pl['responses'][0]['schema'], {'counts': O({'active': I(), 'closed': I(), 'all': I()}, []), 'total': I()})
add_props(pl['responses'][0]['schema']['properties']['items']['items'], {'reference': S(), 'next_milestone': O({'name': S(), 'due': DUE}, ['name']), 'needs_person': I(), 'stopped': I()})
pr = EP_BY_ID['E-PROJECT']['responses'][0]['schema']
add_props(pr, {'pm': PERSON, 'route': S(), 'work_count': I(), 'line_count': I(),
               'facts': A(O({'label': S(), 'value': S(), 'money': MONEY_OR_UNKNOWN('Figure amount.'), 'unknown': B}, ['label'])),
               'agent_summary': O({'agent': AGENT_KEY, 'text': S()}, ['agent', 'text']),
               'delivery': A(O({'line_key': S(), 'title': S(), 'state': STATE, 'gate': TAG, 'work_id': S(), 'held_by': HOLDER}, ['line_key', 'title']))})
pr['properties']['delivery']['description'] = 'PROPOSAL (D-PROJECTS-VIEW): the delivery overview (SCR-43), one row per delivery line with its gate status as the backend composes it'
add_props(pr['properties']['lines']['items'], {'reference': S(), 'title': S(), 'detail': S(description='e.g. "Station 2 of 5 · client UAT"'), 'station': O({'index': I(minimum=1), 'count': I(minimum=1), 'name': S()}, ['index', 'count']),
                                               'status_label': S(), 'tone': TONE})
# -- Factory floor lines (SCR-06; F-08 round 1 PMO-0-4) -> D-OVERVIEW-VIEW
ov = EP_BY_ID['E-OVERVIEW']['responses'][0]['schema']
add_props(ov['properties']['lines']['items'], {'key': S(), 'subtitle': S(description='e.g. "RFP · commercial"'), 'agent': AGENT_KEY, 'status': TAG})

# -- new endpoints
PREFS_READ = O(dict({'channel': S(), 'frequency': S()}, **copy.deepcopy(PREFS_VIEW)), ['channel', 'frequency', 'revision', 'events'])
INVOICE_ROW = O({'invoice_id': S(), 'reference': S(), 'client': S(), 'project': CASE_REF, 'issued_on': DATE, 'due': DUE,
                 'invoiced': MONEY_OR_UNKNOWN('Invoiced amount.'), 'received': MONEY_OR_UNKNOWN('Receipts recorded by Finance.'), 'owed': MONEY_OR_UNKNOWN('Still owed, as composed by the backend.'),
                 'status': TAG, 'work_id': S(), 'revision': I(minimum=1), 'reminder': O({'status': S(), 'last_sent_at': DT, 'work_id': S()}, ['status']), 'sample': B}, ['invoice_id', 'reference', 'invoiced', 'received', 'owed'])
EP_V7 = [
 ('E-RFP-FOLLOWUP', 'POST', '/api/v1/work/{work_id}/rfp-outcome/followup', 'Send the drafted RFP follow-up', 'Send follow-up on the outcome-unknown board', 'rfp.outcome on the case, as the backend allows; agents rejected.', 'api.rfp.followup', 'pmo.rfp (follow-up) + outbox', 'R-RESPONSE', ['REC-WORK', 'REC-EVIDENCE', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-RESEND', 'INV-AGENT', 'INV-AUDIT'], ['D-RFP-OUTCOME'], 'T-RESPONSE', 'A-RFP-FOLLOWUP', [P('work_id')],
  O(dict(EXPECTED, version=I(minimum=1, description='rfp_outcome.followup.version being sent'), body=S(description='Edited text; absent sends the draft as is'), idempotency_key=S()), ['expected_revision', 'version', 'idempotency_key']),
  O({'work_id': S(), 'status': S(enum=['sending', 'sent', 'effect_uncertain']), 'revision': I(minimum=1)})),
 ('E-WORK-STEP', 'POST', '/api/v1/work/{work_id}/steps', 'Take a line step', 'A step button in a line workspace (accept a suggestion, record impact, confirm minutes, send a reminder, etc.)', 'The step\'s authority on the line as the backend checks it; agents rejected for steps that approve, send or pay.', 'api.work.step', 'workflows.factory (line step handlers)', 'R-WORKITEM', ['REC-WORK', 'REC-EVIDENCE', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-RESEND', 'INV-AGENT', 'INV-UNKNOWN', 'INV-AUDIT'], ['D-LINE-WORKSPACE'], 'T-WORKSPACE', 'A-WORKSPACE', [P('work_id')],
  O(dict(EXPECTED, step=S(description='One of workspace.steps[].key'), item_ids=A(S()), inputs={'type': 'object', 'additionalProperties': True, 'description': 'Field name to value for the step\'s fields, shaped per field kind as in D-START-INTAKE'},
         case_revision=I(minimum=1), evidence_ids=A(S()), note={'type': 'string', 'description': 'Up to 2000 characters'}, idempotency_key=S()), ['expected_revision', 'step', 'idempotency_key']),
  O({'work_id': S(), 'state': STATE, 'revision': I(minimum=1), 'outcome': S(enum=['done', 'queued', 'effect_uncertain']), 'message': S()}, ['work_id', 'state', 'revision', 'outcome'])),
 ('E-WORK-ASSIGN', 'POST', '/api/v1/work/{work_id}/assignment', 'Assign the accountable person', 'Assign drawer from the Unassigned queue (SCR-24)', 'The assign authority configured for the line (e.g. rfp.assign).', 'api.work.assign', 'pmo.rfp.assign', 'R-START', ['REC-WORK', 'REC-GRANT', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], ['D-RFP-INTAKE'], 'T-ASSIGN', 'A-ASSIGN', [P('work_id')],
  O(dict(EXPECTED, person_id=S(description='One of assign.candidates[].person_id'), note={'type': 'string', 'description': 'Up to 2000 characters'}), ['expected_revision', 'person_id']),
  O({'work_id': S(), 'state': STATE, 'revision': I(minimum=1), 'assigned_to': S()})),
 ('E-ALERT-PREFS-READ', 'GET', '/api/v1/me/alert-preferences', 'Read my alert preferences', 'Alert settings page load', 'Own preferences only.', 'api.me.alert_prefs_read', 'api notifications (new)', 'R-ALERTS', ['REC-ALERT-PREF'], ['INV-ACCESS'], ['D-NOTIFY-MODEL', 'D-ALERT-PREFS-VIEW'], 'T-ALERTS', 'A-ALERT-PREFS', [], None, PREFS_READ),
 ('E-NOTIFICATION-READ', 'POST', '/api/v1/notifications/{notification_id}/read', 'Mark an alert read', 'Open an alert', 'Own notifications only.', 'api.notifications.read', 'api notifications (new)', 'R-ALERTS', ['REC-NOTIFICATION', 'REC-AUDIT'], ['INV-ACCESS', 'INV-AUDIT'], ['D-NOTIFY-MODEL', 'D-ALERT-PREFS-VIEW'], 'T-ALERTS', 'A-NOTIFICATIONS', [P('notification_id')], None,
  O({'id': S(), 'read': B, 'unread_count': I()})),
 ('E-CONVERSATIONS', 'GET', '/api/v1/assistant/conversations', 'My conversations', 'Assistant page side list', 'Own conversations only.', 'api.assistant.list', 'agents (new)', 'R-ASSISTANT', ['REC-CONVERSATION'], ['INV-ACCESS', 'INV-AGENT'], ['D-CONVERSATION-MODEL', 'D-ASSISTANT-VIEW', 'D-PAGING'], 'T-ASSISTANT', 'A-ASSISTANT-THREADS', [P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(O({'conversation_id': S(), 'title': S(), 'agent': AGENT_KEY, 'status': CONV_STATUS, 'status_line': S(description='e.g. "Working · step 3 of 5", "Can\'t share"'), 'updated_at': DT}, ['conversation_id', 'title', 'agent', 'status', 'updated_at']))),
 ('E-MENTION-OPTIONS', 'GET', '/api/v1/assistant/mentions', 'Records I can mention', 'Typing @ in the assistant composer', 'Signed in; only records the person may read.', 'api.assistant.mentions', 'identity.services.visible_cases + domain services', 'R-ASSISTANT', ['REC-CASE', 'REC-WORK', 'REC-DOCUMENT'], ['INV-ACCESS', 'INV-RESTRICTED', 'INV-SAMPLE'], ['D-ASSISTANT-VIEW', 'D-PAGING'], 'T-ASSISTANT', 'A-ASSISTANT-THREADS',
  [P('q', 'query', True), P('kind', 'query', False, S(enum=['project', 'work', 'document', 'person'])), P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(O({'kind': S(enum=['project', 'work', 'document', 'person']), 'id': S(), 'label': S(), 'hint': S(), 'sample': B}, ['kind', 'id', 'label']))),
 ('E-DELEGATIONS', 'GET', '/api/v1/setup/delegations', 'Delegations I can see', 'Setup delegation tab', 'Leads for their own authority; Admin as the backend allows.', 'api.setup.delegations', 'policy.role_assignments', 'R-SETUP', ['REC-CONFIG'], ['INV-ACCESS'], ['D-DELEGATION-VIEW', 'D-PAGING'], 'T-SETUP', 'A-DELEGATIONS', [P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(O({'delegation_id': S(), 'from': PERSON, 'delegate': PERSON, 'authority': S(), 'starts': DATE, 'ends': DATE, 'reason': S(), 'status': S(enum=['scheduled', 'active', 'ended']), 'can_change': B, 'revision': I(minimum=1)}, ['delegation_id', 'from', 'delegate', 'starts', 'status']),
       {'authorities': A(LABELLED), 'delegate_options': A(O({'person_id': S(), 'name': S(), 'role': S()}, ['person_id', 'name'])), 'revision': I(minimum=0)})),
 ('E-PERSON-ROLES', 'PUT', '/api/v1/setup/people/{person_id}/roles', 'Assign roles to a person', 'Assign and resume held work (SCR-13 validation)', 'Role assignment authority as configured (D-ADMIN-AUTHORITY).', 'api.setup.person_roles', 'policy.role_assignments', 'R-SETUP', ['REC-GRANT', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], ['D-PEOPLE-VIEW', 'D-ADMIN-AUTHORITY'], 'T-SETUP-PEOPLE', 'A-PEOPLE-ADMIN', [P('person_id')],
  O(dict(EXPECTED, roles=A(O({'role': S(), 'scope': S()}, ['role'])), reason=S(), resume_held=B), ['expected_revision', 'roles']),
  O({'person_id': S(), 'revision': I(minimum=1), 'resumed': I()}, ['person_id', 'revision'])),
 ('E-INVITE', 'POST', '/api/v1/setup/people/invitations', 'Invite a staff member', 'Invite drawer (SCR-21 invite)', 'Account authority as configured (D-ADMIN-AUTHORITY).', 'api.setup.invite', 'identity services', 'R-SETUP', ['REC-GRANT', 'REC-AUDIT'], ['INV-ACCESS', 'INV-AUDIT'], ['D-PEOPLE-VIEW', 'D-ADMIN-AUTHORITY', 'D-SIGNIN'], 'T-SETUP-PEOPLE', 'A-PEOPLE-ADMIN', [],
  O({'name': S(), 'email': S(), 'roles': A(O({'role': S(), 'scope': S()}, ['role'])), 'idempotency_key': S()}),
  O({'person_id': S(), 'state': S(enum=['invited'])})),
 ('E-DEACTIVATE', 'POST', '/api/v1/setup/people/{person_id}/deactivation', 'Deactivate a staff account', 'Deactivate drawer with reassignment (SCR-21 deactivate)', 'Account authority as configured (D-ADMIN-AUTHORITY).', 'api.setup.deactivate', 'identity services + workflows reassignment', 'R-SETUP', ['REC-GRANT', 'REC-WORK', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], ['D-PEOPLE-VIEW', 'D-ADMIN-AUTHORITY'], 'T-SETUP-PEOPLE', 'A-PEOPLE-ADMIN', [P('person_id')],
  O(dict(EXPECTED, reassign=A(O({'work_id': S(), 'person_id': S()}, ['work_id', 'person_id'])), reason=S()), ['expected_revision', 'reason']),
  O({'person_id': S(), 'state': S(enum=['deactivated']), 'reassigned': I(), 'revision': I(minimum=1)})),
 ('E-TEMPLATE-VERSION', 'POST', '/api/v1/setup/templates/{template_id}/versions', 'Upload a new template version', 'Upload on Setup templates (SCR-34)', 'documents template authority as the backend allows.', 'api.setup.template_version', 'documents services', 'R-SETUP', ['REC-DOCUMENT', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT', 'INV-SAMPLE'], ['D-TEMPLATES-VIEW'], 'T-SETUP', 'A-TEMPLATE-VERSION', [P('template_id')],
  O(dict(EXPECTED, filename=S(), content_base64=S(), note={'type': 'string', 'description': 'Up to 2000 characters'}), ['expected_revision', 'filename', 'content_base64']),
  O({'template_id': S(), 'version': S(), 'test_template': B, 'revision': I(minimum=1)})),
 ('E-COSTING-RULE', 'GET', '/api/v1/setup/costing-rule', 'The costing rule and its versions', 'Setup costing rule tab (SCR-39)', 'policy read for costing; Leads.', 'api.setup.costing_rule', 'policy.services.resolve (costing)', 'R-SETUP', ['REC-CONFIG'], ['INV-ACCESS', 'INV-UNKNOWN'], ['D-SETUP-RULES-VIEW', 'D-COSTING-RULE'], 'T-COSTING-RULE', 'A-COSTING-RULE', [], None,
  O({'versions': A(O({'version': I(minimum=1), 'label': S(), 'status': S(enum=['current', 'proposed', 'withdrawn', 'superseded']), 'proposed_by': PERSON, 'proposed_at': DT, 'reviewed_by': PERSON, 'effective_from': DT}, ['version', 'label', 'status'])),
     'sections': A(copy.deepcopy(WS_SECTION)), 'examples': A(O({'label': S(), 'expected': MONEY_OR_UNKNOWN('Expected result.'), 'computed': MONEY_OR_UNKNOWN('Result under the version.'), 'result': S(enum=['match', 'differs', 'unknown'])}, ['label', 'result'])),
     'review_work_id': S(), 'cannot_review_reason': S(description='e.g. "you proposed this version"'), 'not_set': B}, ['versions', 'not_set'])),
 ('E-INVOICES', 'GET', '/api/v1/finance/invoices', 'Invoices and what is owed', 'Payments and follow-up (SCR-20)', 'finance.read; rows filtered by grants.', 'api.finance.invoices', 'finance services', 'R-FINANCE', ['REC-MONEY'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-FACTS', 'INV-SAMPLE'], ['D-RECEIVABLES-VIEW', 'D-PAGING'], 'T-RECEIVABLES', 'A-RECEIVABLES',
  [P('q', 'query', False), P('status', 'query', False, S(description='One of filters[].value as the backend lists them')), P('client', 'query', False), P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(INVOICE_ROW, {'totals': O({'invoiced': MONEY_OR_UNKNOWN('Total invoiced.'), 'received': MONEY_OR_UNKNOWN('Total received.'), 'owed': MONEY_OR_UNKNOWN('Total owed.')}, []), 'filters': A(LABELLED), 'total': I()})),
 ('E-RECEIPT', 'POST', '/api/v1/finance/invoices/{invoice_id}/receipts', 'Record a receipt', 'Record a payment (SCR-20 record)', 'finance receipt authority as configured; agents rejected.', 'api.finance.receipt', 'finance services (receipts; allocation per D-RECEIPT-ALLOCATION)', 'R-FINANCE', ['REC-MONEY', 'REC-EVIDENCE', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-FACTS', 'INV-UNKNOWN', 'INV-AGENT', 'INV-AUDIT'], ['D-RECEIVABLES-VIEW', 'D-RECEIPT-ALLOCATION'], 'T-RECEIVABLES', 'A-RECEIVABLES', [P('invoice_id')],
  O(dict(EXPECTED, amount=dict(MONEY, description='Amount as on the bank record; must be known to record'), received_on=DATE, bank_reference=S(), evidence_id=S(), case_revision=I(minimum=1), idempotency_key=S()), ['expected_revision', 'amount', 'received_on', 'evidence_id', 'idempotency_key']),
  O({'receipt_id': S(), 'invoice_id': S(), 'revision': I(minimum=1), 'allocation': TAG}, ['receipt_id', 'invoice_id', 'revision'])),
 ('E-CLIENTS', 'GET', '/api/v1/clients', 'Clients', 'Clients page (SCR-35)', 'case.read on at least one of the client\'s cases.', 'api.clients.list', 'pmo client register', 'R-PROJECT', ['REC-CLIENT'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-SAMPLE'], ['D-CLIENTS-VIEW', 'D-PAGING'], 'T-CLIENTS', 'A-CLIENTS', [P('q', 'query', False), P('cursor', 'query', False), PAGE_LIMIT], None,
  LIST(O({'client_id': S(), 'name': S(), 'projects': I(), 'owed': MONEY_OR_UNKNOWN('Owed across visible invoices.'), 'billing_contact_set': B, 'sample': B}, ['client_id', 'name', 'billing_contact_set']))),
 ('E-CLIENT', 'GET', '/api/v1/clients/{client_id}', 'Client detail', 'Open a client (SCR-35 detail)', 'As E-CLIENTS.', 'api.clients.read', 'pmo client register', 'R-PROJECT', ['REC-CLIENT', 'REC-CASE', 'REC-MONEY'], ['INV-ACCESS', 'INV-UNKNOWN', 'INV-FACTS'], ['D-CLIENTS-VIEW'], 'T-CLIENTS', 'A-CLIENTS', [P('client_id')], None,
  O({'client_id': S(), 'name': S(), 'revision': I(minimum=1), 'billing_contact': O({'name': S(), 'email': S(), 'set': B}, ['set']), 'projects': A(O({'case_id': S(), 'title': S(), 'stage': S()}, ['case_id', 'title'])),
     'money': O({'invoiced': MONEY_OR_UNKNOWN('Invoiced.'), 'received': MONEY_OR_UNKNOWN('Received.'), 'owed': MONEY_OR_UNKNOWN('Owed.')}, []), 'blocked': A(S(description='e.g. "Invoices wait until a billing contact is set"')), 'can_change': B, 'sample': B},
    ['client_id', 'name', 'revision', 'billing_contact', 'projects'])),
 ('E-CLIENT-CONTACT', 'PUT', '/api/v1/clients/{client_id}/billing-contact', 'Set the billing contact', 'Billing contact form (SCR-35 detail)', 'client contact authority as the backend allows.', 'api.clients.contact', 'pmo client register', 'R-PROJECT', ['REC-CLIENT', 'REC-AUDIT'], ['INV-ACCESS', 'INV-REVISION', 'INV-AUDIT'], ['D-CLIENTS-VIEW'], 'T-CLIENTS', 'A-CLIENTS', [P('client_id')],
  O(dict(EXPECTED, name=S(), email=S(), reason=S()), ['expected_revision', 'name', 'email']), O({'client_id': S(), 'revision': I(minimum=1)})),
]
for row in EP_V7:
    e = make_endpoint(*row); e['evidence'] = e['evidence'] + ['S-DECISIONS-V6']; endpoints.append(e); EP_BY_ID[e['id']] = e
for eid in ('E-WORK-STEP', 'E-RECEIPT', 'E-PERSON-ROLES', 'E-INVITE', 'E-DEACTIVATE', 'E-TEMPLATE-VERSION', 'E-CLIENT-CONTACT', 'E-WORK-ASSIGN'):
    EP_BY_ID[eid]['responses'] = [r if r['status'] != '422' else copy.deepcopy(FIELDS_422) for r in EP_BY_ID[eid]['responses']]
EP_BY_ID['E-RFP-FOLLOWUP']['failure_recovery'] = 'Idempotent on idempotency_key. A send whose outcome is unknown returns effect_uncertain and blocks any resend until reconciled (INV-RESEND); 409 on a stale revision or draft version.'
EP_BY_ID['E-WORK-STEP']['failure_recovery'] = 'Idempotent on idempotency_key. A step that sends and cannot confirm the send returns effect_uncertain; the work item then offers reconcile, never an automatic retry (INV-RESEND). 409 stale; 422 names fields.'
EP_BY_ID['E-RECEIPT']['failure_recovery'] = 'Idempotent on idempotency_key; a retried request never records a second receipt. 409 stale; 422 names fields. Allocation is composed by the backend and returned, never by the frontend.'
link_eps([('E-EXCEPTIONS', ['D-EXCEPTIONS-LIST'])], 'A-EXCEPTIONS-LIST')
link_eps([('E-WORK-ITEM', ['D-RESPONSE-VIEW', 'D-WORK-ACTIONS-VIEW', 'D-RFP-OUTCOME', 'D-LINE-WORKSPACE', 'D-RFP-INTAKE']), ('E-RESPONSE', ['D-RESPONSE-VIEW']), ('E-WORK-ACTION', ['D-WORK-ACTIONS-VIEW']), ('E-RFP-OUTCOME', ['D-RFP-OUTCOME'])], 'A-WORKSPACE')
link_eps([('E-MONTH-END', ['D-MONTH-END-VIEW'])], 'A-MONTHEND-VIEW')
link_eps([('E-SETUP-RULES', ['D-SETUP-RULES-VIEW']), ('E-SETUP-RULE-SAVE', ['D-SETUP-RULES-VIEW'])], 'A-SETUP-RULES-VIEW')
link_eps([('E-DELEGATION', ['D-DELEGATION-VIEW'])], 'A-DELEGATIONS')
link_eps([('E-PEOPLE', ['D-PEOPLE-VIEW'])], 'A-PEOPLE-ADMIN')
link_eps([('E-TEMPLATES', ['D-TEMPLATES-VIEW'])], 'A-TEMPLATE-VERSION')
link_eps([('E-ALERT-PREFS', ['D-NOTIFY-MODEL', 'D-ALERT-PREFS-VIEW'])], 'A-ALERT-PREFS')
link_eps([('E-NOTIFICATIONS', ['D-NOTIFY-MODEL', 'D-ALERT-PREFS-VIEW'])], 'A-NOTIFICATIONS')
link_eps([('E-CONVERSATION', ['D-CONVERSATION-MODEL', 'D-ASSISTANT-VIEW']), ('E-MESSAGE', ['D-ASSISTANT-VIEW']), ('E-ME', ['D-ASSISTANT-VIEW'])], 'A-ASSISTANT-THREADS')
link_eps([('E-PROJECTS', ['D-PROJECTS-VIEW']), ('E-PROJECT', ['D-PROJECTS-VIEW'])], 'A-PROJECTS-VIEW')
link_eps([('E-OVERVIEW', ['D-OVERVIEW-VIEW'])], 'A-OVERVIEW-LINES')
records.append({'id': 'REC-CLIENT', 'title': 'Client and billing contact (proposed; backend developer to confirm where it lives)', 'refs': ['REC-CASE'], 'evidence': ['S-SCREENS', 'S-DECISIONS-V6'],
                'fields': ['id', 'name', 'billing_contact: name, email', 'revision'], 'relationships': ['REC-CASE'], 'constraints': ['An invoice is not sent without a billing contact (as SCR-35 states; the backend holds the rule)', 'Visible only through a case the person may read'], 'owner': 'pmo (backend developer to confirm)'})

# -- decisions (v7)
def dec7(i, title, owner, scope, status, choice, rationale, alts, refs, ev=('S-DECISIONS-V6', 'S-SCREENS')):
    return dec(i, title, owner, scope, status, choice, rationale, alts, refs, ev)
PROPOSAL = 'PROPOSAL for the backend developer to confirm (drafted overnight by the coordinator for the frontend, S-DECISIONS-V6 (i)): '
decisions += [
    dec7('D-EXCEPTIONS-LIST', 'Search, filter and count on All exceptions', 'backend developer', 'E-EXCEPTIONS; SCR-10', 'proposed',
         PROPOSAL + 'E-EXCEPTIONS accepts optional q (search over title, reference, what is being done, who acts) and what (one kind); the response gains optional open_count (all matching rows the person may see, across pages) and each row an optional ref (the work\'s business reference).',
         'Boards: ' + B_CANVAS + 'SCR-10-desktop.dc.html (search, Filter, "4 OPEN", reference under the title), SCR-10-mobile.dc.html ("Exceptions · 4"). Same names as the F-06 round-2 mock (delivery/features/F-06/round-2/build.md), so its fixtures need no rename. A count the backend does not send is not shown, never guessed.',
         ['Client-side search over the loaded page (wrong across pages)', 'Leave search and count off the screen'], ['R-EXCEPTION']),
    dec7('D-MONTH-END-VIEW', 'What the month-end checklist shows', 'backend developer', 'E-MONTH-END; SCR-36', 'proposed',
         PROPOSAL + 'E-MONTH-END gains optional as_of and coverage, a summary (done, waiting, in progress, total) composed by the backend, cash_received_detail (the known part plus has_unknown), an agent note and a next action (label, work_id); each task gains optional title, detail, status_label, tone, restricted and restricted_label (restricted rows carry no work_id). cash_received keeps its v6 shape.',
         'Boards: ' + F_CANVAS + 'SCR-36-desktop.dc.html (as-of line, four-cell strip "2 of 7 / 3 / 2", "Cash received ₦4.7M + Unknown", task detail and "NEEDS FINANCE DECISION" tags, "HR only" row, Chidi\'s note, "Import the missing statement") and SCR-36-mobile.dc.html. v6 money is all-or-unknown and cannot say "known plus Unknown" (F-10 readiness PMO-0-1). Which month is being closed, what is restricted and every amount are backend facts; the frontend buckets nothing.',
         ['Frontend counts states (puts a rule in the browser)', 'Show cash as Unknown whenever any part is unknown (hides the known part the board shows)'], ['R-FINANCE']),
    dec7('D-LINE-WORKSPACE', 'One typed workspace block per line on the work item, and one step write', 'backend developer', 'E-WORK-ITEM workspace; new E-WORK-STEP; line screens SCR-19..SCR-59', 'proposed',
         PROPOSAL + 'E-WORK-ITEM gains an optional workspace block for the line-specific content of every line screen: line key, screen and board state, title, status, byline, version, project context, an agent note, typed sections (facts, table with typed cells, checklist, findings, suggestions, recipients with receipts, figures, text with cited records, timeline) and the steps this person may take now, each with typed fields (the E-LINES field descriptor) and its consequence sentence. Decisions inside a workspace stay on E-TASK-CLAIM/E-TASK-DECIDE (a step carries task_id); responses stay on E-RESPONSE; reconcile stays on E-WORK-ACTION. Every other line step goes through one new POST /api/v1/work/{work_id}/steps with the step key, item ids, typed inputs, proof, expected revision and an idempotency key; a step that sends and cannot confirm the send returns effect_uncertain.',
         'The 27 screens with no task (delivery/screen-coverage.md) and the Finance line screens (F-10 readiness) are line workspaces: e.g. ' + B_CANVAS + 'SCR-25-desktop-review.dc.html (report sections citing records, "2 RECORDS", "Approving sends this exact version"), SCR-26-desktop.dc.html (requirements matrix with suggestions to accept, edit or reject), SCR-28-desktop-suggesting.dc.html (suggested decisions and actions with owner and due date), SCR-31-desktop-impact.dc.html (impact per team), SCR-44-desktop-readiness.dc.html (readiness checklist), SCR-45-desktop-signatures.dc.html (signatures), SCR-46-desktop-evaluating.dc.html (criteria), SCR-49-desktop-blocked.dc.html (closure blockers), SCR-52-desktop-received.dc.html (receipts per recipient), and ' + F_CANVAS + 'SCR-53..SCR-59 (quarantine findings, review results, schedules by class with Unknown, recipients and receipts). One shared block avoids about 25 endpoints and follows the v6 reconcile and rfp_outcome pattern. Which sections and steps exist, their values, who may take a step and what it does are backend rules; the frontend renders by kind and offers only returned steps. Restricted sections return restricted=true and no rows (INV-RESTRICTED); unknown amounts and dates use the unknown form, never 0.',
         ['One endpoint per line workspace (about 25 reads and writes)', 'Untyped workspace JSON (the mock cannot validate it)'], ['R-WORKITEM', 'R-FINANCE']),
    dec7('D-RFP-INTAKE', 'Logging a received RFP and assigning its accountable person', 'backend developer', 'E-LINES (case_scope fixed), E-WORK-ITEM assign, new E-WORK-ASSIGN; SCR-23, SCR-24', 'proposed',
         PROPOSAL + 'a received RFP starts on a fixed pre-sale intake case the backend names on the line (D-START-INTAKE case_scope fixed), because E-WORK-START requires a case and a new RFP has none; the work item gains an optional assign block (role, candidates, note required) when this person may assign, and a new POST /api/v1/work/{work_id}/assignment records the choice.',
         'Boards: ' + B_CANVAS + 'SCR-23-desktop.dc.html / -mobile (log a received RFP), SCR-24-desktop.dc.html / -mobile (assign the accountable PM from the Unassigned queue). Who may assign ("who may assign an RFP" is a Setup rule) and who the candidates are come from the backend. Whether the backend instead creates the case on start is for the backend developer.',
         ['A start that creates its own case (changes the E-WORK-START contract)', 'Assign through E-TASK-DECIDE'], ['R-START']),
    dec7('D-SETUP-RULES-VIEW', 'What the Setup rule tabs show and save', 'backend developer', 'E-SETUP-RULES, E-SETUP-RULE-SAVE, new E-COSTING-RULE (read only); SCR-13 rules, finance-rules, delivery-rules; SCR-39', 'proposed',
         PROPOSAL + 'E-SETUP-RULES rows gain optional area and group (with labels), used_by, display_value (absent when Not set), link, holds_work, effective_from, can_change, restricted and an editor (role_set with role options, or read_only); the response gains not_set_count and roles_missing_count. E-SETUP-RULE-SAVE accepts expected_revision 0 for the first version of a rule that is Not set (v6 required at least 1, which made A-SETUP impossible) and optional starts, reason and evidence_id. A read-only GET /api/v1/setup/costing-rule returns the rule\'s versions, its content as typed sections, worked examples and the review work item, for display only.',
         'Boards: ' + B_CANVAS + 'SCR-13-desktop-rules.dc.html ("Save as version 1", Roles allowed, Starts, Why, Proof, HOLDS WORK), SCR-13-desktop-finance-rules.dc.html (groups, NOT SET), SCR-13-desktop-delivery-rules.dc.html (USED BY), SCR-39-desktop.dc.html / -review / -example / -review-own (costing versions and examples) and their mobile boards. Only the role-list editor is drawn, so other value kinds stay read-only. Edit controls follow can_change, never /me roles; a missing value is Not set, never a default (REC-CONFIG). How the costing rule is proposed, reviewed and withdrawn is open (D-COSTING-RULE), so no costing write is proposed.',
         ['Rule-specific endpoints per area', 'A create endpoint for the first version'], ['R-SETUP']),
    dec7('D-DELEGATION-VIEW', 'Listing delegations', 'backend developer', 'New E-DELEGATIONS; E-DELEGATION; SCR-13 delegation', 'proposed',
         PROPOSAL + 'a new GET /api/v1/setup/delegations lists the delegations the person may see (from, delegate, authority, starts, ends, reason, status, can_change, revision) with the authorities and delegate options the backend allows; E-DELEGATION gains optional authority and reason.',
         'Boards: ' + B_CANVAS + 'SCR-13-desktop-delegation.dc.html and SCR-13-mobile-delegation.dc.html show current and scheduled delegations; v6 E-DELEGATION is a PUT with nothing to read (F-11 readiness, F-11B). Which authority may be delegated and to whom is the backend\'s rule.',
         ['Read delegations from E-PEOPLE'], ['R-SETUP']),
    dec7('D-PEOPLE-VIEW', 'People, roles and staff accounts', 'backend developer', 'E-PEOPLE; new E-PERSON-ROLES, E-INVITE, E-DEACTIVATE; SCR-13 default, permission, validation; SCR-21', 'proposed',
         PROPOSAL + 'E-PEOPLE rows gain optional person_id, email, scopes, state (active, invited, deactivated), last_signed_in_at, open_items, can_change and revision, and the response the missing roles (with held work) and role options; three proposed writes assign roles (optionally resuming held work), invite a staff member and deactivate an account with reassignment of open items. The writes are gated by D-ADMIN-AUTHORITY; invite also depends on D-SIGNIN.',
         'Boards: ' + B_CANVAS + 'SCR-13-desktop.dc.html ("Roles · 2 missing"), SCR-13-desktop-validation.dc.html ("Assign and resume held work"), SCR-13-desktop-permission.dc.html, SCR-21-desktop.dc.html, SCR-21-desktop-invite.dc.html, SCR-21-desktop-deactivate.dc.html and their mobile boards. Who holds Admin and who may assign roles is PSL\'s to name (design/screens.md); the contract carries only what the backend allows.',
         ['Leave staff accounts in Django admin'], ['R-SETUP']),
    dec7('D-TEMPLATES-VIEW', 'Template list detail and versioned upload', 'backend developer', 'E-TEMPLATES; new E-TEMPLATE-VERSION; SCR-34', 'proposed',
         PROPOSAL + 'E-TEMPLATES rows gain optional template_id, kind, updated_at, updated_by, versions, revision and can_upload; a new POST /api/v1/setup/templates/{template_id}/versions uploads a new version with the expected revision; test_template is returned by the backend, never set by the frontend.',
         'Boards: ' + B_CANVAS + 'SCR-34-desktop.dc.html and SCR-34-mobile.dc.html (versioned upload). PSL supplies real templates; until then they are test templates (13 Nov decision).',
         ['Upload through E-EVIDENCE-UPLOAD (templates have no case)'], ['R-SETUP']),
    dec7('D-ALERT-PREFS-VIEW', 'What the alert settings and notification centre show', 'backend developer', 'New E-ALERT-PREFS-READ, E-NOTIFICATION-READ; E-ALERT-PREFS; E-NOTIFICATIONS; SCR-15', 'proposed',
         PROPOSAL + 'a new GET /api/v1/me/alert-preferences returns the v6 channel and frequency plus revision, per-event rows (key, label, WhatsApp, email, timing), digest time and quiet hours with their options, and the WhatsApp number masked with its verified flag; PUT accepts optional expected_revision, events, digest_at and quiet_hours and keeps channel and frequency required; E-NOTIFICATIONS accepts optional q, agent and unread and returns total and unread_count, each alert its reference, how and when it was delivered, its digest time and why it was in the app only; a new POST /api/v1/notifications/{id}/read marks one alert read.',
         'Boards: ' + B_CANVAS + 'SCR-15-desktop-settings.dc.html (WHEN / WHATSAPP / EMAIL / TIMING rows, "Daily digest at 08:00", "Quiet hours 20:00 to 07:00, and weekends", "+234 803 *** 4412 · verified"), SCR-15-mobile-settings.dc.html, SCR-15-desktop.dc.html ("4 ALERTS", "WhatsApp and email · 10:42", "In app only (you are not HR)", NEW). Which events exist, which channels a restricted alert may use and what quiet hours suppress are backend rules. The number is never unmasked. Keeping channel/frequency as required summaries is the additive choice; whether to retire them is for the backend developer (F-12 PMO-0-1 e).',
         ['Opening an alert marks it read (no write; NEW would clear on any fetch)', 'Replace channel/frequency (breaks v6 PUT bodies)'], ['R-ALERTS', 'D-NOTIFY-MODEL']),
    dec7('D-ASSISTANT-VIEW', 'What the assistant screens show', 'backend developer', 'New E-CONVERSATIONS, E-MENTION-OPTIONS; E-CONVERSATION; E-MESSAGE; E-ME; SCR-05', 'proposed',
         PROPOSAL + 'a conversation list (title, agent, status, status line, updated), the conversation\'s agent, title, status and context (project, "Your access"), per message typed steps (done, now, next, with a record reference), a handoff note, source details with links, why it cannot answer, and a draft (title, label/value rows, status label, what to start: line, case, revision and intake prefill for the normal Start work drawer, and the started work once started); E-MESSAGE accepts mentions, with a new mention search over records the person may read; /me lists the agents this person may talk to.',
         'Boards: ' + B_CANVAS + 'SCR-05-desktop.dc.html (side list "Drafted · ready to start", "Working · step 3 of 5"), SCR-05-desktop-thread.dc.html (steps, sources, draft rows with "₦6,800,000.00"), SCR-05-desktop-draft-started.dc.html, SCR-05-desktop-cant.dc.html ("Can\'t share"), SCR-05-desktop-working.dc.html and their mobile boards. A draft starts only through E-WORK-START (D-CONVERSATION-MODEL); answers use only records the person may read (INV-RESTRICTED). Attachments and speech input are not proposed (D-SPEECH-INPUT open).',
         ['Stateless assistant with no list', 'Start drafts from the assistant directly (bypasses the line)'], ['R-ASSISTANT']),
    dec7('D-PROJECTS-VIEW', 'Projects list, project journey and delivery overview detail', 'backend developer', 'E-PROJECTS, E-PROJECT; SCR-22, SCR-07, SCR-43', 'proposed',
         PROPOSAL + 'E-PROJECTS accepts an optional status (active, closed, all) and returns counts per status and a total; rows gain reference, next milestone (name, due or unknown), needs_person and stopped counts. E-PROJECT gains pm, route, work and line counts, a facts strip, an agent summary, per-line reference, title, detail, station, status label and tone, and a delivery block (one row per delivery line with its gate status) for the delivery overview.',
         'Boards: ' + B_CANVAS + 'SCR-22-desktop.dc.html (Active / Closed / All I can see tabs with counts, NEXT MILESTONE, NEEDS A PERSON, STOPPED, "5 PROJECTS"), SCR-07-desktop.dc.html (PM and route sub-line, six-cell facts strip, RFP-0031, "Station 2 of 5 · client UAT", Tola\'s summary), SCR-43-desktop.dc.html (six delivery lines with gate status). F-07 left these out because v6 had no field (delivery/features/F-07/round-1/build.md). Counts are composed from authorised records by the backend, never by the frontend.',
         ['Frontend counts lines by state (puts a rule in the browser)'], ['R-PROJECT']),
    dec7('D-OVERVIEW-VIEW', 'Factory floor line labels', 'backend developer', 'E-OVERVIEW; SCR-06', 'proposed',
         PROPOSAL + 'each E-OVERVIEW line gains an optional key, subtitle, agent and status (label and tone).',
         'Board: ' + B_CANVAS + 'SCR-06-desktop.dc.html (lines "Pre-sale · RFP · commercial · 1 WAITING", "Payroll · Restricted · 2 PROBLEMS", "ON TRACK"). F-08 drew no avatar, subtitle or tag colour because v6 had none (delivery/features/F-08/round-1/build.md PMO-0-4). Tones are display hints chosen by the backend.',
         ['Parse colours from note (a rule in the browser)'], ['R-OVERVIEW']),
    dec7('D-RECEIVABLES-VIEW', 'Finance-wide invoices, receipts and reminders', 'backend developer', 'New E-INVOICES, E-RECEIPT; SCR-20, SCR-32', 'proposed',
         PROPOSAL + 'a new GET /api/v1/finance/invoices lists invoices with invoiced, received and owed (each may be unknown), status, reminder and totals, filtered by q, status and client; a new POST /api/v1/finance/invoices/{id}/receipts records one receipt (known amount, date, bank reference, proof, idempotency key) and returns the allocation status the backend composed. The payment reminder (SCR-32) is the reminder line\'s workspace (D-LINE-WORKSPACE). The short-payment decision stays parked (D-DECISION-VARIANTS).',
         'Boards: ' + F_CANVAS + 'SCR-20-desktop.dc.html (invoiced, received, owed with Unknown), SCR-20-desktop-record.dc.html (record a payment with bank reference and proof), SCR-32-desktop.dc.html (reminder draft, edit, send) and their mobile boards. Stages, invoices, receipts and allocations are separate (AGENTS.md); how a receipt is allocated and what a short payment does are not decided (D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS), so the receipt write is gated and nothing here erases debt.',
         ['Per-project money tab only (no Finance-wide view)', 'Record receipts through E-WORK-STEP'], ['R-FINANCE']),
    dec7('D-CLIENTS-VIEW', 'Client register and billing contact', 'backend developer', 'New E-CLIENTS, E-CLIENT, E-CLIENT-CONTACT; new REC-CLIENT; SCR-35', 'proposed',
         PROPOSAL + 'a client list (name, projects, owed, billing contact set), a client detail (billing contact, projects, money, what is blocked) and a PUT that sets the billing contact with the expected revision.',
         'Boards: ' + B_CANVAS + 'SCR-35-desktop.dc.html, SCR-35-desktop-detail.dc.html and their mobile boards (billing contact that blocks invoices until set). Where client records live in the backend is for the backend developer (REC-CLIENT is proposed).',
         ['Clients as project fields only'], ['R-PROJECT']),
    # open decisions raised for PSL or the backend developer; the screens that depend on them are gated
    dec7('D-SIGNIN', 'How people sign in, sign out and reset a password in the new frontend', 'backend developer', 'SCR-17 (sign in, error, reset, setup); SCR-15 account menu sign-out; E-INVITE', 'open',
         'Not decided. D-AUTH keeps the Django session; whether the Next.js app renders sign-in through new session endpoints or the Django sign-in pages are styled to the boards, and how reset and invite set-up work, are for the backend developer. No sign-in endpoint is proposed.',
         'Boards: ' + B_CANVAS + 'SCR-17-desktop.dc.html, -error, -reset, -setup and their mobile boards; SCR-15-desktop-account.dc.html "Sign out". Sign-in is a security boundary; designing it from the frontend would set the backend\'s auth design.',
         ['Session endpoints under /api/v1/session', 'Styled Django sign-in templates'], ['R-SESSION', 'D-AUTH']),
    dec7('D-ADMIN-AUTHORITY', 'Who holds Admin and who may assign roles, invite and deactivate', 'business owner', 'SCR-13 roles, SCR-21; E-PERSON-ROLES, E-INVITE, E-DEACTIVATE', 'open',
         'Not decided. PSL names who holds Admin and who may assign roles, invite and deactivate staff; Admin confers no approval authority (guide/10-POLICY-CONFIGURATION.md). The proposed writes stay gated until then.',
         'design/screens.md lists "who holds Admin" for PSL to confirm; F-11 readiness F-11C. Inventing it would name approvers.', ['Leads manage their own team', 'One named Admin'], ['R-SETUP']),
    dec7('D-PAYROLL-VISIBILITY', 'Which payroll fields are restricted and who may change that', 'business owner', 'SCR-13 fields; E-SETUP-RULES area payroll_visibility', 'open',
         'Not decided. Proposed shape only: payroll field visibility would be Setup rules in area payroll_visibility with a role_set editor, read through E-SETUP-RULES. Which fields are configurable and that the HR Lead decides are for PSL to confirm; INV-RESTRICTED stays enforced by the backend whatever is configured.',
         'Boards: ' + B_CANVAS + 'SCR-13-desktop-fields.dc.html and SCR-13-mobile-fields.dc.html. Restricted payroll data is a security boundary owned by HR (F-11 readiness F-11E).', ['A separate payroll visibility endpoint'], ['R-SETUP', 'R-FINANCE']),
    dec7('D-COSTING-RULE', 'The studio-wide costing rule: shape, review and withdrawal', 'business owner with the backend developer', 'SCR-39; SCR-27; E-COSTING-RULE', 'open',
         'Not decided. How a costing rule version is proposed, who reviews it (the proposer may not review their own, 12 Nov), how worked examples are checked, how a version is withdrawn, and the backend change to one studio-wide rule are for PSL and the backend developer. v7 proposes only a read for display (E-COSTING-RULE).',
         'Boards: ' + B_CANVAS + 'SCR-39-desktop.dc.html, -review, -example, -review-own; SCR-27-desktop.dc.html, -adjust, -ask, -approvals. Costing is a financial rule; design/screens.md notes "backend change needed".', ['Keep per-project costing rules'], ['R-SETUP', 'D-APPROVAL-ORDER']),
    dec7('D-CHANGE-DECIDERS', 'Who decides a change request', 'business owner', 'SCR-31 decision and authorise', 'open',
         'Not decided. Whether a change request needs all five deciders drawn or only some, and in which order, is for PSL; the decision view shows only the chain the backend returns (D-TASK-DECISION-VIEW).',
         'Board: ' + B_CANVAS + 'SCR-31-desktop-decision.dc.html and -authorise ("does the change need all five deciders or only some?", delivery/screen-coverage.md).', ['All five', 'Only the affected teams'], ['R-DECIDE']),
    dec7('D-RECEIPT-ALLOCATION', 'How a recorded receipt is allocated, and who records it', 'business owner with the backend developer', 'E-RECEIPT; SCR-20 record', 'open',
         'Not decided. How a receipt is allocated to invoices and stages, what happens on a part payment, and which role records receipts are financial rules for PSL and the backend developer. The receipt write stays gated; payment exceptions stay under D-DECISION-VARIANTS and never erase debt.',
         'Board: ' + F_CANVAS + 'SCR-20-desktop-record.dc.html. Receipts and allocations are separate records (AGENTS.md product invariants).', ['Oldest invoice first', 'Allocation chosen by the person recording'], ['R-FINANCE']),
    dec7('D-SPEECH-INPUT', 'Speech input in the assistant', 'business owner', 'SCR-05 "Speak your request"', 'open',
         'Not decided. Browser speech recognition can send audio to the browser maker, an external connection not authorised in this phase. Options: build the control wired to nothing, use an approved local engine, or record a fidelity exception.',
         'Boards: ' + B_CANVAS + 'SCR-05-desktop.dc.html and SCR-05-mobile.dc.html composer (F-12 readiness PMO-0-9).', ['Browser speech API', 'Local engine', 'Omit by fidelity exception'], ['R-ASSISTANT']),
    dec7('D-ALERTS-ENTRY', 'Where the bell sits and where the account menu links go', 'design engineer', 'SCR-15 account menu; the bell; top bar', 'open',
         'Not decided. No approved board draws the bell (only the site map says "Bell, top right"); the account menu links "My roles" and "Delegate while away" to nothing, and no phone board shows how the account page opens.',
         'Boards: ' + B_CANVAS + 'SCR-15-desktop-account.dc.html, SCR-15-mobile-account.dc.html, SITEMAP-desktop.dc.html (F-12 readiness PMO-0-6, PMO-0-7). A drawing question for the design engineer, not a backend rule.', ['Draw the bell on the top bar', 'Notifications from the account menu only'], ['R-ALERTS']),
]
# revisions of existing proposals (each stays proposed and owned by the backend developer)
add_rev('D-RESPONSE-VIEW', 'proposed', PROPOSAL + 'r1 plus, on tasks[].response: intro, proof_hint, agent_note, the channels a response may have been received by, context (project, document), next lines and a recorded block (by, at, received via, proof count, summary); variants go_live_acceptance and support_handover (go-live signatures recorded by the PM, Support\'s reply recorded by the PM); E-RESPONSE accepts received_via and returns revision, recorded and next.',
        'F-09 readiness PMO-0-1: ' + B_CANVAS + 'SCR-16-desktop.dc.html:20 (intro), :34 (proof hint), :46-47 (Tola\'s aside), SCR-16-desktop-success.dc.html:17 ("received by email", recorded by and at, "1 proof file", what happens next), SCR-16-desktop-sow-signed.dc.html:17 (project crumb, "the SOW\'s 4 stages become the project\'s milestones"); SCR-45-desktop-signatures.dc.html and SCR-48-desktop-record.dc.html record go-live signatures and Support\'s reply. Every sentence is composed by the backend from records, so the mock can hold it under additionalProperties false.',
        ['A fidelity exception with static board copy (F-09 PMO-0-1 b)'], ['S-DECISIONS-V6', 'S-SCREENS'])
add_rev('D-WORK-ACTIONS-VIEW', 'proposed', PROPOSAL + 'r1 plus reconcile.unknown_note and reconcile.resend_note, and an optional case_revision on E-WORK-ACTION for the proof upload that precedes a reconcile.',
        'F-09 readiness PMO-0-1 and PMO-0-5: ' + B_CANVAS + 'SCR-02-desktop-awaiting-reconciliation.dc.html:17 ("Keep it held and remind me tomorrow", "A resend reuses the same invoice number"); E-EVIDENCE-UPLOAD says to send its case_revision on the action that follows, which E-WORK-ACTION could not carry. What "can\'t tell yet" does and what a resend reuses are backend rules stated by the backend.',
        ['Static board copy'], ['S-DECISIONS-V6', 'S-SCREENS'])
add_rev('D-RFP-OUTCOME', 'proposed', PROPOSAL + 'r1 plus an RFP frame on the work item (reference, title, client, status tag with days left, PM, five tabs with counts), and on rfp_outcome: lesson categories, a recorded block with what\'s recorded rows, reminder holder and time, categorised lessons, the debrief proof, the archive reference, the engagement created and next lines, and a follow-up the agent drafted (recipient as returned, body, version, checks, status, can send, can edit). A new POST /api/v1/work/{work_id}/rfp-outcome/followup sends that draft (optionally edited) with the expected revision, draft version and an idempotency key; an unknown outcome returns effect_uncertain and blocks a resend until reconciled. E-RFP-OUTCOME accepts lessons_items.',
        'F-09 readiness PMO-0-2: ' + B_CANVAS + 'SCR-16-desktop-team-input.dc.html:17 and -rfp-outcome.dc.html:17 (frame: "DEADLINE 28 NOV · 16 DAYS", "PM TUNDE BELLO", "Requirements 64", "Team input 2/4"), SCR-16-desktop-rfp-lost.dc.html (PRICE, TIMELINE, STRENGTH lessons, "Debrief notes (proof)", ARC-0117), SCR-16-desktop-rfp-won.dc.html ("Engagement EN-0042 created"), SCR-16-desktop-rfp-pending.dc.html ("Reminder for Tunde Bello · 10 DEC 09:00"), SCR-16-desktop-rfp-unknown.dc.html (follow-up to the procurement address, "It goes only if you send it", Send follow-up, Edit). The send is external messaging, so it is a person\'s action with idempotency and uncertain-effect handling (INV-RESEND, INV-AGENT); the email provider stays open (D-ALERT-PROVIDERS). Who may send is a backend rule.',
        ['Send follow-ups through E-WORK-STEP', 'Leave the follow-up unbuilt'], ['S-DECISIONS-V6', 'S-SCREENS'])
add_rev('D-NOTIFY-MODEL', 'proposed', 'Unchanged storage choice (Notification and AlertPreference records, outbox, mock adapter until I-03), extended as a PROPOSAL for the backend developer: AlertPreference holds per-event WhatsApp and email choices, a digest time, quiet hours and a revision, and keeps channel and frequency as summaries; Notification records how and when it was delivered (or why it stayed in the app) and when it was read, and read is changed only by the mark-read write. Retention and storage details stay the backend developer\'s.',
        'F-12 readiness PMO-0-1: the approved settings board is a per-event matrix with digest time, quiet hours and a verified WhatsApp number, which one channel and one frequency cannot store (' + B_CANVAS + 'SCR-15-desktop-settings.dc.html). Screen fields are in D-ALERT-PREFS-VIEW.',
        ['In-app only for v1', 'One channel and frequency per person (r2)'], ['S-DECISIONS-V6', 'S-SCREENS'])
add_rev('D-CONVERSATION-MODEL', 'proposed', 'Unchanged choice (Conversation and Message records per person, cited records and the agent run on each answer, drafts only through the normal line start), extended as a PROPOSAL for the backend developer: a Conversation stores its agent, title, status and project context; a Message stores typed steps, a handoff note, source details, the reason it cannot answer, and a draft with what to start and the started work once started. Retention and storage details stay the backend developer\'s.',
        'F-12 readiness PMO-0-2: a page reload loses the status today, steps are strings and drafts have no shape (' + B_CANVAS + 'SCR-05-desktop-thread.dc.html, -draft-started, -working). Screen fields are in D-ASSISTANT-VIEW.',
        ['Stateless assistant', 'r2 shape'], ['S-DECISIONS-V6', 'S-SCREENS'])

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
    SC('A-NOT-YOURS', 'Why a person cannot act, and who was asked instead', 'R-DECIDE', 'Invoice v2 waiting for a Finance Lead: a Finance user, its preparer, the Finance Lead after approving, and a CEO before the PMO Lead has approved a costing', 'Each reads the work item',
       'Each gets you_can_act=false with cannot_act_reason not_your_role, prepared_by_you, already_decided or not_your_turn and the people asked; the eligible Finance Lead gets the decision view with version, amount (unknown=true and no value when unknown, never 0), basis, recipient, changes and chain with your_step; values come from records, none from the frontend'),
    SC('A-DECIDE-VARIANTS', 'Payment exception, CEO final costing and CTO emergency decisions', 'R-DECIDE', 'D-DECISION-VARIANTS settled by PSL and the backend developer', 'Each variant is decided',
       'Defined when D-DECISION-VARIANTS is decided; no verdict, rule or approver is assumed before then'),
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
BE = 'backend developer'; FE = 'frontend developer'
tasks = [
    T('T-FOUNDATION', 'API: apps/api, session and CSRF, error shape, /me', by_task['T-FOUNDATION'], ['R-SESSION'], [], [], ['A-ME'], BE),
    T('T-FRONTEND-SHELL', 'Frontend: Next.js app, design system tokens and components, top bar, phone bar, API client with mock server from openapi.json', [], ['R-FRONTEND', 'R-DEVICES', 'R-SAMPLE'], [], [], ['A-ACCESSIBILITY'], FE),
    T('T-MYWORK', 'API: My work queues', by_task['T-MYWORK'], ['R-MYWORK', 'R-VOLUME'], [], ['T-FOUNDATION'], ['A-MYWORK'], BE),
    T('T-WORKITEM', 'API: work item and history', by_task['T-WORKITEM'], ['R-WORKITEM'], [], ['T-FOUNDATION'], ['A-WORKITEM', 'A-HISTORY', 'A-NOT-YOURS'], BE),
    T('T-DECIDE', 'API: claim and decide one exact version', by_task['T-DECIDE'], ['R-DECIDE'], [], ['T-WORKITEM'], ['A-DECIDE', 'A-STALE'], BE),
    T('T-START', 'API: lines and start work', by_task['T-START'], ['R-START'], ['D-LEADERS-START'], ['T-FOUNDATION'], ['A-START'], BE),
    T('T-RESPONSE', 'API: evidence upload and recorded responses', by_task['T-RESPONSE'], ['R-RESPONSE'], [], ['T-FOUNDATION'], ['A-RESPONSE'], BE),
    T('T-EXCEPTIONS', 'API: exceptions and work actions', by_task['T-EXCEPTIONS'], ['R-EXCEPTION'], ['D-RETURN'], ['T-DECIDE'], ['A-RECONCILE', 'A-RESUME'], BE),
    T('T-PROJECTS', 'API: projects, tabs, documents, reports', by_task['T-PROJECTS'], ['R-PROJECT', 'R-REPORTS'], [], ['T-FOUNDATION'], ['A-PROJECT', 'A-REPORT'], BE),
    T('T-FLOOR', 'API: overview counts', by_task['T-FLOOR'], ['R-OVERVIEW'], [], ['T-FOUNDATION'], ['A-OVERVIEW'], BE),
    T('T-FINANCE', 'API: month-end and imports', by_task['T-FINANCE'], ['R-FINANCE'], [], ['T-FOUNDATION'], ['A-MONTHEND'], BE),
    T('T-PAYROLL', 'API: payroll match (restricted)', by_task['T-PAYROLL'], ['R-FINANCE'], [], ['T-FOUNDATION'], ['A-PAYROLL'], BE),
    T('T-SETUP', 'API: rules, people, delegation, templates', by_task['T-SETUP'], ['R-SETUP'], [], ['T-FOUNDATION'], ['A-SETUP'], BE),
    T('T-ALERTS', 'API: notifications and alert preferences (mock adapter)', by_task['T-ALERTS'], ['R-ALERTS'], ['D-ALERT-PROVIDERS'], ['T-DECIDE'], ['A-ALERTS'], BE),
    T('T-ASSISTANT', 'API: assistant conversations', by_task['T-ASSISTANT'], ['R-ASSISTANT'], ['D-AGENT-PROVIDER'], ['T-START'], ['A-ASSISTANT'], BE),
    T('T-BACKEND-ROLES', 'Backend: PMO Lead for Head of PMO, three-step approvals, leaders may start every line', [], ['R-ROLES'], [], [], ['A-START'], BE),
    # frontend work: built against openapi.json with a mock server; no backend decision gates
    T('FE-MYWORK', 'Frontend: My work, three queues, Decide/Do/Fix, search, filter, 10/20/50 rows', [], ['R-MYWORK', 'R-VOLUME', 'R-SAMPLE'], ['D-PAGING', 'D-UPDATES'], ['T-FRONTEND-SHELL'], ['A-MYWORK'], FE),
    T('FE-WORKITEM', 'Frontend: work item, stations, facts, agent checklist, history', [], ['R-WORKITEM'], ['D-UPDATES'], ['T-FRONTEND-SHELL'], ['A-WORKITEM', 'A-HISTORY'], FE),
    T('FE-DECIDE', 'Frontend: standard decision panel and phone action bar (approve, return, reject; stale-version reload; not yours; own work)', [], ['R-DECIDE'], [], ['T-FRONTEND-SHELL'], ['A-DECIDE', 'A-STALE', 'A-NOT-YOURS'], FE),
    T('FE-DECIDE-VARIANTS', 'Frontend: payment-exception, CEO final costing and CTO emergency decision variants (parked)', [], ['R-DECIDE'], ['D-DECISION-VARIANTS'], ['FE-DECIDE'], ['A-DECIDE-VARIANTS'], FE),
    T('FE-CONNECT-1', 'Connect the first feature to the real API', [], ['R-SESSION', 'R-MYWORK', 'R-WORKITEM', 'R-DECIDE'], [], ['FE-MYWORK', 'FE-WORKITEM', 'FE-DECIDE', 'T-FOUNDATION', 'T-MYWORK', 'T-WORKITEM', 'T-DECIDE'], ['A-ME', 'A-MYWORK', 'A-WORKITEM', 'A-DECIDE', 'A-STALE', 'A-NOT-YOURS'], FE),
    dict(T('FE-M2', 'Frontend: start work drawers, record a response, exceptions (retired 14 Nov 2026: split into FE-M2A and FE-M2B)', [], ['R-START', 'R-RESPONSE', 'R-EXCEPTION'], [], ['T-FRONTEND-SHELL'], ['A-START', 'A-RESPONSE', 'A-RECONCILE'], FE), status='retired'),
    dict(T('FE-M3', 'Frontend: projects, overview and factory floor, Finance, payroll, setup (retired 14 Nov 2026: split into FE-M3-PROJECTS, -OVERVIEW, -FINANCE, -SETUP)', [], ['R-PROJECT', 'R-REPORTS', 'R-OVERVIEW', 'R-MOTION', 'R-FINANCE', 'R-SETUP'], [], ['T-FRONTEND-SHELL'], ['A-PROJECT', 'A-OVERVIEW', 'A-MONTHEND', 'A-PAYROLL', 'A-SETUP'], FE), status='retired'),
    dict(T('FE-M2A', 'Frontend: Start work button and line intake drawers', [], ['R-START'], [], ['T-FRONTEND-SHELL'], ['A-START'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M2B', 'Frontend: record a client response and the all-exceptions list', [], ['R-RESPONSE', 'R-EXCEPTION'], [], ['FE-WORKITEM'], ['A-RESPONSE', 'A-RECONCILE'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M3-PROJECTS', 'Frontend: projects list, project journey and project tabs', [], ['R-PROJECT'], [], ['T-FRONTEND-SHELL'], ['A-PROJECT'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M3-OVERVIEW', 'Frontend: overview, factory floor and reports', [], ['R-OVERVIEW', 'R-MOTION', 'R-REPORTS'], [], ['T-FRONTEND-SHELL'], ['A-OVERVIEW'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M3-FINANCE', 'Frontend: Finance month end, import and payroll', [], ['R-FINANCE'], [], ['T-FRONTEND-SHELL'], ['A-MONTHEND', 'A-PAYROLL'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M3-SETUP', 'Frontend: setup, rules, people and templates', [], ['R-SETUP'], [], ['T-FRONTEND-SHELL'], ['A-SETUP'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
    dict(T('FE-M4', 'Frontend: notification centre, alert settings, assistant', [], ['R-ALERTS', 'R-ASSISTANT'], [], ['T-FRONTEND-SHELL'], ['A-ALERTS', 'A-ASSISTANT'], FE), evidence=['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V4']),
]
for t in tasks:
    if t['id'] == 'T-ALERTS': t['refs'] += ['I-ALERTS', 'JOB-ALERTS']
    if t['id'] == 'T-ASSISTANT': t['refs'] += ['I-AGENT', 'JOB-ASSISTANT']
milestones = [
    {'id': 'M-1', 'title': 'First feature, frontend: My work and one decision against the API contract', 'refs': ['T-FRONTEND-SHELL', 'FE-MYWORK', 'FE-WORKITEM', 'FE-DECIDE', 'D-FIRST-FEATURE'], 'evidence': ['S-SCREENS', 'S-DECISIONS-V2'], 'owner_role': 'delivery owner',
     'exit_criteria': ['Screens match the approved canvas on desktop and phone', 'A-ACCESSIBILITY passes', 'Runs on the mock server built from openapi.json with sample data'], 'gate_ids': ['D-FIRST-FEATURE', 'D-PAGING', 'D-UPDATES']},
    {'id': 'M-1B', 'title': 'First feature, backend: the API for My work and decisions', 'refs': ['T-FOUNDATION', 'T-MYWORK', 'T-WORKITEM', 'T-DECIDE'], 'evidence': ['S-BACKEND'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-ME, A-MYWORK, A-WORKITEM, A-HISTORY, A-DECIDE, A-STALE, A-NOT-YOURS pass on PostgreSQL'], 'gate_ids': ['D-API-STYLE', 'D-AUTH']},
    {'id': 'M-1C', 'title': 'First feature connected end to end', 'refs': ['FE-CONNECT-1'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['The frontend runs on the real API with sample data; the same scenarios pass'], 'gate_ids': []},
    {'id': 'M-2', 'title': 'Start, respond and recover', 'refs': ['T-START', 'T-RESPONSE', 'T-EXCEPTIONS', 'T-BACKEND-ROLES', 'FE-M2', 'FE-M2A', 'FE-M2B', 'FE-DECIDE-VARIANTS'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-START, A-RESPONSE, A-RECONCILE, A-RESUME pass', 'A-DECIDE-VARIANTS passes once D-DECISION-VARIANTS is decided'], 'gate_ids': ['D-RETURN', 'D-DECISION-VARIANTS']},
    {'id': 'M-3', 'title': 'Projects, overview, Finance, payroll and setup', 'refs': ['T-PROJECTS', 'T-FLOOR', 'T-FINANCE', 'T-PAYROLL', 'T-SETUP', 'FE-M3', 'FE-M3-PROJECTS', 'FE-M3-OVERVIEW', 'FE-M3-FINANCE', 'FE-M3-SETUP'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-PROJECT, A-REPORT, A-OVERVIEW, A-MONTHEND, A-PAYROLL, A-SETUP pass'], 'gate_ids': []},
    {'id': 'M-4', 'title': 'Alerts and assistant', 'refs': ['T-ALERTS', 'T-ASSISTANT', 'FE-M4'], 'evidence': ['S-SCREENS'], 'owner_role': 'delivery owner',
     'exit_criteria': ['A-ALERTS and A-ASSISTANT pass on mock and synthetic providers'], 'gate_ids': ['D-ALERT-PROVIDERS', 'D-AGENT-PROVIDER', 'D-NOTIFY-MODEL', 'D-CONVERSATION-MODEL']},
]

# ---- v6 (S-DECISIONS-V5): scenarios, frontend task split, milestones and coverage for the proposals above
def SC6(*a):
    s = SC(*a); s['evidence'] = ['S-SCREENS', 'S-DECISIONS-V5']; return s
scenarios += [
    SC6('A-START-INTAKE', 'Start work drawers are built from what the backend returns', 'R-START', 'A PM with factory.start on two projects, a Finance user with the back-office lines, a CEO, and a milestone that is not complete',
        'Each opens Start work, chooses a line and fills its intake', 'Fields render by their defined kind; record options come from E-LINE-OPTIONS filtered by grants and narrowed by the parent field; the case and its revision come from the chosen project or the line\'s fixed case; proof is uploaded first and sent as an evidence_id; a blank money value is sent as unknown, never 0; the CEO\'s main button opens the menu because no default_line is returned; a 422 names each field'),
    SC6('A-RFP-OUTCOME', 'Record an RFP outcome against one submission', 'R-RESPONSE', 'A submitted RFP whose work item returns rfp_outcome, and a person not among the record_as roles',
        'Record won with the award letter; record lost with reason and lessons; record pending; the other person opens the RFP', 'Each is stored once with its proof and the role recorded as; an unknown awarded amount stays unknown; lost lessons are kept; the person not allowed sees no outcome form (no rfp_outcome block); a stale revision returns 409'),
    SC6('A-PROJECT-TABS', 'Project tabs show typed rows with separate facts', 'R-PROJECT', 'A project with four milestones (one amount unknown, one change with unknown amount), registers, documents and nine actions (three overdue, one without owner)',
        'Read each tab', 'Rows match their tab\'s shape; unknown amounts have unknown=true and no value; completion, invoice and paid are separate; register filter and search narrow rows; action summary counts match the rows; tab counts match E-PROJECT'),
]
for s in scenarios:
    if s['id'] in ('A-RESPONSE', 'A-RECONCILE'):
        s['evidence'] = sorted(set(s['evidence']) | {'S-DECISIONS-V5'})
    if s['id'] == 'A-RESPONSE':
        s['then'] += '; the form offers only the responders, actions and versions the task returns, and claims first when claim_required'
    if s['id'] == 'A-RECONCILE':
        s['then'] += '; only actions in allowed_actions are offered'
# Like FE-DECIDE in v4, frontend tasks build against the proposals on the contract mock and are not gated by them; FE-CONNECT-1 and the backend tasks are.
V6_TASK_EV = ['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V5']
task_by_id = {t['id']: t for t in tasks}
def retitle(i, title):
    t = task_by_id[i]; t['title'] = title; t['evidence'] = sorted(set(t['evidence']) | {'S-DECISIONS-V5'})
retitle('FE-M2A', 'Frontend: core Start work: button, line chooser and intake drawers without proof fields (invoice, weekly, minutes, issue, change, incident, escalation, leadership)')
t = task_by_id['FE-M2A']; t['acceptance'] = ['A-START', 'A-START-INTAKE']
retitle('FE-M2B', 'Frontend: all-exceptions list (exceptions only)')
t = task_by_id['FE-M2B']; t['refs'] = ['R-EXCEPTION']; t['acceptance'] = ['A-ACCESSIBILITY']
retitle('FE-M3-PROJECTS', 'Frontend: projects list and project journey (tabs in FE-M3-PROJECT-TABS and FE-M3-REPORT)')
tasks += [
    dict(T('FE-M2A-PROOF', 'Frontend: Start work proof fields and the Finance and payroll drawers (accounts, schedules, fixed assets, forecast, BU totals, ledger, payroll restricted)', [], ['R-START', 'R-FINANCE'], [], ['FE-M2A', 'FE-M2B-RESPONSE'], ['A-START-INTAKE', 'A-PAYROLL'], FE), evidence=V6_TASK_EV),
    dict(T('FE-M2B-RESPONSE', 'Frontend: record a response (client response, SOW signature, team input, RFP outcome) and reconcile on the work item', [], ['R-RESPONSE', 'R-EXCEPTION'], [], ['FE-WORKITEM'], ['A-RESPONSE', 'A-RECONCILE', 'A-RFP-OUTCOME'], FE), evidence=V6_TASK_EV),
    dict(T('FE-M3-PROJECT-TABS', 'Frontend: project tabs: milestones, documents, registers and actions', [], ['R-PROJECT'], [], ['FE-M3-PROJECTS'], ['A-PROJECT-TABS'], FE), evidence=V6_TASK_EV),
    dict(T('FE-M3-REPORT', 'Frontend: project money tab report with drill-down (SCR-12)', [], ['R-PROJECT', 'R-REPORTS'], [], ['FE-M3-PROJECTS'], ['A-PROJECT', 'A-REPORT'], FE), evidence=V6_TASK_EV),
]
for m in milestones:
    if m['id'] == 'M-2':
        m['refs'] += ['FE-M2A-PROOF', 'FE-M2B-RESPONSE']; m['exit_criteria'] = m['exit_criteria'] + ['A-START-INTAKE and A-RFP-OUTCOME pass on the contract mock']
    if m['id'] == 'M-3':
        m['refs'] += ['FE-M3-PROJECT-TABS', 'FE-M3-REPORT']; m['exit_criteria'] = m['exit_criteria'] + ['A-PROJECT-TABS passes']
for r in requirements:
    if r['id'] == 'R-START': r['coverage'] = 'E-LINES, E-LINE-OPTIONS, E-WORK-START / A-START, A-START-INTAKE'
    if r['id'] == 'R-RESPONSE': r['coverage'] = 'E-EVIDENCE-UPLOAD, E-RESPONSE, E-RFP-OUTCOME / A-RESPONSE, A-RFP-OUTCOME'
    if r['id'] == 'R-PROJECT': r['coverage'] = 'E-PROJECTS, E-PROJECT, E-PROJECT-TAB, E-DOCUMENT / A-PROJECT, A-PROJECT-TABS'
for j in journeys:
    if j['id'] == 'JR-01': j['refs'] = j['refs'] + ['E-LINE-OPTIONS', 'E-EVIDENCE-UPLOAD']
    if j['id'] == 'JR-03': j['refs'] = j['refs'] + ['E-WORK-ITEM', 'E-RFP-OUTCOME']

# ---- v7 (S-DECISIONS-V6): client messages integration, scenarios, backend and frontend tasks for every remaining screen and slice
integrations.append({'id': 'I-CLIENT-MESSAGES', 'title': 'Messages to clients (RFP follow-ups, payment reminders, report sends)', 'refs': ['D-ALERT-PROVIDERS', 'D-RFP-OUTCOME', 'D-LINE-WORKSPACE', 'T-RESPONSE', 'T-WORKSPACE'],
    'evidence': ['S-SCOPE', 'S-BACKEND', 'S-DECISIONS-V6'], 'provider': 'Not chosen (existing delivery outbox with a mock adapter)', 'selection': 'unresolved',
    'purpose': 'Send what a person approved or chose to send to a client contact (e.g. the RFP follow-up on SCR-16 rfp-unknown, the payment reminder on SCR-32).',
    'data': 'Only the exact version the person sent; recipient as recorded by the backend.', 'secret_boundary': 'Provider credentials server-only; never in the frontend.',
    'failure_recovery': 'An unknown send outcome makes the work effect_uncertain; it is reconciled (E-WORK-ACTION) before any resend (INV-RESEND).',
    'operations': [{'name': 'queue_client_message', 'relationship': 'queued_work', 'contract': 'E-RFP-FOLLOWUP and sending steps on E-WORK-STEP write an outbox entry for the exact version; the outbox worker sends it and records the receipt or an uncertain effect.',
                    'authentication': 'Internal; provider call authenticated server-side when chosen.', 'evidence': ['S-BACKEND', 'S-DECISIONS-V6']}]})
for eid in ('E-RFP-FOLLOWUP', 'E-WORK-STEP'):
    EP_BY_ID[eid]['integration_calls'] = [{'integration': 'I-CLIENT-MESSAGES', 'operation': 'queue_client_message'}]

def SC7(*a):
    s = SC(*a); s['evidence'] = ['S-SCREENS', 'S-DECISIONS-V6']; return s
scenarios += [
    SC7('A-EXCEPTIONS-LIST', 'Search, filter and count all exceptions', 'R-EXCEPTION', 'A Lead with 25 visible exceptions of several kinds', 'Search a reference, filter one kind, page through', 'Rows match q and what across pages; open_count counts every match the Lead may see; each row\'s ref equals its work item\'s reference; absent counts are not shown'),
    SC7('A-RFP-FOLLOWUP', 'Send a drafted RFP follow-up exactly once', 'R-RESPONSE', 'An RFP with outcome unknown and a follow-up drafted by the agent', 'The PM edits and sends it; sends again with the same idempotency key; the provider outcome is unknown',
        'One outbox entry for the exact version; the repeat changes nothing; an unknown outcome shows effect_uncertain and no resend is possible until reconciled; an agent actor is refused; a stale version returns 409'),
    SC7('A-MONTHEND-VIEW', 'Month-end shows known cash plus Unknown and restricted rows without links', 'R-FINANCE', 'October with one statement missing and a restricted payroll task', 'A Finance Lead reads month-end',
        'Summary counts are as returned; cash shows the known part and Unknown, never 0; the payroll row says HR only with no work_id; the next action opens its work item'),
    SC7('A-WORKSPACE', 'A line workspace shows typed sections and takes only offered steps', 'R-WORKITEM', 'A weekly report in review, a minutes item with suggestions, a fixed-asset schedule with one Unknown, and a restricted payroll section',
        'Each is read; a suggestion is accepted with E-WORK-STEP; a step is repeated with the same idempotency key; a sending step cannot confirm the send',
        'Sections render by kind with cited records; unknown amounts are unknown, never 0; restricted sections return restricted=true and no rows to people without the grant; only returned steps are offered; the repeat changes nothing; an unconfirmed send returns effect_uncertain and the item offers reconcile; decisions use E-TASK-DECIDE; a stale revision returns 409'),
    SC7('A-ASSIGN', 'Assign the accountable person on an unassigned RFP', 'R-START', 'A logged RFP in the Unassigned queue and a person allowed to assign', 'Assign a candidate; a person without the authority opens the RFP',
        'The work moves to the chosen PM with one audit event; the other person sees no assign block; a person not in candidates gets 422; stale 409'),
    SC7('A-SETUP-RULES-VIEW', 'Rules show Not set, holds work and can_change; the first version saves', 'R-SETUP', 'A rule that is Not set (revision 0) and a read-only Lead', 'The Admin saves roles allowed for it; the read-only Lead opens Rules',
        'Save with expected_revision 0 creates version 1; not_set_count drops; the read-only Lead sees no edit control; a stale save returns 409 and re-applies nothing'),
    SC7('A-DELEGATIONS', 'Delegations are listed and set', 'R-SETUP', 'A Lead with one scheduled delegation', 'Read delegations; set a new one with authority and reason', 'The list shows from, delegate, authority, dates and status as returned; the new delegation appears with a new revision; an authority not offered gets 422'),
    SC7('A-PEOPLE-ADMIN', 'Assign roles, invite and deactivate (once D-ADMIN-AUTHORITY is decided)', 'R-SETUP', 'D-ADMIN-AUTHORITY and D-SIGNIN decided; a person with held work and a person leaving',
        'Assign the missing role and resume; invite a new staff member; deactivate the leaver with reassignment', 'Held work resumes; the invite is idempotent; open items are reassigned before deactivation; every write is audited; defined fully when the decisions are made'),
    SC7('A-TEMPLATE-VERSION', 'Upload a new template version', 'R-SETUP', 'A test template at version 1', 'Upload version 2; upload with a stale revision', 'Version 2 is listed with who and when; test_template is as the backend returns it; stale 409'),
    SC7('A-PAYROLL-FIELDS', 'Payroll field visibility (once D-PAYROLL-VISIBILITY is decided)', 'R-SETUP', 'D-PAYROLL-VISIBILITY decided by PSL', 'The HR Lead changes who may see a payroll field', 'Defined when D-PAYROLL-VISIBILITY is decided; INV-RESTRICTED holds whatever is configured'),
    SC7('A-COSTING-RULE', 'Costing rule versions and examples are shown as returned', 'R-SETUP', 'A current costing rule, a proposed version and worked examples, one with an unknown result', 'A Lead and the proposer open the costing rule',
        'Versions, sections and examples show as returned; an unknown result stays unknown; the proposer sees cannot_review_reason; the review and withdrawal writes are defined when D-COSTING-RULE is decided'),
    SC7('A-ALERT-PREFS', 'Read and save per-event alert preferences', 'R-ALERTS', 'A person with a verified WhatsApp number', 'Read preferences; turn off email for one event; set the digest time; save with a stale revision',
        'Events, digest time and quiet hours come back with their options; the number is masked; the save returns a new revision; stale 409; channel and frequency stay valid'),
    SC7('A-NOTIFICATIONS', 'Search, count and mark alerts read', 'R-ALERTS', 'A person with four alerts, one restricted (in app only) and one sent in a digest', 'Search, filter unread, open one',
        'total and unread_count are as returned; each alert shows how and when it was delivered or why it stayed in the app; opening marks it read and unread_count drops'),
    SC7('A-ASSISTANT-THREADS', 'Conversation list, typed steps and a draft that starts its line', 'R-ASSISTANT', 'A PM with three conversations, one drafted and one working', 'Reload the page; open the drafted one; start the draft; mention a project',
        'The list and each conversation keep their status after reload; steps show done, now and next with references; the draft opens the normal Start work drawer prefilled and the started work is linked; mentions offer only readable records'),
    SC7('A-SPEECH-INPUT', 'Speech input in the assistant (once D-SPEECH-INPUT is decided)', 'R-ASSISTANT', 'D-SPEECH-INPUT decided', 'Use Speak your request', 'Defined when D-SPEECH-INPUT is decided; no external connection is made before then'),
    SC7('A-SIGNIN', 'Sign in, sign out and reset (once D-SIGNIN is decided)', 'R-SESSION', 'D-SIGNIN decided by the backend developer', 'Sign in, fail once, reset, sign out', 'Defined when D-SIGNIN is decided'),
    SC7('A-PROJECTS-VIEW', 'Projects list counts and journey detail come from the backend', 'R-PROJECT', 'Five active and two closed projects, one with lines needing a person', 'Read each status tab and one project',
        'Counts and totals are as returned; next milestone due may be unknown; the journey shows PM, facts, per-line detail and station as returned; nothing is counted by the frontend'),
    SC7('A-OVERVIEW-LINES', 'Floor lines carry subtitle, agent and status', 'R-OVERVIEW', 'A PMO Lead with sample work on every line', 'Read overview', 'Each line shows its subtitle, agent and status tag as returned; no tone is parsed from note'),
    SC7('A-RECEIVABLES', 'Invoices list what is owed; a receipt is recorded once and kept separate', 'R-FINANCE', 'Invoices with one received amount unknown; D-RECEIPT-ALLOCATION decided for the receipt part',
        'A Finance user lists invoices; records a receipt with proof; repeats it with the same idempotency key', 'Owed and received show Unknown where unknown, never 0; the receipt is a separate record with its allocation status as returned; the repeat records nothing; no debt is erased; agents are refused'),
    SC7('A-CLIENTS', 'Client register and billing contact', 'R-PROJECT', 'A client with no billing contact and an invoice waiting', 'Read clients and the detail; set the billing contact', 'billing_contact_set is false and the blocked line says invoices wait; after the save it is set with a new revision; stale 409'),
    SC7('A-CONTRACT-V7', 'The frontend contract is v7 and every mock validates', 'R-FRONTEND', 'The frontend on the v6 contract with all merged fixtures', 'Repoint the mock, generated types and drift test to packages/v7', 'Every existing fixture and request validates against v7 unchanged; proposal-only fields from earlier rounds now validate without stripping where v7 carries them'),
]
for s in scenarios:
    if s['id'] == 'A-RFP-OUTCOME':
        s['then'] += '; the RFP frame, recorded rows, categorised lessons, reminder and engagement show as returned (D-RFP-OUTCOME r2)'
        s['evidence'] = sorted(set(s['evidence']) | {'S-DECISIONS-V6'})
    if s['id'] == 'A-RESPONSE':
        s['then'] += '; the success view shows the recorded block (who, when, how received, proof count) and the next lines as returned'
        s['evidence'] = sorted(set(s['evidence']) | {'S-DECISIONS-V6'})

V7_TASK_EV = ['S-SCREENS', 'S-SCOPE', 'S-DECISIONS-V6']
def T7(*a, **kw):
    return dict(T(*a, **kw), evidence=V7_TASK_EV)
task_by_id = {t['id']: t for t in tasks}
for tid, extra_refs, extra_acc in (('T-RESPONSE', ['I-CLIENT-MESSAGES'], ['A-RFP-FOLLOWUP', 'A-RFP-OUTCOME']), ('T-ALERTS', [], ['A-ALERT-PREFS', 'A-NOTIFICATIONS']), ('T-ASSISTANT', [], ['A-ASSISTANT-THREADS']),
                                   ('T-SETUP', [], ['A-SETUP-RULES-VIEW', 'A-DELEGATIONS', 'A-TEMPLATE-VERSION']), ('T-EXCEPTIONS', [], ['A-EXCEPTIONS-LIST']), ('T-FINANCE', [], ['A-MONTHEND-VIEW']),
                                   ('T-PROJECTS', [], ['A-PROJECTS-VIEW']), ('T-FLOOR', [], ['A-OVERVIEW-LINES']), ('T-WORKITEM', [], ['A-WORKSPACE'])):
    t = task_by_id[tid]; t['refs'] = t['refs'] + extra_refs; t['acceptance'] = t['acceptance'] + [a for a in extra_acc if a not in t['acceptance']]
    t['evidence'] = sorted(set(t['evidence']) | {'S-DECISIONS-V6'})
tasks += [
    T7('T-WORKSPACE', 'API: line workspace block on the work item and the line step write', by_task['T-WORKSPACE'] + ['I-CLIENT-MESSAGES'], ['R-WORKITEM', 'R-FINANCE'], [], ['T-WORKITEM'], ['A-WORKSPACE'], BE),
    T7('T-ASSIGN', 'API: assign the accountable person', by_task['T-ASSIGN'], ['R-START'], [], ['T-START'], ['A-ASSIGN'], BE),
    T7('T-SETUP-PEOPLE', 'API: role assignment, invite and deactivate (gated)', by_task['T-SETUP-PEOPLE'], ['R-SETUP'], ['D-ADMIN-AUTHORITY', 'D-SIGNIN'], ['T-SETUP'], ['A-PEOPLE-ADMIN'], BE),
    T7('T-COSTING-RULE', 'API: costing rule read (writes wait for D-COSTING-RULE)', by_task['T-COSTING-RULE'], ['R-SETUP'], ['D-COSTING-RULE'], ['T-SETUP'], ['A-COSTING-RULE'], BE),
    T7('T-RECEIVABLES', 'API: Finance-wide invoices and receipt recording (receipt gated)', by_task['T-RECEIVABLES'], ['R-FINANCE'], ['D-RECEIPT-ALLOCATION'], ['T-FINANCE'], ['A-RECEIVABLES'], BE),
    T7('T-CLIENTS', 'API: client register and billing contact', by_task['T-CLIENTS'], ['R-PROJECT'], [], ['T-PROJECTS'], ['A-CLIENTS'], BE),
]
# frontend: retitles for the slices readiness split, then one task per remaining screen or slice. All build on the v7 contract mock.
def retitle7(i, title, acc=None):
    t = task_by_id[i]; t['title'] = title; t['evidence'] = sorted(set(t['evidence']) | {'S-DECISIONS-V6'})
    if acc is not None: t['acceptance'] = acc
retitle7('FE-M2B-RESPONSE', 'Frontend (F-09): record a client response or SOW signature (SCR-16 default, validation, success, sow-signed) and reconcile on the work item (SCR-02 awaiting-reconciliation); team input and RFP outcome are FE-M2B-RFP', ['A-RESPONSE', 'A-RECONCILE'])
retitle7('FE-M2B', 'Frontend (F-06): all-exceptions list with search, filter and count (SCR-10)', ['A-ACCESSIBILITY', 'A-EXCEPTIONS-LIST'])
retitle7('FE-M3-FINANCE', 'Frontend (F-10): Finance month-end checklist (SCR-36); the other Finance screens are FE-FIN-*', ['A-MONTHEND', 'A-MONTHEND-VIEW'])
retitle7('FE-M3-SETUP', 'Frontend (F-11): Setup frame and rule tabs (SCR-13 rules, finance-rules, delivery-rules); other Setup tabs are FE-SETUP-*', ['A-SETUP', 'A-SETUP-RULES-VIEW'])
retitle7('FE-M3-PROJECTS', 'Frontend (F-07): projects list and project journey (SCR-22, SCR-07) with the v7 list and journey fields; tabs in FE-M3-PROJECT-TABS and FE-M3-REPORT', ['A-PROJECT', 'A-PROJECTS-VIEW'])
retitle7('FE-M3-OVERVIEW', 'Frontend (F-08): overview and factory floor (SCR-06) with line subtitle, agent and status', ['A-OVERVIEW', 'A-OVERVIEW-LINES'])
task_by_id['FE-M4']['status'] = 'retired'
retitle7('FE-M4', 'Frontend: notification centre, alert settings, assistant (retired 15 Nov 2026: split into FE-ALERTS, FE-ALERTS-MENU, FE-ASSISTANT and FE-ASSISTANT-SPEECH)')
V7DEP = 'FE-CONTRACT-V7'; WSF = 'FE-WORKSPACE-FRAME'
tasks += [
    T7('FE-CONTRACT-V7', 'Frontend: repoint the frontend contract to v7 and validate all mocks (mock server, gen:api types, drift test, client version comment); one lane owns the repoint', [], ['R-FRONTEND'], [], ['T-FRONTEND-SHELL'], ['A-CONTRACT-V7'], FE),
    T7('FE-M2B-RFP', 'Frontend (F-09B): team input and RFP outcome in the RFP frame, with the drafted follow-up (SCR-16 team-input, rfp-outcome, -lost, -pending, -unknown, rfp-won, rfp-lost, rfp-pending, rfp-unknown)', [], ['R-RESPONSE'], [], ['FE-M2B-RESPONSE', V7DEP], ['A-RFP-OUTCOME', 'A-RFP-FOLLOWUP'], FE),
    T7('FE-WORKSPACE-FRAME', 'Frontend: line workspace renderer on the work item (typed sections, step forms from field descriptors, step write with idempotency and uncertain-effect handling)', [], ['R-WORKITEM'], [], ['FE-WORKITEM', 'FE-DECIDE', 'FE-M2B-RESPONSE', V7DEP], ['A-WORKSPACE'], FE),
    T7('FE-RFP-INTAKE', 'Frontend: log a received RFP (SCR-23) and assign the accountable PM from Unassigned (SCR-24)', [], ['R-START'], [], ['FE-M2A', 'FE-MYWORK', V7DEP], ['A-START-INTAKE', 'A-ASSIGN'], FE),
    T7('FE-RFP-RESPONSE', 'Frontend: RFP response workspace (SCR-26 default, review, edit, accepted, reject, response-review)', [], ['R-WORKITEM', 'R-DECIDE'], [], [WSF, 'FE-M2B-RFP'], ['A-WORKSPACE'], FE),
    T7('FE-RFP-SUBMIT', 'Frontend: RFP submission (SCR-40 draft, review, submitted, submitted-portal)', [], ['R-WORKITEM', 'R-DECIDE'], [], [WSF, 'FE-M2B-RFP'], ['A-WORKSPACE', 'A-RECONCILE'], FE),
    T7('FE-COSTING', 'Frontend: costing sheet (SCR-27 default, adjust, ask, approvals); the CEO final decision stays in FE-DECIDE-VARIANTS', [], ['R-WORKITEM', 'R-DECIDE'], ['D-COSTING-RULE'], [WSF, 'FE-SETUP-COSTING'], ['A-WORKSPACE', 'A-COSTING-RULE'], FE),
    T7('FE-ENGAGEMENT-PLANNING', 'Frontend: engagement and planning (SCR-41 default, register; SCR-42 default, record, held, readiness, ready)', [], ['R-WORKITEM', 'R-RESPONSE'], [], [WSF], ['A-WORKSPACE', 'A-RESPONSE'], FE),
    T7('FE-LINE-WEEKLY', 'Frontend: weekly client update (SCR-25 default, invalid, assembling, review, returned, received)', [], ['R-WORKITEM', 'R-DECIDE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-LINE-MINUTES', 'Frontend: confirm the minutes (SCR-28 default, suggesting, drafted, review, internal, published)', [], ['R-WORKITEM', 'R-DECIDE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-ISSUE', 'Frontend: issue detail (SCR-30 default, overdue, no-owner, verified)', [], ['R-WORKITEM'], [], [WSF, 'FE-M3-PROJECT-TABS'], ['A-WORKSPACE'], FE),
    T7('FE-CHANGE', 'Frontend: change request detail (SCR-31 default, impact, decision, rejected, authorise, notice, execution, go-live-note, closed)', [], ['R-WORKITEM', 'R-DECIDE'], ['D-CHANGE-DECIDERS'], [WSF, 'FE-M3-PROJECT-TABS'], ['A-WORKSPACE'], FE),
    T7('FE-EMERGENCY-ESCALATION', 'Frontend: emergency change (SCR-50 record, refused, review, retro, report) and escalation (SCR-51 investigating, decide, not-escalated, draft, review, received); the CTO emergency decision stays in FE-DECIDE-VARIANTS', [], ['R-WORKITEM', 'R-DECIDE'], [], [WSF, 'FE-M2A'], ['A-WORKSPACE'], FE),
    T7('FE-LEADERSHIP-REPORT', 'Frontend: leadership report (SCR-52 setup, drafting, review, tuesday, received)', [], ['R-WORKITEM', 'R-REPORTS'], [], [WSF, 'FE-M3-REPORT'], ['A-WORKSPACE', 'A-REPORT'], FE),
    T7('FE-MILESTONE-COMPLETE', 'Frontend: mark a milestone complete from the Milestones tab (SCR-19), started as the invoice line with proof', [], ['R-START', 'R-PROJECT'], [], ['FE-M3-PROJECT-TABS', 'FE-M2A-PROOF'], ['A-START-INTAKE', 'A-PROJECT-TABS'], FE),
    T7('FE-DOCUMENT-REVIEW', 'Frontend: document review page (SCR-08 default, returned)', [], ['R-PROJECT', 'R-DECIDE'], [], ['FE-M3-PROJECT-TABS', 'FE-DECIDE'], ['A-PROJECT-TABS', 'A-DECIDE'], FE),
    T7('FE-DELIVERY-RELEASE', 'Frontend: delivery overview (SCR-43), release gates (SCR-44 default, decision, returned, owner-needed, readiness, ready) and go-live acceptance (SCR-45 default, signatures, accepted, changes, declined)', [], ['R-PROJECT', 'R-WORKITEM', 'R-RESPONSE'], [], [WSF, 'FE-M3-PROJECTS'], ['A-WORKSPACE', 'A-PROJECTS-VIEW', 'A-RESPONSE'], FE),
    T7('FE-DELIVERY-HYPERCARE-ARCHIVE', 'Frontend: hypercare (SCR-46 default, record, evaluating, qualified, not-met, setup-needed) and archive (SCR-47 default, working, uncertain)', [], ['R-WORKITEM', 'R-EXCEPTION'], [], [WSF], ['A-WORKSPACE', 'A-RECONCILE'], FE),
    T7('FE-DELIVERY-CLOSURE', 'Frontend: handover to Support (SCR-48 default, record, gaps, received), closure (SCR-49 default, blocked, decision, returned, closed) and the retrospective (SCR-33)', [], ['R-WORKITEM', 'R-DECIDE', 'R-RESPONSE'], [], [WSF], ['A-WORKSPACE', 'A-RESPONSE'], FE),
    T7('FE-PAYMENTS', 'Frontend: payments and follow-up list (SCR-20 default) and the payment reminder (SCR-32); the short payment stays in FE-DECIDE-VARIANTS', [], ['R-FINANCE'], [], [WSF], ['A-RECEIVABLES', 'A-WORKSPACE'], FE),
    T7('FE-PAYMENTS-RECEIPT', 'Frontend: record a payment (SCR-20 record), gated until the allocation rule is decided', [], ['R-FINANCE'], ['D-RECEIPT-ALLOCATION'], ['FE-PAYMENTS'], ['A-RECEIVABLES'], FE),
    T7('FE-CLIENTS', 'Frontend: clients and client detail with the billing contact (SCR-35 default, detail)', [], ['R-PROJECT'], [], ['FE-M3-PROJECTS', V7DEP], ['A-CLIENTS'], FE),
    T7('FE-SIGNIN', 'Frontend: sign in, error, reset and account set-up (SCR-17), gated until sign-in is decided', [], ['R-SESSION'], ['D-SIGNIN'], ['T-FRONTEND-SHELL'], ['A-SIGNIN'], FE),
    T7('FE-FIN-PAYROLL-IMPORT', 'Frontend (F-10B): payroll inputs and restricted matching (SCR-09 default, error; SCR-18 default, permission)', [], ['R-FINANCE'], [], [WSF], ['A-PAYROLL', 'A-WORKSPACE'], FE),
    T7('FE-FIN-PAYROLL-CORRECTIONS', 'Frontend (F-10C): payroll corrections and the HR Lead decision (SCR-37)', [], ['R-FINANCE', 'R-DECIDE'], [], [WSF], ['A-PAYROLL', 'A-WORKSPACE'], FE),
    T7('FE-FIN-PAYROLL-RUN', 'Frontend (F-10D): payroll run (SCR-59 input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup)', [], ['R-FINANCE'], [], ['FE-FIN-PAYROLL-IMPORT'], ['A-PAYROLL', 'A-WORKSPACE'], FE),
    T7('FE-FIN-ACCOUNTS-INTAKE', 'Frontend (F-10E1): management accounts intake and investigation (SCR-53 quarantined, units, investigating, owner-needed, setup-needed, returned)', [], ['R-FINANCE'], [], [WSF, 'FE-M2A-PROOF'], ['A-MONTHEND', 'A-WORKSPACE'], FE),
    T7('FE-FIN-ACCOUNTS-PUBLISH', 'Frontend (F-10E2): management accounts reviews and publication (SCR-53 reviews, drafting, publishing, uncertain, verified)', [], ['R-FINANCE', 'R-DECIDE'], [], ['FE-FIN-ACCOUNTS-INTAKE', 'FE-M3-FINANCE'], ['A-WORKSPACE', 'A-RECONCILE'], FE),
    T7('FE-FIN-SCHEDULES', 'Frontend (F-10F): income detail and schedules (SCR-54 investigating, held, review, returned, verified, export, withdrawn)', [], ['R-FINANCE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-FIN-PPE', 'Frontend (F-10G): fixed asset schedule (SCR-55 investigating, register-review, date-review, calculating, schedule-review, returned, verified)', [], ['R-FINANCE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-FIN-FORECAST', 'Frontend (F-10H): cash forecast and actuals (SCR-56 investigating, review, group-rows, group-review, uncertain, verified, actuals)', [], ['R-FINANCE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-FIN-BU', 'Frontend (F-10I): business-unit totals (SCR-57 source-review, investigating, held, result-review, publish, receipts, verified)', [], ['R-FINANCE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-FIN-LEDGER', 'Frontend (F-10J): ledger source reference (SCR-58 investigating, duplicate, observe, review, rejected, verified)', [], ['R-FINANCE'], [], [WSF], ['A-WORKSPACE'], FE),
    T7('FE-SETUP-DELEGATION', 'Frontend (F-11B): delegation tab (SCR-13 delegation)', [], ['R-SETUP'], [], ['FE-M3-SETUP', V7DEP], ['A-DELEGATIONS'], FE),
    T7('FE-SETUP-ROLES', 'Frontend (F-11C): roles and staff accounts (SCR-13 default, permission, validation; SCR-21 default, invite, deactivate), gated until PSL names who holds Admin', [], ['R-SETUP'], ['D-ADMIN-AUTHORITY'], ['FE-M3-SETUP', V7DEP], ['A-PEOPLE-ADMIN'], FE),
    T7('FE-SETUP-TEMPLATES', 'Frontend (F-11D): templates with versioned upload (SCR-34)', [], ['R-SETUP'], [], ['FE-M3-SETUP', V7DEP], ['A-TEMPLATE-VERSION'], FE),
    T7('FE-SETUP-PAYROLL-FIELDS', 'Frontend (F-11E): payroll field visibility (SCR-13 fields), gated until PSL decides it', [], ['R-SETUP'], ['D-PAYROLL-VISIBILITY'], ['FE-M3-SETUP', V7DEP], ['A-PAYROLL-FIELDS'], FE),
    T7('FE-SETUP-COSTING', 'Frontend (F-11F): costing rule (SCR-39 default, review, example, review-own), gated until the rule is decided', [], ['R-SETUP'], ['D-COSTING-RULE'], ['FE-M3-SETUP', V7DEP], ['A-COSTING-RULE'], FE),
    T7('FE-ALERTS', 'Frontend (F-12A): notification centre and alert settings (SCR-15 default, settings; STATES); the WhatsApp and email boards are T-ALERTS message content', [], ['R-ALERTS'], [], [V7DEP], ['A-ALERTS', 'A-ALERT-PREFS', 'A-NOTIFICATIONS'], FE),
    T7('FE-ALERTS-MENU', 'Frontend (F-12A2): bell and account menu in the top bar (SCR-15 account), gated on where the bell is drawn and on sign-out', [], ['R-ALERTS', 'R-SESSION'], ['D-ALERTS-ENTRY', 'D-SIGNIN'], ['FE-ALERTS', 'FE-M2A'], ['A-NOTIFICATIONS'], FE),
    T7('FE-ASSISTANT', 'Frontend (F-12B): assistant (SCR-05 default, thread, draft-started, cant, working) without speech input', [], ['R-ASSISTANT'], [], [V7DEP, 'FE-M2A'], ['A-ASSISTANT', 'A-ASSISTANT-THREADS'], FE),
    T7('FE-ASSISTANT-SPEECH', 'Frontend: "Speak your request" in the assistant composer (SCR-05), gated on D-SPEECH-INPUT', [], ['R-ASSISTANT'], ['D-SPEECH-INPUT'], ['FE-ASSISTANT'], ['A-SPEECH-INPUT'], FE),
]
for m in milestones:
    if m['id'] == 'M-2':
        m['refs'] += ['FE-CONTRACT-V7', 'FE-M2B-RFP', 'FE-RFP-INTAKE', 'T-ASSIGN']; m['exit_criteria'] = m['exit_criteria'] + ['A-CONTRACT-V7, A-RFP-FOLLOWUP, A-ASSIGN and A-EXCEPTIONS-LIST pass on the v7 contract mock']
    if m['id'] == 'M-3':
        m['refs'] += ['T-SETUP-PEOPLE', 'T-COSTING-RULE', 'T-CLIENTS', 'FE-SETUP-DELEGATION', 'FE-SETUP-ROLES', 'FE-SETUP-TEMPLATES', 'FE-SETUP-PAYROLL-FIELDS', 'FE-SETUP-COSTING', 'FE-DOCUMENT-REVIEW', 'FE-MILESTONE-COMPLETE', 'FE-CLIENTS']
        m['exit_criteria'] = m['exit_criteria'] + ['A-MONTHEND-VIEW, A-SETUP-RULES-VIEW, A-DELEGATIONS, A-TEMPLATE-VERSION, A-PROJECTS-VIEW, A-OVERVIEW-LINES and A-CLIENTS pass', 'A-PEOPLE-ADMIN, A-PAYROLL-FIELDS and A-COSTING-RULE pass once their decisions are made']
        m['gate_ids'] = m['gate_ids'] + ['D-ADMIN-AUTHORITY', 'D-PAYROLL-VISIBILITY', 'D-COSTING-RULE']
    if m['id'] == 'M-4':
        m['refs'] += ['FE-ALERTS', 'FE-ALERTS-MENU', 'FE-ASSISTANT', 'FE-ASSISTANT-SPEECH']; m['exit_criteria'] = m['exit_criteria'] + ['A-ALERT-PREFS, A-NOTIFICATIONS and A-ASSISTANT-THREADS pass on the contract mock']
        m['gate_ids'] = m['gate_ids'] + ['D-ALERTS-ENTRY', 'D-SPEECH-INPUT']
MS7 = lambda i, t, refs, exits, gates: {'id': i, 'title': t, 'refs': refs, 'evidence': ['S-SCREENS', 'S-DECISIONS-V6'], 'owner_role': 'delivery owner', 'exit_criteria': exits, 'gate_ids': gates}
milestones += [
    MS7('M-5', 'Line workspaces: frame, pre-sale and planning lines', ['T-WORKSPACE', 'FE-WORKSPACE-FRAME', 'FE-RFP-RESPONSE', 'FE-RFP-SUBMIT', 'FE-COSTING', 'FE-ENGAGEMENT-PLANNING'],
        ['A-WORKSPACE passes on PostgreSQL and on the contract mock', 'Every SCR-26, SCR-40, SCR-41, SCR-42 board passes the design-fidelity check', 'SCR-27 passes once D-COSTING-RULE is decided'], ['D-LINE-WORKSPACE', 'D-COSTING-RULE']),
    MS7('M-6', 'Delivery lines: weekly, minutes, issues, changes, emergencies, escalations, leadership report, release, hypercare, archive, handover and closure',
        ['FE-LINE-WEEKLY', 'FE-LINE-MINUTES', 'FE-ISSUE', 'FE-CHANGE', 'FE-EMERGENCY-ESCALATION', 'FE-LEADERSHIP-REPORT', 'FE-DELIVERY-RELEASE', 'FE-DELIVERY-HYPERCARE-ARCHIVE', 'FE-DELIVERY-CLOSURE'],
        ['Every board of SCR-25, 28, 30, 31, 33, 43-52 passes the design-fidelity check on the contract mock', 'SCR-31 decision and authorise pass once D-CHANGE-DECIDERS is decided'], ['D-LINE-WORKSPACE', 'D-CHANGE-DECIDERS', 'D-DECISION-VARIANTS']),
    MS7('M-7', 'Finance lines, payroll, payments and receipts',
        ['T-RECEIVABLES', 'FE-FIN-PAYROLL-IMPORT', 'FE-FIN-PAYROLL-CORRECTIONS', 'FE-FIN-PAYROLL-RUN', 'FE-FIN-ACCOUNTS-INTAKE', 'FE-FIN-ACCOUNTS-PUBLISH', 'FE-FIN-SCHEDULES', 'FE-FIN-PPE', 'FE-FIN-FORECAST', 'FE-FIN-BU', 'FE-FIN-LEDGER', 'FE-PAYMENTS', 'FE-PAYMENTS-RECEIPT'],
        ['Every Finance canvas board of SCR-09, 18, 20, 32, 37, 53-59 passes the design-fidelity check', 'A-PAYROLL and A-RECEIVABLES pass; the receipt write once D-RECEIPT-ALLOCATION is decided'], ['D-LINE-WORKSPACE', 'D-RECEIPT-ALLOCATION', 'D-RETURN', 'D-DECISION-VARIANTS']),
    MS7('M-8', 'Sign-in', ['FE-SIGNIN'], ['A-SIGNIN passes once D-SIGNIN is decided'], ['D-SIGNIN', 'D-AUTH']),
]
for r in requirements:
    if r['id'] == 'R-EXCEPTION': r['coverage'] = 'E-WORK-ACTION, E-EXCEPTIONS / A-RECONCILE, A-RESUME, A-EXCEPTIONS-LIST'
    if r['id'] == 'R-RESPONSE': r['coverage'] = 'E-EVIDENCE-UPLOAD, E-RESPONSE, E-RFP-OUTCOME, E-RFP-FOLLOWUP / A-RESPONSE, A-RFP-OUTCOME, A-RFP-FOLLOWUP'
    if r['id'] == 'R-WORKITEM': r['coverage'] = 'E-WORK-ITEM, E-WORK-HISTORY, E-WORK-STEP / A-WORKITEM, A-HISTORY, A-WORKSPACE'
    if r['id'] == 'R-START': r['coverage'] = 'E-LINES, E-LINE-OPTIONS, E-WORK-START, E-WORK-ASSIGN / A-START, A-START-INTAKE, A-ASSIGN'
    if r['id'] == 'R-PROJECT': r['coverage'] = 'E-PROJECTS, E-PROJECT, E-PROJECT-TAB, E-DOCUMENT, E-CLIENTS, E-CLIENT, E-CLIENT-CONTACT / A-PROJECT, A-PROJECT-TABS, A-PROJECTS-VIEW, A-CLIENTS'
    if r['id'] == 'R-FINANCE': r['coverage'] = 'E-MONTH-END, E-IMPORT, E-PAYROLL-MATCH, E-INVOICES, E-RECEIPT, E-WORK-STEP / A-MONTHEND, A-MONTHEND-VIEW, A-PAYROLL, A-RECEIVABLES, A-WORKSPACE'
    if r['id'] == 'R-SETUP': r['coverage'] = 'E-SETUP-RULES, E-SETUP-RULE-SAVE, E-PEOPLE, E-DELEGATION, E-DELEGATIONS, E-TEMPLATES, E-TEMPLATE-VERSION, E-PERSON-ROLES, E-INVITE, E-DEACTIVATE, E-COSTING-RULE / A-SETUP, A-SETUP-RULES-VIEW, A-DELEGATIONS, A-TEMPLATE-VERSION, A-PEOPLE-ADMIN, A-COSTING-RULE'
    if r['id'] == 'R-ALERTS': r['coverage'] = 'E-NOTIFICATIONS, E-NOTIFICATION-READ, E-ALERT-PREFS, E-ALERT-PREFS-READ / A-ALERTS, A-ALERT-PREFS, A-NOTIFICATIONS'
    if r['id'] == 'R-ASSISTANT': r['coverage'] = 'E-CONVERSATION-NEW, E-CONVERSATIONS, E-MESSAGE, E-CONVERSATION, E-MENTION-OPTIONS / A-ASSISTANT, A-ASSISTANT-THREADS'
for j in journeys:
    if j['id'] == 'JR-03': j['refs'] = j['refs'] + ['E-RFP-FOLLOWUP']
    if j['id'] == 'JR-05': j['refs'] = j['refs'] + ['E-WORK-STEP']
for v in views:
    if v['id'] == 'V-DATA':
        v['nodes'] = v['nodes'] + ['REC-CLIENT']; v['refs'] = v['nodes']; v['edges'].append({'from': 'REC-CLIENT', 'to': 'REC-CASE', 'label': 'has cases (proposed)'})
        v['notes'] += ' v7 proposes REC-CLIENT (client and billing contact).'

model = {
    'schema_version': '1.0', 'pins': {'skill': '0.1.0', 'generator': '0.1.0'},
    'project': {'id': 'psl-factory-frontend', 'title': 'PSL operations factory — frontend and data API', 'scope': 'Scope v2: new Next.js frontend in frontend/ on a data API added to the existing Django backend (S-08, I-02).',
                'stage': 'existing', 'roles': ['operator', 'developer', 'frontend developer', 'backend developer', 'technical reviewer', 'business owner', 'delivery owner', 'release authority'],
                'constraints': ['Django keeps login, permissions and every business rule (C-05).', 'No deployment, live AI or external connections authorised in this phase.', 'Never invent financial rules or real approvers.']},
    'security_schemes': {
        'Session': {'type': 'apiKey', 'name': 'sessionid', 'in': 'cookie', 'description': 'Django session cookie from the existing sign-in (D-AUTH, proposed).'},
        'Csrf': {'type': 'apiKey', 'name': 'X-CSRFToken', 'in': 'header', 'description': 'Django CSRF token, required on every write together with the session.'}},
    'sources': sources, 'requirements': requirements, 'decisions': decisions, 'components': components, 'records': records, 'invariants': invariants,
    'endpoints': endpoints, 'integrations': integrations, 'jobs': jobs, 'journeys': journeys, 'views': views, 'scenarios': scenarios, 'runbooks': runbooks,
    'tasks': tasks, 'milestones': milestones}
json.dump(model, open(os.path.join(HERE, 'model.json'), 'w'), indent=2, ensure_ascii=False)
print(len(endpoints), 'endpoints,', len(tasks), 'tasks,', len(decisions), 'decisions')
