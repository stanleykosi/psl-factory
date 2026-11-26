// F-116: the archive page (SCR-47) in the live shapes of contract 1.26.x: GET|POST /work/{id}/archive-files, POST .../archive-files/{job}/recovery
// and POST /work/{id}/actions (reconcile). Integer ids 5301 to 5308 only; every other id falls through. (The spec named 4401 to 4407;
// those are taken, so each fixture is a free id in the 53xx range.) Sample data; no business rules.
// 5301 verified (42 files, five groups, receipts); 5302 working (28 confirmed, 10 leased, 4 pending); 5303 uncertain (6 unknown, lookup then
// retry, reconcile offered); 5304 ready to start (no files, three sources); 5305 unavailable to everyone; 5306 two files on hold and the copy
// limit reached; 5307 the work read has revision null; 5308 every file confirmed but not verified.
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route here with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer only the writes; wdrop (the write ran, the answer is lost) and wdrop0 (the answer is lost, nothing ran).
import { workLive } from './work-live.mjs';

export const ARCHIVE_PATH = /^\/api\/v1\/work\/(530[1-8])(\/archive-files|\/archive-files\/(\d+)\/recovery|\/actions)?$/;

const NOW = '2026-11-26T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'source_ids', message: 'Choose at least one source.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const SCENARIO = {
  w403: [403, { code: 'forbidden', message: 'Only the PM can do this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const GROUPS = ['Project documents', 'Costing and SOW', 'Planning', 'Release records', 'Meeting minutes'];
const SOURCES = [{ id: 11, label: 'RFP response' }, { id: 12, label: 'Costing and SOW' }, { id: 13, label: 'Planning' }];
const STATUS = { pending: 'Queued', leased: 'Copying', unknown: 'Confirmation missing', missing: 'File not found', confirmed: 'Archived', held: 'Needs review' };

// a file's job state by its position; `n` files, `states` assigns the state of each index
const makeFiles = (id, n, stateOf, groupOf = (i) => GROUPS[i % GROUPS.length]) =>
  Array.from({ length: n }, (_, i) => ({ id: id * 100 + i, name: `${groupOf(i).toLowerCase().replaceAll(' ', '-')}-${i + 1}.pdf`, group: groupOf(i), source_id: 11 + (i % 3), source_kind: 'document', state: stateOf(i), rev: 1 }));

const START = {
  5301: { files: makeFiles(5301, 42, () => 'confirmed'), verified: true, work: ['verified', 'Verified'] },
  5302: {
    files: makeFiles(5302, 42, (i) => (i < 28 ? 'confirmed' : i < 38 ? 'leased' : 'pending')),
    work: ['processing', 'Processing'],
  },
  5303: {
    files: makeFiles(5303, 42, (i) => (i < 6 ? 'unknown' : 'confirmed'), (i) => (i < 6 ? 'RFP response and submission' : GROUPS[i % GROUPS.length])),
    work: ['effect_uncertain', 'Effect uncertain'],
    actions: ['reconcile'],
  },
  5304: { files: [], canReserve: true, required: [11, 12], work: ['ready', 'Ready'] },
  5306: { files: makeFiles(5306, 6, (i) => (i < 2 ? 'held' : 'confirmed')), limited: true, work: ['action_needed', 'Action needed'] },
  5307: { files: makeFiles(5307, 6, () => 'confirmed'), work: ['action_needed', 'Action needed'], nullRevision: true },
  5308: { files: makeFiles(5308, 6, () => 'confirmed'), finding: 'Every file is copied. The archive index has not been matched yet.', work: ['action_needed', 'Action needed'] },
};

// what the writes changed: id -> { revision, files (state overrides by file id), reserved, retried }
let live = {};
export const resetArchiveLive = () => {
  live = {};
};
const revisionOf = (id) => live[id]?.revision ?? 7;
const stateOfFile = (id, f) => live[id]?.states?.[f.id] ?? f.state;
const reservedOf = (id) => live[id]?.reserved === true;

const filesOf = (id) => {
  const data = START[id];
  if (id === 5304 && reservedOf(id)) return makeFiles(5304, 3, () => 'pending', () => GROUPS[0]);
  return data.files;
};

const read = (id) => {
  const data = START[id];
  const files = filesOf(id).map((f) => {
    const state = stateOfFile(id, f);
    const rev = f.rev + (live[id]?.bumps?.[f.id] ?? 0);
    const lookedUp = live[id]?.lookedUp?.includes(f.id) === true;
    const actions = state === 'unknown' ? ['lookup'] : state === 'missing' && lookedUp ? ['retry'] : [];
    return {
      id: f.id,
      name: f.name,
      status: STATUS[state],
      job: { id: f.id + 90000, revision: rev, state },
      group: f.group,
      source_id: f.source_id,
      source_kind: f.source_kind,
      actions,
      receipt: state === 'confirmed' ? { id: f.id + 70000, at: '2026-11-25T16:00:00Z' } : null,
    };
  });
  const verified = data.verified === true;
  const active = files.some((f) => f.job.state === 'pending' || f.job.state === 'leased');
  return {
    expected_revision: revisionOf(id),
    case_revision: 41,
    plan_id: files.length === 0 ? null : 12,
    store: files.length === 0 ? null : 'archive-store',
    finding: data.finding ?? (files.length === 0 ? 'Nothing has been archived yet.' : verified ? 'The archive is verified.' : 'The archive is not verified yet.'),
    verified,
    can_reserve: data.canReserve === true && !reservedOf(id) && !active,
    limited: data.limited === true,
    required_source_ids: data.required ?? [],
    sources: data.canReserve ? SOURCES : [],
    files,
  };
};

const workState = (id) => (id === 5304 && reservedOf(id) ? ['processing', 'Processing'] : live[id]?.moved ?? START[id].work);

const item = (id) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const [state, label] = workState(id);
  const data = START[id];
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Archive for Kora Logistics',
    line: 'delivery-archive/v1',
    state,
    status_label: label,
    reference: 'ARC-0131',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: `${NOW.slice(0, 17)}${String(revisionOf(id)).padStart(2, '0')}Z`,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: data.nullRevision ? null : revisionOf(id),
    case_revision: 41,
    actions: (data.actions ?? []).filter(() => live[id]?.moved === undefined),
    available_control: [],
    panels: [{ key: 'archive-files', url: `/api/v1/work/${id}/archive-files`, contract_path: '/api/v1/work/{work_id}/archive-files' }],
  };
};

const refused = (field) => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message: 'This field is missing or not accepted.' }] }];
const parse = (rawBytes) => {
  try {
    return JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return null;
  }
};
const bump = (id, patch) => {
  live[id] = { ...live[id], revision: revisionOf(id) + 1, ...patch };
};

function reserve(id, scenario, rawBytes) {
  const body = parse(rawBytes);
  if (body === null) return [400, BODIES[400]];
  const odd = Object.keys(body).find((k) => !['expected_revision', 'case_revision', 'source_ids'].includes(k));
  if (odd) return refused(odd);
  if (!Number.isInteger(body.expected_revision)) return refused('expected_revision');
  if (!Number.isInteger(body.case_revision)) return refused('case_revision');
  if (!Array.isArray(body.source_ids) || body.source_ids.length === 0 || body.source_ids.some((s) => !SOURCES.some((x) => x.id === s))) return [422, BODIES[422]];
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  if (!START[id].canReserve || reservedOf(id)) return [422, { code: 'invalid', message: 'The archive can’t be started now.' }];
  if (body.expected_revision !== revisionOf(id)) return [409, BODIES[409]];
  bump(id, { reserved: true });
  if (scenario === 'wdrop') return ['drop'];
  return [202, { work_id: id, state: 'processing', revision: revisionOf(id), plan_id: 12 }];
}

function recovery(id, jobId, scenario, rawBytes) {
  const body = parse(rawBytes);
  if (body === null) return [400, BODIES[400]];
  const odd = Object.keys(body).find((k) => !['revision', 'action'].includes(k));
  if (odd) return refused(odd);
  if (!Number.isInteger(body.revision)) return refused('revision');
  if (!['lookup', 'retry'].includes(body.action)) return refused('action');
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  const file = read(id).files.find((f) => f.job.id === jobId);
  if (!file) return [404, BODIES[404]];
  if (!file.actions.includes(body.action)) return [422, { code: 'invalid', message: 'That isn’t offered for this file.' }];
  if (body.revision !== file.job.revision) return [409, BODIES[409]];
  const state = live[id]?.states ?? {};
  const bumps = live[id]?.bumps ?? {};
  const lookedUp = live[id]?.lookedUp ?? [];
  const fid = file.id;
  let next = file.job.state;
  if (body.action === 'lookup') {
    // the first two files the store did not confirm are found missing; the rest arrived
    const missing = fid % 100 < 2;
    next = missing ? 'missing' : 'confirmed';
    live[id] = { ...live[id], states: { ...state, [fid]: next }, bumps: { ...bumps, [fid]: (bumps[fid] ?? 0) + 1 }, lookedUp: [...lookedUp, fid] };
  } else {
    next = 'pending';
    live[id] = { ...live[id], states: { ...state, [fid]: next }, bumps: { ...bumps, [fid]: (bumps[fid] ?? 0) + 1 } };
  }
  if (scenario === 'wdrop') return ['drop'];
  return [200, { id: jobId, revision: file.job.revision + 1, state: next }];
}

function actions(id, scenario, rawBytes) {
  const body = parse(rawBytes);
  if (body === null) return [400, BODIES[400]];
  const odd = Object.keys(body).find((k) => !['expected_revision', 'action'].includes(k));
  if (odd) return refused(odd);
  if (!Number.isInteger(body.expected_revision)) return refused('expected_revision');
  if (body.action !== 'reconcile') return refused('action');
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  if (!(START[id].actions ?? []).includes('reconcile')) return [422, { code: 'invalid', message: 'There is nothing to check.' }];
  if (body.expected_revision !== revisionOf(id)) return [409, BODIES[409]];
  bump(id, { moved: ['processing', 'Processing'] });
  if (scenario === 'wdrop') return ['drop'];
  return [202, { work_id: id, state: 'processing', revision: revisionOf(id) }];
}

/** One archive read or write. `scenario` is the cookie or header value. */
export function archiveLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = ARCHIVE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1]);
  if (persona === 'none' || id === 5305) return [404, BODIES[404]];
  const part = found[2];
  if (method === 'post') {
    if (!part) return [405, { code: 'method_not_allowed', message: 'Read only.' }];
    if (!csrfOk) return [403, CSRF_FAILED];
    if (part === '/archive-files') return reserve(id, scenario, rawBytes);
    if (part === '/actions') return actions(id, scenario, rawBytes);
    return recovery(id, Number(found[3]), scenario, rawBytes);
  }
  if (method !== 'get' || part === '/actions' || /recovery$/.test(part ?? '')) return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  return [200, part ? read(id) : item(id)];
}
