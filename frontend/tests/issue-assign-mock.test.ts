// F-30: the contract mock's E-WORK-ASSIGN (mock/workspace.mjs) and the four issue fixtures. Mock evidence only: it proves
// the mock follows the contract it was given, not what the backend will do.
import { readFileSync, readdirSync } from 'node:fs';
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
const assignOp = openapi.paths['/api/v1/work/{work_id}/assignment'].post;
const reply = (status: number) => ajv.compile(assignOp.responses[String(status)].content['application/json'].schema);
const itemSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const dir = join(__dirname, '../mock/fixtures/work');
const fixture = (name: string) => JSON.parse(readFileSync(join(dir, `${name}.json`), 'utf8'));

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
const GOOD = { expected_revision: 2, person_id: 'T-ENG' };

async function assign(body: unknown, headers: Record<string, string> = HEADERS, workId = 'W-2413') {
  const response = await fetch(`${base}/api/v1/work/${workId}/assignment`, { method: 'POST', headers, body: typeof body === 'string' ? body : JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}
const cookie = (extra: string) => ({ ...HEADERS, Cookie: `psl_mock_persona=pm; ${extra}` });
const served = async (workId: string) => (await (await fetch(`${base}/api/v1/work/${workId}`, { headers: HEADERS })).json()) as { revision: number; state: string; assign?: unknown; workspace: { revision: number; status: { label: string } } };
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { assignments: { work_id: string; person_id: string; status: number; written: boolean }[] };

// the two F-30 proposal keys are removed before the generated schema check, each checked on its own
type Loose = { assign?: { candidates: { kind?: unknown }[] }; workspace?: { steps?: { starts_line?: { line_key?: unknown; prefill?: unknown } }[] } };
function contractItem(body: Loose) {
  const copy = structuredClone(body);
  for (const candidate of copy.assign?.candidates ?? []) {
    expect(['person', 'team', 'outside_party']).toContain(candidate.kind);
    delete candidate.kind;
  }
  for (const step of copy.workspace?.steps ?? []) {
    if (step.starts_line === undefined) continue;
    expect(typeof step.starts_line.line_key).toBe('string');
    expect(typeof step.starts_line.prefill).toBe('object');
    delete step.starts_line;
  }
  return copy;
}

describe('the four issue fixtures', () => {
  const names = readdirSync(dir).filter((n) => /^W-241[1-4](\.next)?\.json$/.test(n));

  it('each item and sidecar validates against E-WORK-ITEM, is sample data and carries numeric revisions', () => {
    expect(names).toEqual(['W-2411.json', 'W-2411.next.json', 'W-2412.json', 'W-2412.next.json', 'W-2413.json', 'W-2413.next.json', 'W-2414.json']);
    for (const name of names) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expect(itemSchema(contractItem(body)), `${name} ${ajv.errorsText(itemSchema.errors)}`).toBe(true);
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('issue_followup');
      expect(body.workspace.context.project.case_id, name).toBe('P-0101');
      expect(body.revision).toBeGreaterThanOrEqual(1);
      expect(body.workspace.revision).toBeGreaterThanOrEqual(1);
    }
  });

  it('the proposal keys appear only here: starts_line on W-2412, candidate kind on W-2413', () => {
    const all = readdirSync(dir).filter((n) => /^W-\d+(\.[a-z]+)?\.json$/.test(n));
    const text = (n: string) => readFileSync(join(dir, n), 'utf8');
    expect(all.filter((n) => text(n).includes('"starts_line"'))).toEqual(['W-2412.json']);
    expect(all.filter((n) => /"candidates"[\s\S]*"kind": "(team|outside_party)"/.test(text(n)))).toEqual(['W-2413.json']);
  });

  it('the step scripts name only steps the item offers; raise_escalation has none', () => {
    for (const id of ['W-2411', 'W-2412']) {
      const keys = fixture(id).workspace.steps.map((s: { key: string }) => s.key);
      for (const step of Object.keys(fixture(`${id}.steps`))) expect(keys).toContain(step);
    }
    expect(fixture('W-2412.steps')).not.toHaveProperty('raise_escalation');
  });

  it('the mock serves each fixture as itself', async () => {
    for (const id of ['W-2411', 'W-2412', 'W-2413', 'W-2414']) expect(await (await fetch(`${base}/api/v1/work/${id}`, { headers: HEADERS })).json()).toEqual(fixture(id));
  });

  it('the register row for ISS-0233 opens W-2411', () => {
    const tab = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/tabs/P-0101.registers.json'), 'utf8'));
    const rows = JSON.stringify(tab);
    expect(rows).not.toContain('W-1002');
    expect(tab.rows ?? rows).toBeTruthy();
    expect(rows).toMatch(/"work_id":\s*"W-2411"/);
  });
});

describe('E-WORK-ASSIGN on the mock', () => {
  it('checks in order: CSRF, the item, the body, an unlisted person, the revision; then success bumps the revision', async () => {
    expect((await assign(GOOD, { ...HEADERS, 'X-CSRFToken': 'nope' })).status).toBe(403);
    expect((await assign(GOOD, HEADERS, 'W-2499')).status).toBe(404);
    const bad = await assign({ expected_revision: 2, person_id: 'T-ENG', note: 'x'.repeat(2001), extra: true });
    expect(bad.status).toBe(422);
    expect(reply(422)(bad.body)).toBe(true);
    expect((bad.body.fields as { name: string }[]).map((f) => f.name).sort()).toEqual(['extra', 'note']);
    expect((await assign('not json')).status).toBe(422);
    const unlisted = await assign({ expected_revision: 2, person_id: 'P-9999' });
    expect(unlisted.status).toBe(422);
    expect((unlisted.body.fields as { name: string }[]).map((f) => f.name)).toEqual(['person_id']);
    expect((await assign({ expected_revision: 1, person_id: 'T-ENG' })).status).toBe(409);
    expect((await log()).assignments).toEqual([{ work_id: 'W-2413', person_id: 'T-ENG', expected_revision: 1, status: 409, written: false }]);

    const ok = await assign({ ...GOOD, note: 'Raised by Lagoon Health support' });
    expect(ok.status).toBe(200);
    expect(reply(200)(ok.body)).toBe(true);
    expect(ok.body).toMatchObject({ work_id: 'W-2413', revision: 3, assigned_to: 'Engineering' });
    const after = await served('W-2413');
    expect(after).toMatchObject({ revision: 3, workspace: { revision: 3, status: { label: 'FOLLOW-UP STARTED' } } });
    expect(after.assign).toBeUndefined();
    // the owner is set: the served item offers no one any more, so the same request is refused
    expect((await assign(GOOD)).status).toBe(422);
  });

  it('an item with no assign offers no one: any person_id is a 422', async () => {
    const response = await assign({ expected_revision: 3, person_id: 'T-ENG' }, HEADERS, 'W-2411');
    expect(response.status).toBe(422);
  });

  it('cookies: stale moves the item on then 409; invalid names person_id; uncertain writes nothing; uncertain_written writes then 500', async () => {
    const stale = await assign(GOOD, cookie('psl_mock_assign=stale'));
    expect(stale.status).toBe(409);
    expect((await served('W-2413')).workspace.revision).toBe(3);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });

    const invalid = await assign(GOOD, cookie('psl_mock_assign=invalid'));
    expect(invalid.status).toBe(422);
    expect((invalid.body.fields as { name: string }[]).map((f) => f.name)).toEqual(['person_id']);

    const uncertain = await assign(GOOD, cookie('psl_mock_assign=uncertain'));
    expect(uncertain.status).toBe(500);
    expect((await served('W-2413')).workspace.revision).toBe(2);
    expect((await log()).assignments.filter((a) => a.written)).toHaveLength(0);

    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const written = await assign(GOOD, cookie('psl_mock_assign=uncertain_written'));
    expect(written.status).toBe(500);
    const after = await served('W-2413');
    expect(after.workspace.revision).toBe(3);
    expect(after.assign).toBeUndefined();
    expect((await log()).assignments.filter((a) => a.written)).toHaveLength(1);
  });

  it('a scenario cookie answers first; reset clears the served item and the log', async () => {
    expect((await assign(GOOD, cookie('psl_mock_scenario=401'))).status).toBe(401);
    expect((await log()).assignments).toEqual([]);
    expect((await assign(GOOD)).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await served('W-2413')).workspace.revision).toBe(2);
    expect((await log()).assignments).toEqual([]);
  });

  it('E-WORK-STEP on W-2411 and W-2412 still goes through the step handler and serves the next version', async () => {
    const k = '00000000-0000-4000-8000-000000000001';
    const step = await fetch(`${base}/api/v1/work/W-2411/steps`, { method: 'POST', headers: HEADERS, body: JSON.stringify({ expected_revision: 3, step: 'post_owner_update', inputs: { update_type: 'progress', update: 'x' }, idempotency_key: k }) });
    expect(step.status).toBe(200);
    expect((await served('W-2411')).workspace.revision).toBe(4);
    const reply2 = await fetch(`${base}/api/v1/work/W-2412/steps`, { method: 'POST', headers: HEADERS, body: JSON.stringify({ expected_revision: 3, step: 'record_reply', inputs: { reply: 'x' }, idempotency_key: '00000000-0000-4000-8000-000000000002' }) });
    expect(reply2.status).toBe(200);
    expect((await served('W-2412')).workspace.status.label).toBe('REPLY RECORDED');
  });
});
