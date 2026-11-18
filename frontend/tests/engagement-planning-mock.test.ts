// F-31: the contract mock's engagement and planning fixtures (W-2601 to W-2604), their overlay fields
// (mock/proposals/engagement-planning.json), the register scripts and the T-2603 rules. Mock evidence only: it proves the mock
// follows the contract it was given, not what the backend will do.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const itemSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const stepReply = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.responses['200'].content['application/json'].schema);
const workDir = join(__dirname, '../mock/fixtures/work');
const sidecar = join(__dirname, '../mock/fixtures/response/W-2603.recorded.json');
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/engagement-planning.json'), 'utf8')) as Record<string, { properties?: Record<string, unknown> }> & { $comment: string };
const fixture = (path: string) => JSON.parse(readFileSync(path, 'utf8'));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  expect((await fetch(`${base}/__mock/reset`, { method: 'POST' })).status).toBe(204);
});

const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const get = async (path: string, headers: Record<string, string> = HEADERS) => {
  const response = await fetch(`${base}${path}`, { headers });
  return { status: response.status, body: (await response.json()) as Json };
};
const post = async (path: string, body: unknown, headers: Record<string, string> = HEADERS) => {
  const response = await fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Json };
};
let n = 0;
const key = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
const served = async (id: string) => (await get(`/api/v1/work/${id}`)).body;
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { entries: { work_id: string; step: string; status: number; replay: boolean }[]; sends: Record<string, number>; assignments: { work_id: string; person_id: string; status: number }[] };
const upload = (caseId: string, kind: string, caseRevision: number) => post(`/api/v1/cases/${caseId}/evidence`, { kind, filename: 'plan.pdf', content_base64: Buffer.from('%PDF-1.4 plan').toString('base64'), case_revision: caseRevision });

// The overlay fields are checked on their own, then removed before the generated-schema check.
function contractItem(body: Json) {
  const copy = structuredClone(body);
  expect(typeof overlay.$comment).toBe('string');
  if (copy.assign?.default_person_id !== undefined) {
    expect(copy.assign.candidates.map((c: Json) => c.person_id), 'default_person_id is a candidate').toContain(copy.assign.default_person_id);
    expect(Object.keys(copy.assign).filter((k) => !['role', 'candidates', 'note_required'].includes(k)).sort()).toEqual(Object.keys(overlay.assign.properties!).sort());
    delete copy.assign.default_person_id;
    delete copy.assign.default_hint;
  }
  for (const section of copy.workspace?.sections ?? []) {
    for (const row of section.items) {
      if (row.team_key === undefined) continue;
      expect(typeof row.team_key).toBe('string');
      delete row.team_key;
    }
  }
  delete copy.workspace?.links;
  for (const task of copy.tasks ?? []) for (const team of task.response?.teams ?? []) for (const field of Object.keys(overlay.team.properties!)) delete team[field];
  return copy;
}

describe('the fixtures', () => {
  const names = readdirSync(workDir).filter((name) => /^W-260[1-4](\.[a-z]+)?\.json$/.test(name));

  it('the set is W-2601 to W-2604 with their .next and .steps files', () => {
    expect(names).toEqual(['W-2601.json', 'W-2601.next.json', 'W-2601.steps.json', 'W-2602.json', 'W-2602.next.json', 'W-2602.steps.json', 'W-2603.json', 'W-2604.json', 'W-2604.next.json', 'W-2604.steps.json']);
  });

  it('each item and sidecar validates against the generated E-WORK-ITEM schema once the overlay is stripped, is sample data and has numeric revisions', () => {
    for (const name of names.filter((x) => !x.includes('.steps')).concat('../../response/W-2603.recorded.json')) {
      const body = fixture(name.startsWith('..') ? sidecar : join(workDir, name));
      expect(itemSchema(contractItem(body)), `${name} ${ajv.errorsText(itemSchema.errors)}`).toBe(true);
      expect(body.sample, name).toBe(true);
      expect(Number.isInteger(body.revision) && body.revision >= 1, name).toBe(true);
      expect(Number.isInteger(body.workspace.revision) && body.workspace.revision >= 1, name).toBe(true);
    }
  });

  it('default_person_id is one of the candidates, and the overlay fields exist on their own', () => {
    const w2601 = fixture(join(workDir, 'W-2601.json'));
    expect(w2601.assign.candidates.map((c: Json) => c.person_id)).toContain(w2601.assign.default_person_id);
    expect(w2601.assign.candidates).toHaveLength(3);
    expect(w2601.workspace.steps).toBeUndefined();
    const carrying = readdirSync(workDir).filter((name) => /^W-\d+(\.[a-z]+)?\.json$/.test(name) && 'default_person_id' in (fixture(join(workDir, name)).assign ?? {}));
    expect(carrying).toEqual(['W-2601.json']);
    const planning = fixture(join(workDir, 'W-2603.json'));
    const rows = planning.workspace.sections[0].items.filter((r: Json) => r.team_key);
    expect(rows.map((r: Json) => r.team_key)).toEqual(['qa', 'infrastructure']);
  });

  it('the only change to an existing fixture is the one P-0106 lines entry', () => {
    const p0106 = fixture(join(__dirname, '../mock/fixtures/projects/P-0106.json'));
    expect(p0106.lines.at(-1)).toEqual({ line: 'Plan a project', state: 'waiting', work_id: 'W-2603' });
    expect(p0106.lines).toHaveLength(3);
  });

  it('the registered item cites the project and the planning item, and the packet keeps its unknowns', () => {
    const registered = fixture(join(workDir, 'W-2602.next.json'));
    const created = registered.workspace.sections.find((s: Json) => s.key === 'created');
    expect(created.items.flatMap((i: Json) => i.cites)).toEqual([
      { case_id: 'P-0106', label: 'Ojo Foods · ordering app' },
      { work_id: 'W-2603', label: 'Planning · PLN-0031' },
    ]);
    expect(registered.workspace.status).toEqual({ label: 'REGISTERED', tone: 'neutral' });
    expect(registered.workspace.steps).toBeUndefined();
  });
});

describe('confirm the PM and register (W-2601, W-2602)', () => {
  it('the PM confirmation serves W-2601.next, the register step then serves the registered item under W-2601, and the reply validates', async () => {
    const assign = await post('/api/v1/work/W-2601/assignment', { expected_revision: 3, person_id: 'P-0021' });
    expect(assign.status).toBe(200);
    expect(assign.body).toMatchObject({ work_id: 'W-2601', assigned_to: 'Sola Martins' });
    const after = await served('W-2601');
    expect(after.assign).toBeUndefined();
    expect(after.workspace.steps.map((s: Json) => s.key)).toEqual(['register_engagement']);
    const upped = await upload('C-2601', 'plan', after.case_revision);
    expect(upped.status).toBe(200);
    const registered = await post('/api/v1/work/W-2601/steps', { expected_revision: after.workspace.revision, step: 'register_engagement', inputs: { start_date: '2027-01-15' }, evidence_ids: [upped.body.evidence_id], idempotency_key: key() });
    expect(registered.status).toBe(200);
    expect(stepReply(registered.body), ajv.errorsText(stepReply.errors)).toBe(true);
    expect(registered.body).toMatchObject({ work_id: 'W-2601', outcome: 'done', message: 'Engagement EN-0042 registered.' });
    const final = await served('W-2601');
    expect(final.id).toBe('W-2601');
    expect(final.workspace.status.label).toBe('REGISTERED');
    expect(final.workspace.steps).toBeUndefined();
  });

  it('W-2602 register answers done with the message and serves W-2602.next; a repeat of the key replays with no second send', async () => {
    const k = key();
    const body = { expected_revision: 4, step: 'register_engagement', idempotency_key: k };
    const first = await post('/api/v1/work/W-2602/steps', body);
    expect(first.status).toBe(200);
    expect(first.body).toMatchObject({ outcome: 'done', message: 'Engagement EN-0042 registered.', revision: 5 });
    expect((await served('W-2602')).workspace.status.label).toBe('REGISTERED');
    const again = await post('/api/v1/work/W-2602/steps', body);
    expect(again).toEqual(first);
    expect((await log()).sends[k]).toBe(1);
  });

  it('W-2604 answers effect_uncertain and serves the item in that state, with no steps that can be sent again', async () => {
    const first = await post('/api/v1/work/W-2604/steps', { expected_revision: 4, step: 'register_engagement', idempotency_key: key() });
    expect(first.status).toBe(200);
    expect(stepReply(first.body)).toBe(true);
    expect(first.body.outcome).toBe('effect_uncertain');
    const after = await served('W-2604');
    expect(after.state).toBe('effect_uncertain');
    expect(after.reconcile).toBeTruthy();
    expect((await log()).entries.filter((e) => e.work_id === 'W-2604' && !e.replay)).toHaveLength(1);
  });

  it('a stale revision answers 409 and a step the item does not offer answers 404', async () => {
    expect((await post('/api/v1/work/W-2602/steps', { expected_revision: 3, step: 'register_engagement', idempotency_key: key() })).status).toBe(409);
    expect((await post('/api/v1/work/W-2603/steps', { expected_revision: 6, step: 'register_engagement', idempotency_key: key() })).status).toBe(404);
  });

  it('plan evidence uploads to the engagement case in its own kind, 422 for another kind, 409 for a stale case revision', async () => {
    const item = await served('W-2602');
    expect((await upload('C-2602', 'client_document', item.case_revision)).status).toBe(422);
    expect((await upload('C-2602', 'plan', item.case_revision + 1)).status).toBe(409);
    const ok = await upload('C-2602', 'plan', item.case_revision);
    expect(ok.status).toBe(200);
    expect((await served('W-2602')).case_revision).toBe(item.case_revision + 1);
  });

  it('a scripted 403 or 404 answers the same on each item', async () => {
    for (const id of ['W-2601', 'W-2602', 'W-2603']) {
      for (const status of [403, 404]) expect((await get(`/api/v1/work/${id}`, { ...HEADERS, 'X-Mock-Scenario': String(status) })).status).toBe(status);
    }
  });
});

describe('T-2603 on W-2603 (record department input)', () => {
  const recordBody = async (team: string, extra: Json = {}) => {
    const item = await served('W-2603');
    const evidence = await upload('C-2603', 'proof', item.case_revision);
    expect(evidence.status).toBe(200);
    return { expected_revision: item.tasks[0].revision, who: 'R-QA', action: 'estimate', responded_at: '2026-12-11T15:05:00Z', evidence_id: evidence.body.evidence_id, attested: true, case_revision: evidence.body.case_revision, team, estimate_person_days: 45, what: 'Test plan and QA effort', ...extra };
  };

  it('offers QA and Infrastructure, both asking for an estimate', async () => {
    const item = await served('W-2603');
    expect(item.tasks[0].response.teams.map((t: Json) => [t.key, t.estimate_needed])).toEqual([['qa', true], ['infrastructure', true]]);
    expect(item.tasks[0].you_can_act).toBe(true);
  });

  it('a team that is not listed is 422 on team; a team that needs an estimate and sends none is 422 on estimate_person_days', async () => {
    const unlisted = await post('/api/v1/tasks/T-2603/response', await recordBody('security'));
    expect(unlisted.status).toBe(422);
    expect(unlisted.body.message).toContain('team');
    const body = await recordBody('qa');
    delete (body as Json).estimate_person_days;
    const missing = await post('/api/v1/tasks/T-2603/response', body);
    expect(missing.status).toBe(422);
    expect(missing.body.message).toContain('estimate_person_days');
    expect((await served('W-2603')).workspace.status.label).toBe('PLANNING · 2 OF 5 IN');
  });

  it('QA recorded swaps in W-2603.recorded: 3 of 5 in, QA in, its button gone, T-2603 open for Infrastructure only; the 200 names who recorded it', async () => {
    const reply = await post('/api/v1/tasks/T-2603/response', await recordBody('qa'));
    expect(reply.status).toBe(200);
    expect(reply.body.recorded).toMatchObject({ by: { name: 'Tunde Bello' }, summary: 'QA’s input', proof_count: 1 });
    const after = await served('W-2603');
    expect(after.workspace.status.label).toBe('PLANNING · 3 OF 5 IN');
    const qa = after.workspace.sections[0].items.find((r: Json) => r.id === 'D-QA');
    expect(qa.cells.find((c: Json) => c.column === 'status').tag.label).toBe('IN · 11 DEC');
    expect(qa.cells.find((c: Json) => c.column === 'estimate').text).toBe('45 person-days');
    expect(qa.steps).toBeUndefined();
    expect(after.tasks[0].response.teams.map((t: Json) => t.key)).toEqual(['infrastructure']);
    expect(after.tasks[0].response.recorded).toBeUndefined();
  });

  it('a second record for QA after the swap is 422 on team; Infrastructure is still accepted', async () => {
    expect((await post('/api/v1/tasks/T-2603/response', await recordBody('qa'))).status).toBe(200);
    const again = await post('/api/v1/tasks/T-2603/response', await recordBody('qa'));
    expect(again.status).toBe(422);
    expect(again.body.message).toContain('team');
    const infra = await post('/api/v1/tasks/T-2603/response', await recordBody('infrastructure', { who: 'R-INF' }));
    expect(infra.status).toBe(200);
    expect(infra.body.recorded.summary).toBe('Infrastructure’s input');
  });

  it('record-then-fail applies as in F-18: the effect happens, the answer is 502, and the re-read shows it', async () => {
    const body = await recordBody('qa');
    const failed = await post('/api/v1/tasks/T-2603/response', body, { ...HEADERS, Cookie: 'psl_mock_persona=pm; psl_mock_scenario=record-then-fail' });
    expect(failed.status).toBe(502);
    expect((await served('W-2603')).workspace.status.label).toBe('PLANNING · 3 OF 5 IN');
  });

  it('a stale expected_revision is 409 and an attestation that is not true is 422', async () => {
    const stale = await post('/api/v1/tasks/T-2603/response', await recordBody('qa', { expected_revision: 1 }));
    expect(stale.status).toBe(409);
    const unattested = await post('/api/v1/tasks/T-2603/response', await recordBody('qa', { attested: false }));
    expect(unattested.status).toBe(422);
  });

  it('reset clears every swap', async () => {
    expect((await post('/api/v1/tasks/T-2603/response', await recordBody('qa'))).status).toBe(200);
    expect((await post('/api/v1/work/W-2602/steps', { expected_revision: 4, step: 'register_engagement', idempotency_key: key() })).status).toBe(200);
    expect((await post('/api/v1/work/W-2601/assignment', { expected_revision: 3, person_id: 'P-0021' })).status).toBe(200);
    expect((await fetch(`${base}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    expect((await served('W-2603')).workspace.status.label).toBe('PLANNING · 2 OF 5 IN');
    expect((await served('W-2602')).workspace.steps).toHaveLength(1);
    expect((await served('W-2601')).assign).toBeTruthy();
    expect((await log()).entries).toEqual([]);
  });
});
