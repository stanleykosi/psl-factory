// Project retrospective (F-119, SCR-33): the live project-meetings operations and the closure checklist, in the live
// shapes (contract 1.25.0: meeting_records_collection, _record, _detail, _options, _create_action, closure_checklist).
// Cases (sample data only):
//   ...2001 nothing saved, dossier 5001      ...2002 meeting 301, versions 9001 and 9002 (current), dossier 5002
//   ...2003 can_record false, options 403    ...2004 no participants, no proofs
//   ...2005 every save answers 503 and records nothing   ...2006 thirty retrospectives (25 a page)
//   ...2008 not yours: 404 everywhere. Dossier 5009 answers 503. Any other case or dossier: 404.
// Writes check the token and the case revision (409), a repeated reference on another meeting (422 with fields),
// and append a version. POST /__mock/retrospective/bump raises a case's revision, to make a save stale; GET
// /__mock/retrospective/log lists the writes.
const PREFIX = '3f6c1a52-0d2b-4c11-9b0a-5a1e7d9c';
const caseId = (n) => `${PREFIX}${n}`;
export const RETRO_LOG_PATH = '/__mock/retrospective/log';
export const RETRO_BUMP_PATH = '/__mock/retrospective/bump';
const PAGE = 25;

const NOT_FOUND = { code: 'not_found', message: 'This record is unavailable.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const PEOPLE = [{ id: 12, label: 'Tunde Bello' }, { id: 15, label: 'Ada Obi' }];
const PROOFS = [{ id: 87, label: 'Retrospective notes' }, { id: 88, label: 'Test plan v2' }];

const v1Summary = 'Went fine overall. The client team answered quickly.\n\nOlder phones were missed.';
const v2Summary = "## What went well\nUAT finished on time.\n\n## What didn't\nOlder Android phones weren't in the test plan.\n\n## Lessons for next projects\nAsk for the client's device mix during planning.";

const version = (over) => ({ participants: PEOPLE.slice(0, 1), decisions: [], evidence_id: 87, purpose: 'Project retrospective', ...over });

function seed() {
  const cases = {
    '2001': { revision: 41, canRecord: true, canActions: true, options: { participants: PEOPLE, owners: PEOPLE, proofs: PROOFS }, meetings: [], dossier: 5001 },
    '2002': {
      revision: 52, canRecord: true, canActions: true, options: { participants: PEOPLE, owners: PEOPLE, proofs: PROOFS }, dossier: 5002, pinned: 9001,
      meetings: [{ id: 301, reference: 'Retrospective 2026-11-10', actions: [{ case_id: caseId('2002'), revision: 52, id: 701, reference: 'Retro action 1', current: { id: 7011, revision: 1, status: 'open', description: 'Add the device mix to the test plan template.', owner: PEOPLE[0], deadline: null, timing: 'UNKNOWN', recorded_at: '2026-11-12T09:00:00Z' } }],
        versions: [version({ version_id: 9001, version: 1, occurred_at: '2026-11-10T10:00:00Z', summary: v1Summary }), version({ version_id: 9002, version: 2, occurred_at: '2026-11-10T10:00:00Z', summary: v2Summary, decisions: [{ text: "Ask for the client's device mix during planning.", evidence_id: 88, change_evidence_id: 90 }] })] }],
    },
    '2003': { revision: 7, canRecord: false, canActions: false, noOptions: true, options: { participants: [], owners: [], proofs: [] }, meetings: [{ id: 302, reference: 'Retrospective 2026-10-30', actions: [], versions: [version({ version_id: 9301, version: 1, occurred_at: '2026-10-30T10:00:00Z', summary: v2Summary })] }] },
    '2004': { revision: 9, canRecord: true, canActions: false, options: { participants: PEOPLE, owners: [], proofs: [] }, meetings: [{ id: 303, reference: 'Retrospective 2026-10-01', actions: [], versions: [version({ version_id: 9401, version: 1, occurred_at: '2026-10-01T10:00:00Z', summary: v2Summary, participants: [] })] }] },
    '2005': { revision: 11, canRecord: true, canActions: true, fail503: true, options: { participants: PEOPLE, owners: PEOPLE, proofs: PROOFS }, meetings: [] },
    '2006': { revision: 3, canRecord: true, canActions: false, options: { participants: PEOPLE, owners: [], proofs: PROOFS }, meetings: Array.from({ length: 30 }, (_, i) => ({ id: 400 + i, reference: `Retrospective ${i + 1}`, actions: [], versions: [version({ version_id: 9500 + i, version: 1, occurred_at: `2026-09-${String((i % 28) + 1).padStart(2, '0')}T10:00:00Z`, summary: v2Summary })] })) },
  };
  return cases;
}

let cases = seed();
let nextVersionId = 9100;
let nextMeetingId = 800;
let log = [];
export const resetRetrospective = () => {
  cases = seed();
  nextVersionId = 9100;
  nextMeetingId = 800;
  log = [];
};

const current = (m) => m.versions[m.versions.length - 1];
const row = (m, v = current(m)) => ({ id: m.id, version_id: v.version_id, version: v.version, reference: m.reference, kind: 'retrospective', occurred_at: v.occurred_at, purpose: v.purpose });

function checklist(c, n) {
  const m = c.meetings[0];
  const ref = m ? (c.pinned ?? current(m).version_id) : null;
  const closed = (key, title) => ({ key, title, status: 'closed', summary: `${title} is recorded.`, references: [], finding: null });
  return {
    revision: c.revision, as_of: '2026-11-23T09:00:00Z', ready_to_prepare: false, recorded_closure_id: null,
    checks: [
      closed('context', 'Project context'), closed('go_live', 'Go-live accepted'), { ...closed('hypercare', 'Hypercare finished'), status: 'recorded' }, closed('archive', 'Archive complete'), closed('handover', 'Handover to Support'),
      m ? { key: 'retrospective', title: 'Retrospective saved', status: 'current', summary: 'A retrospective is saved.', references: [ref], finding: null } : { key: 'retrospective', title: 'Retrospective saved', status: 'held', summary: 'No retrospective is saved.', references: [], finding: 'No retrospective saved' },
      { key: 'finance', title: 'Finance confirmation', status: 'unknown', summary: 'Not known.', references: [], finding: null }, closed('report', 'Closure report'),
    ],
    debt: null, retrospective_url: m ? `/api/v1/projects/${caseId(n)}/meetings/${m.id}?version_id=${ref}` : null,
  };
}

function detail(c, n, m, versionId, page) {
  const v = versionId ? m.versions.find((x) => x.version_id === versionId) : current(m);
  if (!v) return [404, NOT_FOUND];
  const isCurrent = v === current(m);
  const actions = isCurrent ? m.actions : [];
  return [200, { ...row(m, v), revision: c.revision, summary: v.summary, participants: v.participants, decisions: v.decisions, evidence_id: v.evidence_id, actions: actions.slice((page - 1) * PAGE, page * PAGE), next_page: actions.length > page * PAGE ? page + 1 : null, current: isCurrent }];
}


/** Whether this mock answers the path: only the sample cases above (and the not-yours one). */
export function ownsRetrospective(pathname) {
  return pathname.startsWith(`/api/v1/projects/${PREFIX}`);
}

export function retrospectiveRoute({ method, url, raw, token, expected }) {
  const parts = url.pathname.split('/').slice(4); // [case, ...]
  const n = parts[0].slice(PREFIX.length);
  const c = cases[n];
  if (!c) return [404, NOT_FOUND];
  const rest = parts.slice(1);
  const write = method === 'post';
  if (write && token !== expected) return [403, CSRF_FAILED];
  if (rest.length === 0 && method === 'get') return [200, { case_id: caseId(n), title: 'Sabi Market web store', revision: 1, sample: true, tabs: [], items: [], page: 1, next_page: null }];
  if (rest[0] === 'delivery' && rest[2] === 'closure-checklist' && method === 'get') {
    if (rest[1] === '5009') return [503, { code: 'unavailable', message: 'Not available right now.' }];
    return Number(rest[1]) === c.dossier ? [200, checklist(c, n)] : [404, NOT_FOUND];
  }
  if (rest[0] === 'meetings' && rest.length === 1 && method === 'get') {
    const page = Number(url.searchParams.get('page') ?? 1);
    const all = [...c.meetings].reverse().map((m) => row(m));
    return [200, { revision: c.revision, items: all.slice((page - 1) * PAGE, page * PAGE), next_page: all.length > page * PAGE ? page + 1 : null, can_record: c.canRecord, can_manage_actions: c.canActions }];
  }
  if (rest[0] === 'meetings' && rest[1] === 'options' && method === 'get') {
    if (c.noOptions) return [403, FORBIDDEN];
    return [200, { revision: c.revision, ...c.options, more_participants: false, more_owners: false, more_proofs: false }];
  }
  if (rest[0] === 'meetings' && rest.length === 2 && method === 'get') {
    const m = c.meetings.find((x) => String(x.id) === rest[1]);
    if (!m) return [404, NOT_FOUND];
    const versionId = url.searchParams.get('version_id');
    return detail(c, n, m, versionId ? Number(versionId) : null, Number(url.searchParams.get('page') ?? 1));
  }
  if (rest[0] === 'meetings' && rest.length === 1 && write) {
    let body;
    try { body = JSON.parse(raw); } catch { return [400, { code: 'bad_request', message: 'Unreadable.' }]; }
    log.push({ path: url.pathname, body });
    if (c.fail503) return [503, { code: 'unavailable', message: 'Not available right now.' }];
    if (body.revision !== c.revision) return [409, STALE];
    // 'Retrospective 2026-11-20' stands for a meeting saved elsewhere with that reference.
    // 'Retrospective 2026-11-21': a 422 naming a field the page has no control for.
    if (body.reference === 'Retrospective 2026-11-21') return [422, { code: 'invalid_input', message: 'Check the details and try again.', fields: [{ name: 'participant_ids', message: 'Pick people who are on the project.' }] }];
    const clash = c.meetings.find((m) => m.reference === body.reference && m.id !== body.meeting_id) || (body.meeting_id == null && body.reference === 'Retrospective 2026-11-20');
    if (clash) return [422, { code: 'invalid_input', message: 'Check the details and try again.', fields: [{ name: 'reference', message: 'Meeting reference exists; create a new revision' }] }];
    if (body.evidence_id && !c.options.proofs.some((p) => p.id === body.evidence_id)) return [422, { code: 'invalid_evidence', message: 'That file is not recorded for this project.', fields: [{ name: 'evidence_id', message: 'That file is not recorded for this project.' }] }];
    let m = body.meeting_id ? c.meetings.find((x) => x.id === body.meeting_id) : null;
    if (body.meeting_id && !m) return [404, NOT_FOUND];
    if (m && m.reference !== body.reference) return [422, { code: 'invalid_input', message: 'Check the details and try again.', fields: [{ name: 'reference', message: 'The reference cannot change on a new version.' }] }];
    if (!m) { m = { id: nextMeetingId++, reference: body.reference, actions: [], versions: [] }; c.meetings.push(m); }
    const people = c.options.participants.filter((p) => body.participant_ids.includes(p.id));
    m.versions.push({ version_id: nextVersionId++, version: m.versions.length + 1, occurred_at: body.occurred_at, purpose: body.purpose, summary: body.summary, participants: people, decisions: body.decisions, evidence_id: body.evidence_id });
    c.revision += 1;
    return [201, { ...row(m), revision: c.revision }];
  }
  if (rest[0] === 'actions' && rest[1] === 'create' && write) {
    let body;
    try { body = JSON.parse(raw); } catch { return [400, { code: 'bad_request', message: 'Unreadable.' }]; }
    log.push({ path: url.pathname, body });
    if (body.revision !== c.revision) return [409, STALE];
    // 'Retro action 8': a 422 that names no field, only a message.
    if (body.reference === 'Retro action 8') return [422, { code: 'invalid_input', message: 'The action could not be created.', fields: [] }];
    const all = c.meetings.flatMap((m) => m.actions);
    // 'Retro action 9' stands for an action of another meeting.
    if (all.some((a) => a.reference === body.reference) || body.reference === 'Retro action 9') return [422, { code: 'invalid_input', message: 'Action reference already exists', fields: [{ name: 'reference', message: 'Action reference already exists' }] }];
    const m = c.meetings.find((x) => x.id === body.meeting_id);
    const action = { case_id: caseId(n), revision: c.revision + 1, id: 700 + all.length + 1, reference: body.reference, current: { id: 7000 + all.length + 1, revision: 1, status: 'open', description: body.description, owner: c.options.owners.find((o) => o.id === body.owner_id) ?? null, deadline: body.due_at ?? null, timing: 'UNKNOWN', recorded_at: new Date().toISOString() } };
    if (m) m.actions.push(action);
    c.revision += 1;
    return [201, action];
  }
  return [404, NOT_FOUND];
}

export function retrospectiveAdmin({ method, url, raw }) {
  if (method === 'get' && url.pathname === RETRO_LOG_PATH) return [200, { writes: log }];
  if (method === 'post' && url.pathname === RETRO_BUMP_PATH) {
    const c = cases[JSON.parse(raw).case];
    if (!c) return [404, NOT_FOUND];
    c.revision += 1;
    return [204, null];
  }
  return null;
}
