// F-86: Start work in the live shapes of contract 1.22.0: GET /lines, GET /lines/projects, GET /projects/{case_id}/intake-sources
// and the weekly branch of POST /work. The v7 start (start-work.mjs) keeps answering its own tests;
// server.mjs hands these routes here when it runs with `liveStart` (the mock run from the command line). Sample data; no business rules.
// Cookie scenarios (psl_mock_scenario or X-Mock-Scenario) for POST /work: start_stale (409 once, the project's revision moves
// on), start_uncertain (503 on the first send of a key, 200 on the same key), start_denied (403), csrf_failed (403 with
// code csrf_failed), start_missing (404). A status number answers every route here with that status.
export const START_LIVE_PATH = /^\/api\/v1\/(lines|lines\/projects|projects\/[^/]+\/intake-sources)$/;
export const START_LIVE_WORK = '/api/v1/work';

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

const line = (key, title, description, can, slug, projects) => ({
  key,
  title,
  description,
  can_submit_via_api: can,
  django_url: `/lines/${slug}/`,
  project_options_url: projects ? `/api/v1/lines/projects?line=${key}` : null,
  submit_url: '/api/v1/work',
});
const LINES = [
  line(WEEKLY, 'Weekly client report', 'Friday report for a client', true, 'pmo-weekly-report', true),
  line('pmo-minutes/v1', 'Minutes after a meeting', 'Formal minutes and action handoff', false, 'pmo-minutes', true),
  line('finance-payroll/v1', 'Payroll', 'Monthly payroll preparation', true, 'finance-payroll', true),
  line('pmo-issues/v1', 'Chase an open issue', 'Issue investigation and owner follow-up', false, 'pmo-issues', true),
];

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
  if (body.line !== WEEKLY) return reply(422, { ...BODIES[422], fields: [{ name: 'line', message: 'This line cannot be started here.' }] });
  const fields = weeklyProblems(body);
  if (fields.length > 0) return reply(422, { ...BODIES[422], fields });
  const project = PROJECTS.find((p) => p.case_id === body.case_id);
  if (!project) return reply(404, BODIES[404]);
  const done = sentKeys.get(body.idempotency_key);
  if (done) return reply(200, done);
  if (scenario === 'start_uncertain' && !sentKeys.has(`${body.idempotency_key}#tried`)) {
    sentKeys.set(`${body.idempotency_key}#tried`, true);
    return reply(503, BODIES[503]);
  }
  if ((scenario === 'start_stale' && !staleSpent) || body.case_revision !== revisionOf(project)) {
    if (scenario === 'start_stale' && !staleSpent) {
      staleSpent = true;
      revisions.set(project.case_id, revisionOf(project) + 1);
    }
    return reply(409, BODIES[409]);
  }
  const answer = { work_id: 4102, state: 'processing', revision: 1, background: 'not_requested' };
  sentKeys.set(body.idempotency_key, answer);
  started.push({ idempotency_key: body.idempotency_key, case_id: body.case_id });
  return reply(200, answer);
}

/** One live start read or write. Returns [status, body]. */
export function startLive({ method, url, raw, scenario, csrfOk, persona }) {
  const status = Number(scenario);
  if (BODIES[status]) return send(status, BODIES[status]);
  if (method === 'post') return start({ raw, scenario, csrfOk });
  if (url.pathname === '/api/v1/lines') return send(200, { items: persona === 'none' ? [] : LINES, as_of: NOW });
  if (persona === 'none') return send(404, BODIES[404]);
  if (url.pathname === '/api/v1/lines/projects') {
    const lineKey = url.searchParams.get('line');
    if (!lineKey) return send(422, { ...BODIES[422], fields: [{ name: 'line', message: 'This field is required.' }] });
    if (lineKey !== WEEKLY) return send(200, { items: [], page: 1, next_page: null });
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const page = Number.parseInt(url.searchParams.get('page') ?? '1', 10);
    if (!(page >= 1 && page <= 10000) || q.length > 120) return send(422, { ...BODIES[422], fields: [{ name: page >= 1 ? 'q' : 'page', message: 'Out of range.' }] });
    const all = PROJECTS.filter((p) => p.title.toLowerCase().includes(q));
    const items = all.slice((page - 1) * PAGE, page * PAGE).map((p) => ({ ...p, case_revision: revisionOf(p), django_url: `/projects/${p.case_id}/`, source_options_url: `/api/v1/projects/${p.case_id}/intake-sources?line=${lineKey}`, workflow_intake_url: null }));
    return send(200, { items, page, next_page: page * PAGE < all.length ? page + 1 : null });
  }
  const caseId = decodeURIComponent(url.pathname.split('/')[4] ?? '');
  const project = PROJECTS.find((p) => p.case_id === caseId);
  if (!project) return send(404, BODIES[404]);
  const before = url.searchParams.get('before');
  const items = before ? SOURCES.filter((s) => s.id < Number.parseInt(before, 10)) : SOURCES;
  return send(200, { case_revision: revisionOf(project), fields: [], field: url.searchParams.get('field'), items, next_before: null });
}
