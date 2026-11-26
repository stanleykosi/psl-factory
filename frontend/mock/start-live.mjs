// F-86: Start work in the live shapes of contract 1.22.0: GET /lines, GET /lines/projects, GET /projects/{case_id}/intake-sources
// and the weekly branch of POST /work. The v7 start (start-work.mjs) keeps answering its own tests;
// server.mjs hands these routes here when it runs with `liveStart` (the mock run from the command line). Sample data; no business rules.
// Cookie scenarios (psl_mock_scenario or X-Mock-Scenario) for POST /work: start_stale (409 once, the project's revision moves
// on), start_uncertain (503 on the first send of a key, 200 on the same key), start_denied (403), csrf_failed (403 with
// code csrf_failed), start_missing (404). A status number answers every route here with that status.
// F-92: the five PMO lines the form engine builds read their `request_schema` from GET /lines, source rows from intake-sources
// (parent_id and before), the escalation register, and minutes starts as multipart to POST /projects/{case_id}/minutes/intake.
import AjvModule from 'ajv';
import addFormatsModule from 'ajv-formats';

import { parseMultipart } from './received-bids.mjs';

export const START_LIVE_PATH = /^\/api\/v1\/(lines|lines\/projects|projects\/[^/]+\/(intake-sources|escalation-register))$/;
export const START_LIVE_WORK = '/api/v1/work';
export const START_LIVE_MINUTES = /^\/api\/v1\/projects\/[^/]+\/minutes\/intake$/;

const Ajv = AjvModule.default ?? AjvModule;
const addFormats = addFormatsModule.default ?? addFormatsModule;
const ajv = addFormats(new Ajv({ allErrors: true, strict: false }));

const WEEKLY = 'pmo-weekly-report/v1';
const NOW = '2026-11-23T09:00:00Z';
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'The project has a newer revision.' },
  413: { code: 'too_large', message: 'The request is too large.' },
  415: { code: 'unsupported_media', message: 'The request type is not accepted.' },
  422: { code: 'invalid', message: 'Check the form and try again.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

// The served `request_schema` of each line, built as the backend builds them (apps/core/factory_api/intake.py START_INPUT).
const ID = { type: 'integer', minimum: 1, maximum: 9223372036854775807 };
const NID = { anyOf: [ID, { type: 'null' }] };
const obj = (properties, optional = []) => ({ type: 'object', properties, required: Object.keys(properties).filter((k) => !optional.includes(k)), additionalProperties: false });
const work = (line, intake, derivedReference = false) =>
  obj(
    {
      line: { type: 'string', const: line },
      case_id: { type: 'string', format: 'uuid' },
      case_revision: { type: 'integer', minimum: 1, maximum: 2147483647 },
      idempotency_key: { type: 'string', minLength: 1, maxLength: 100, pattern: '^[ -~]+$' },
      background: { type: 'boolean' },
      intake,
      ...(derivedReference ? {} : { reference: { type: 'string', minLength: 1, maxLength: 160 } }),
    },
    ['background'],
  );
const EMERGENCY_INPUTS = obj({ template_id: NID, authorization_id: NID, outcome_id: NID, audience: { enum: ['internal', 'client', null] } });
const CHANGE_INPUTS = obj({ template_id: NID, authorization_id: NID });
export const SCHEMAS = {
  [WEEKLY]: work(WEEKLY, obj({ inputs: obj({ template_id: NID, content_id: NID, start_at: { type: 'string', maxLength: 64 }, end_at: { type: 'string', maxLength: 64 } }) })),
  'pmo-issues/v1': work('pmo-issues/v1', obj({ issue_id: ID }), true),
  'pmo-escalation/v1': work('pmo-escalation/v1', obj({ request_id: ID, template_id: NID })),
  'pmo-emergency/v1': work('pmo-emergency/v1', obj({ profile_id: ID, inputs: EMERGENCY_INPUTS })),
  'pmo-change/v1': work('pmo-change/v1', obj({ version_id: ID, inputs: CHANGE_INPUTS })),
  'pmo-minutes/v1': work(
    'pmo-minutes/v1',
    obj({ data: obj({ protocol: { const: 'factory-minutes-intake/v1' }, meeting_version_id: NID, evidence_id: ID, template_id: ID, audience: { enum: ['internal', 'client'] }, publish: { type: 'boolean' } }) }),
  ),
  // Array and object leaves: the engine cannot draw this one.
  'pmo-leadership-report/v1': work(
    'pmo-leadership-report/v1',
    obj({ inputs: obj({ template_id: NID, content_id: NID, start_at: { type: 'string', maxLength: 64 }, end_at: { type: 'string', maxLength: 64 }, kind: { enum: ['monthly_executive'] }, audience: { enum: ['internal', 'management'] }, selections: obj({ issues: { type: 'array', items: ID } }), scope: obj({ domains: { type: 'array', items: { enum: ['pmo'] } } }) }) }),
  ),
  // F-94: the intake is a oneOf on `mode`, as the server serves it.
  'pmo-finance/v1': work(
    'pmo-finance/v1',
    {
      oneOf: [
        obj({ mode: { const: 'completion' }, coverage_id: ID, handoff_id: ID }),
        obj({ mode: { const: 'preparation' }, preparation_id: ID, due_date: { anyOf: [{ type: 'string', format: 'date' }, { type: 'null' }] }, invoice_id: NID }),
      ],
    },
  ),
  'finance-payroll/v1': work('finance-payroll/v1', obj({ request_id: ID })),
  'finance-ppe/v1': work('finance-ppe/v1', obj({ register_id: ID, prior_id: NID, ledger_id: NID })),
};
const VALIDATORS = Object.fromEntries(Object.entries(SCHEMAS).map(([key, schema]) => [key, ajv.compile(schema)]));

const line = (key, title, description, can, slug, projects) => ({
  key,
  title,
  description,
  can_submit_via_api: can,
  django_url: `/lines/${slug}/`,
  project_options_url: projects ? `/api/v1/lines/projects?line=${key}` : null,
  submit_url: '/api/v1/work',
  request_schema: SCHEMAS[key] ?? {},
  content_type: 'application/json',
});
const LINES = [
  line(WEEKLY, 'Weekly client report', 'Friday report for a client', true, 'pmo-weekly-report', true),
  line('pmo-minutes/v1', 'Minutes after a meeting', 'Formal minutes and action handoff', true, 'pmo-minutes', true),
  line('finance-payroll/v1', 'Payroll', 'Monthly payroll preparation', true, 'finance-payroll', true),
  line('received-bid', 'Log a received RFP', 'Record an RFP a client sent, with its file', false, 'received-bid', false),
  line('pmo-issues/v1', 'Chase an open issue', 'Issue investigation and owner follow-up', true, 'pmo-issues', true),
  line('pmo-escalation/v1', 'Escalate an issue', 'Move an issue to the next level', true, 'pmo-escalation', true),
  line('pmo-emergency/v1', 'Record an emergency', 'Emergency change with its authorisation', true, 'pmo-emergency', true),
  line('pmo-change/v1', 'Start a change', 'Ordinary change for a project', true, 'pmo-change', true),
  line('finance-ppe/v1', 'Fixed asset schedule', 'Depreciation schedule from a register', true, 'finance-ppe', true),
  line('pmo-finance/v1', 'Prepare an invoice', 'Continue an exact Finance preparation or PMO completion through review, issuance and delivery.', true, 'pmo-finance', true),
  line('pmo-leadership-report/v1', 'Leadership report', 'Monthly report for leadership', true, 'pmo-leadership-report', true),
];
const PROJECT_LINES = new Set([WEEKLY, 'pmo-issues/v1', 'pmo-escalation/v1', 'pmo-emergency/v1', 'pmo-change/v1', 'pmo-minutes/v1', 'finance-ppe/v1', 'pmo-finance/v1']);
const PICKS = (n, text, extra = {}) => Array.from({ length: n }, (_, i) => ({ id: n - i, label: `${text} ${n - i}`, ...extra }));
// Source rows by line and field, newest first. A row with `parent` belongs to the record chosen above it (parent_id).
const SOURCE_ROWS = {
  'pmo-issues/v1': { issue_id: PICKS(28, 'ISS-') },
  'pmo-escalation/v1': { template_id: [{ id: 51, label: 'Status note v2' }] },
  'pmo-emergency/v1': {
    profile_id: [{ id: 32, label: 'CHG-0007 · v2' }, { id: 31, label: 'CHG-0003 · v1' }],
    'inputs.authorization_id': [{ id: 42, label: 'Authorised 14 November', parent: 32 }, { id: 41, label: 'Authorised 2 November', parent: 31 }],
    'inputs.outcome_id': [{ id: 62, label: 'Implemented 15 November', parent: 32 }],
    'inputs.template_id': [{ id: 52, label: 'Incident review v1' }],
  },
  'pmo-change/v1': {
    version_id: [{ id: 72, label: 'CHG-0011 · Normal · 2' }, { id: 71, label: 'CHG-0010 · Standard · 1' }],
    'inputs.authorization_id': [{ id: 82, label: 'CHG-0011 authorised', parent: 72 }],
    'inputs.template_id': [{ id: 53, label: 'Change summary v3' }],
  },
  'finance-ppe/v1': {
    register_id: [{ id: 33, label: 'PPE register 2025 · v2' }, { id: 31, label: 'PPE register 2025 · v1' }],
    prior_id: [{ id: 41, label: 'Schedule 2024' }],
    ledger_id: [{ id: 51, label: 'Ledger mapping Q4' }],
  },
  'pmo-finance/v1': {
    coverage_id: [{ id: 12, label: 'COV-0002 · 3' }, { id: 11, label: 'COV-0001 · 1' }],
    handoff_id: [{ id: 22, label: 'Go-live accepted · #22' }, { id: 21, label: 'Design signed off · #21' }],
    preparation_id: [{ id: 32, label: 'fixed_contract · COV-0002 · #32' }, { id: 31, label: 'usage · COV-0001 · #31' }],
    invoice_id: [{ id: 42, label: 'INV-0042 · 1', parent: 32 }],
  },
  'pmo-minutes/v1': {
    'data.template_id': [{ id: 54, label: 'Minutes, internal and client' }],
    'data.meeting_version_id': [{ id: 91, label: 'MTG-0004 · 2' }, { id: 90, label: 'MTG-0003 · 1' }],
  },
};
const ESCALATION_REQUESTS = [
  { id: 23, profile_id: 5, direction: 'escalate', target: 'PMO' },
  { id: 22, profile_id: 4, direction: 'de_escalate', target: 'Client' },
  { id: 21, profile_id: 4, direction: 'escalate', target: 'CTO' },
];

// The server names a project by its P-nnnn form in a path (mock/projects.mjs normaliseProjectPath); this mock keeps UUIDs.
const caseOf = (segment) => {
  const id = decodeURIComponent(segment ?? '');
  const old = /^P-(\d{4})$/.exec(id);
  return old ? uuid(Number(old[1])) : id;
};
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
// 28 projects: two pages of 25 and 3. Revisions 4 and 7 alternate; the third is a sample.
const PROJECTS = Array.from({ length: 28 }, (_, i) => ({ case_id: uuid(i + 1), title: i === 2 ? 'Sample project' : `Project ${String(i + 1).padStart(2, '0')}`, case_revision: i % 2 ? 7 : 4, sample: i === 2 }));
const PAGE = 25;
const SOURCES = [{ id: 11, label: 'Meeting of 17 November' }, { id: 12, label: 'Meeting of 10 November' }, { id: 13, label: 'Meeting of 3 November' }];

let revisions = new Map();
let staleSpent = false;
let sentKeys = new Map();
let started = [];
let log = [];
export const resetStartLive = () => {
  revisions = new Map();
  staleSpent = false;
  sentKeys = new Map();
  started = [];
  log = [];
};
/** Every POST /work this mock received, with the status it answered: tests compare bodies and count starts. */
export const startLiveLog = () => ({ requests: log, started });

const revisionOf = (project) => revisions.get(project.case_id) ?? project.case_revision;
const send = (status, body) => [status, body];
const isInt = (v) => Number.isSafeInteger(v);
const WEEKLY_KEYS = ['case_id', 'case_revision', 'idempotency_key', 'intake', 'line', 'reference'];

function weeklyProblems(body) {
  const fields = [];
  const problem = (name, message) => fields.push({ name, message });
  const keys = Object.keys(body).filter((k) => k !== 'background').sort();
  for (const k of keys) if (!WEEKLY_KEYS.includes(k)) problem(k, 'This field is not accepted.');
  for (const k of WEEKLY_KEYS) if (!(k in body)) problem(k, 'This field is required.');
  if ('idempotency_key' in body && !(typeof body.idempotency_key === 'string' && /^[\x20-\x7e]{1,100}$/.test(body.idempotency_key))) problem('idempotency_key', 'Use 1 to 100 printable characters.');
  if ('reference' in body && !(typeof body.reference === 'string' && body.reference.length >= 1 && body.reference.length <= 160)) problem('reference', 'Use 1 to 160 characters.');
  if ('case_revision' in body && !isInt(body.case_revision)) problem('case_revision', 'This must be a whole number.');
  const inputs = body.intake?.inputs;
  if ('intake' in body) {
    if (!inputs || typeof inputs !== 'object') problem('intake.inputs', 'This field is required.');
    else {
      for (const k of ['template_id', 'content_id']) if (!(k in inputs) || (inputs[k] !== null && !isInt(inputs[k]))) problem(k, 'Send a number or null.');
      for (const k of ['start_at', 'end_at']) if (typeof inputs[k] !== 'string' || inputs[k].length < 1 || inputs[k].length > 64) problem(`intake.inputs.${k}`, 'Use 1 to 64 characters.');
      for (const k of Object.keys(inputs)) if (!['template_id', 'content_id', 'start_at', 'end_at'].includes(k)) problem(`intake.inputs.${k}`, 'This field is not accepted.');
    }
  }
  return fields;
}

// The server's period rules (apps/workflows/factory_reporting.py): each end carries an explicit offset, the window is
// positive and at most eight days, and the period has ended. A date alone has no offset and is refused with no field list.
const AWARE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/;
function periodProblem(inputs) {
  for (const [key, label] of [['start_at', 'Period start'], ['end_at', 'Period end']]) {
    if (!AWARE.test(inputs[key]) || Number.isNaN(Date.parse(inputs[key]))) return `${label} requires an explicit timezone offset`;
  }
  const start = Date.parse(inputs.start_at);
  const end = Date.parse(inputs.end_at);
  if (end <= start || end - start > 8 * 86400000) return 'Select a positive weekly reporting window of at most eight days; this is not a configured publication cadence';
  if (end > Date.parse(NOW)) return 'Selected reporting period must have ended; future progress is unknown';
  return null;
}

// What every start shares once its body is valid: the project, a replayed key, an uncertain first send, a stale revision, then the work.
function finish({ reply, scenario, caseId, key, revision }) {
  const project = PROJECTS.find((p) => p.case_id === caseId);
  if (!project) return reply(404, BODIES[404]);
  const done = sentKeys.get(key);
  if (done) return reply(200, done);
  if (scenario === 'start_uncertain' && !sentKeys.has(`${key}#tried`)) {
    sentKeys.set(`${key}#tried`, true);
    return reply(503, BODIES[503]);
  }
  if ((scenario === 'start_stale' && !staleSpent) || revision !== revisionOf(project)) {
    if (scenario === 'start_stale' && !staleSpent) {
      staleSpent = true;
      revisions.set(project.case_id, revisionOf(project) + 1);
    }
    return reply(409, BODIES[409]);
  }
  const answer = { work_id: 4102, state: 'processing', revision: 1, background: 'not_requested' };
  sentKeys.set(key, answer);
  started.push({ idempotency_key: key, case_id: caseId });
  return reply(200, answer);
}

// An ajv error as the 422 `fields[]` name the server gives it: the dotted path, a missing or extra key named in full.
function schemaProblems(validate, body) {
  if (validate(body)) return [];
  return validate.errors.map((e) => {
    const path = e.instancePath.split('/').filter(Boolean);
    if (e.keyword === 'required') path.push(e.params.missingProperty);
    if (e.keyword === 'additionalProperties') path.push(e.params.additionalProperty);
    const message = e.keyword === 'required' ? 'This field is required.' : e.keyword === 'additionalProperties' ? 'This field is not accepted.' : `This is not valid (${e.message}).`;
    return { name: path.join('.'), message };
  });
}

function start({ raw, scenario, csrfOk }) {
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return send(400, BODIES[400]);
  }
  if (!body || typeof body !== 'object') return send(400, BODIES[400]);
  const entry = { body, status: 0 };
  log.push(entry);
  const reply = (status, answer) => {
    entry.status = status;
    return send(status, answer);
  };
  if (scenario === 'csrf_failed' || !csrfOk) return reply(403, CSRF_FAILED);
  if (scenario === 'start_denied') return reply(403, BODIES[403]);
  if (scenario === 'start_missing') return reply(404, BODIES[404]);
  if (!VALIDATORS[body.line] || body.line === 'pmo-minutes/v1' || body.line === 'pmo-leadership-report/v1' || body.line === 'finance-payroll/v1') {
    return reply(422, { ...BODIES[422], fields: [{ name: 'line', message: 'This line cannot be started here.' }] });
  }
  if (body.line !== WEEKLY) {
    const fields = schemaProblems(VALIDATORS[body.line], body);
    if (fields.length > 0) return reply(422, { ...BODIES[422], fields });
    return finish({ reply, scenario, caseId: body.case_id, key: body.idempotency_key, revision: body.case_revision });
  }
  const fields = weeklyProblems(body);
  if (fields.length > 0) return reply(422, { ...BODIES[422], fields });
  const period = periodProblem(body.intake.inputs);
  if (period) return reply(422, { code: 'action_unavailable', message: period });
  return finish({ reply, scenario, caseId: body.case_id, key: body.idempotency_key, revision: body.case_revision });
}

const MINUTES_PARTS = ['case_revision', 'idempotency_key', 'reference', 'template_id', 'meeting_version_id', 'audience', 'background', 'notes_file'];
const MINUTES_LIMIT = 5 * 1024 * 1024;

// POST /projects/{case_id}/minutes/intake: the multipart parts the server reads (apps/core/factory_api/intake.py MinutesUploadForm).
function minutes({ url, rawBytes, contentType, scenario, csrfOk }) {
  const form = parseMultipart(rawBytes ?? Buffer.alloc(0), contentType);
  const entry = { minutes: form ? { parts: [...Object.keys(form.fields), ...Object.keys(form.files)], fields: form.fields, file: form.files.notes_file?.filename ?? null } : null, path: url.pathname, status: 0 };
  log.push(entry);
  const reply = (status, answer) => {
    entry.status = status;
    return send(status, answer);
  };
  if (!form) return reply(415, BODIES[415]);
  if (scenario === 'csrf_failed' || !csrfOk) return reply(403, CSRF_FAILED);
  if (scenario === 'start_denied') return reply(403, BODIES[403]);
  if (scenario === 'start_missing') return reply(404, BODIES[404]);
  const { fields, files } = form;
  const problems = [];
  const problem = (name, message) => problems.push({ name, message });
  for (const k of [...Object.keys(fields), ...Object.keys(files)]) if (!MINUTES_PARTS.includes(k)) problem(k, 'This field is not accepted.');
  const whole = (v) => /^[1-9]\d*$/.test(v ?? '');
  if (!whole(fields.case_revision)) problem('case_revision', 'Enter a whole number.');
  if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(fields.idempotency_key ?? '')) problem('idempotency_key', 'Enter a valid value.');
  if (!fields.reference || fields.reference.length > 160) problem('reference', fields.reference ? 'Use 160 characters or fewer.' : 'This field is required.');
  if (!whole(fields.template_id)) problem('template_id', fields.template_id === undefined ? 'This field is required.' : 'Enter a whole number.');
  if (fields.meeting_version_id !== undefined && !whole(fields.meeting_version_id)) problem('meeting_version_id', 'Enter a whole number.');
  if (!['internal', 'client'].includes(fields.audience)) problem('audience', fields.audience === undefined ? 'This field is required.' : 'Select a valid choice.');
  if (!files.notes_file) problem('notes_file', 'This field is required.');
  if (problems.length > 0) return reply(422, { ...BODIES[422], fields: problems });
  if (files.notes_file.bytes > MINUTES_LIMIT) return reply(413, BODIES[413]);
  const caseId = caseOf(url.pathname.split('/')[4]);
  return finish({ reply, scenario, caseId, key: fields.idempotency_key, revision: Number.parseInt(fields.case_revision, 10) });
}

/** The source rows of a line's field, filtered by the parent the request names; `before` pages 25 at a time, newest first. */
function sources(url, project, lineKey) {
  const field = url.searchParams.get('field');
  const rows = SOURCE_ROWS[lineKey];
  if (!rows) {
    // The weekly report and any line this mock has no rows for: a short list and no `fields`.
    const before = url.searchParams.get('before');
    const items = before ? SOURCES.filter((s) => s.id < Number.parseInt(before, 10)) : SOURCES;
    return send(200, { case_revision: revisionOf(project), fields: [], field, items, next_before: null });
  }
  const answer = { case_revision: revisionOf(project), fields: Object.keys(rows).sort(), field, items: [], next_before: null };
  if (field === null) return send(200, answer);
  if (!rows[field]) return send(422, { ...BODIES[422], fields: [{ name: 'field', message: 'Choose a supported source field.' }] });
  const parent = url.searchParams.get('parent_id');
  const before = url.searchParams.get('before');
  const all = rows[field].filter((r) => (r.parent === undefined || String(r.parent) === parent) && (before === null || r.id < Number.parseInt(before, 10)));
  const items = all.slice(0, PAGE).map(({ id, label }) => ({ id, label }));
  return send(200, { ...answer, items, next_before: all.length > PAGE ? items[items.length - 1].id : null });
}

/** One live start read or write. Returns [status, body]. */
export function startLive({ method, url, raw, rawBytes, contentType, scenario, csrfOk, persona }) {
  const status = Number(scenario);
  if (BODIES[status]) return send(status, BODIES[status]);
  if (method === 'post') return START_LIVE_MINUTES.test(url.pathname) ? minutes({ url, rawBytes, contentType, scenario, csrfOk }) : start({ raw, scenario, csrfOk });
  if (url.pathname === '/api/v1/lines') return send(200, { items: persona === 'none' ? [] : LINES, as_of: NOW });
  if (persona === 'none') return send(404, BODIES[404]);
  if (url.pathname === '/api/v1/lines/projects') {
    const lineKey = url.searchParams.get('line');
    if (!lineKey) return send(422, { ...BODIES[422], fields: [{ name: 'line', message: 'This field is required.' }] });
    if (!PROJECT_LINES.has(lineKey)) return send(200, { items: [], page: 1, next_page: null });
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const page = Number.parseInt(url.searchParams.get('page') ?? '1', 10);
    if (!(page >= 1 && page <= 10000) || q.length > 120) return send(422, { ...BODIES[422], fields: [{ name: page >= 1 ? 'q' : 'page', message: 'Out of range.' }] });
    const all = PROJECTS.filter((p) => p.title.toLowerCase().includes(q));
    const items = all.slice((page - 1) * PAGE, page * PAGE).map((p) => ({
      ...p,
      case_revision: revisionOf(p),
      django_url: `/projects/${p.case_id}/`,
      source_options_url: `/api/v1/projects/${p.case_id}/intake-sources?line=${lineKey}`,
      workflow_intake_url: lineKey === 'pmo-escalation/v1' ? `/api/v1/projects/${p.case_id}/escalation-register` : null,
    }));
    return send(200, { items, page, next_page: page * PAGE < all.length ? page + 1 : null });
  }
  const caseId = caseOf(url.pathname.split('/')[4]);
  const project = PROJECTS.find((p) => p.case_id === caseId);
  if (!project) return send(404, BODIES[404]);
  if (url.pathname.endsWith('/escalation-register')) {
    const page = Number.parseInt(url.searchParams.get('page') ?? '1', 10);
    return send(200, { revision: revisionOf(project), can_request: true, issues: [], profiles: [], requests: page === 1 ? ESCALATION_REQUESTS : [], evidence: [], next_page: null });
  }
  return sources(url, project, url.searchParams.get('line'));
}
