// F-36: the contract mock's RFP assignment fixtures (W-3301 to W-3306), their overlay keys (mock/proposals/rfp-assign.json), the
// E-WORK-ASSIGN rules for an item with no workspace, and the Unassigned list for persona pmo_lead. Mock evidence only: it proves the
// mock follows the contract it was given, not what the backend will do.
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
const overlay = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/rfp-assign.json'), 'utf8')) as { $comment: string; assign_extra: object; request_extra: object };
const assignExtra = ajv.compile(overlay.assign_extra);
const requestExtra = ajv.compile(overlay.request_extra);
const workDir = join(__dirname, '../mock/fixtures/work');
const fixture = (name: string) => JSON.parse(readFileSync(join(workDir, name), 'utf8'));

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

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const HEADERS = { Cookie: 'psl_mock_persona=pmo_lead', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pmo_lead' };
const get = async (path: string, headers: Record<string, string> = HEADERS) => {
  const response = await fetch(`${base}${path}`, { headers });
  return { status: response.status, body: (await response.json()) as Json };
};
const post = async (path: string, body: unknown, headers: Record<string, string> = HEADERS) => {
  const response = await fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Json };
};
const assign = (id: string, body: unknown, extraCookie = '') => post(`/api/v1/work/${id}/assignment`, body, { ...HEADERS, Cookie: `${HEADERS.Cookie}${extraCookie}` });
const upload = (caseId: string, kind: string, caseRevision: number) => post(`/api/v1/cases/${caseId}/evidence`, { kind, filename: 'a.eml', content_base64: Buffer.from('From: kemi').toString('base64'), case_revision: caseRevision });
const unassigned = async (dataset = '') => (await get('/api/v1/work?queue=unassigned', { ...HEADERS, Cookie: `${HEADERS.Cookie}${dataset}` })).body;
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { assignments: { work_id: string; status: number; written: boolean; acting_role?: string; evidence_id?: string }[] };

/** The overlay keys are checked on their own against rfp-assign.json, then removed before the generated-schema check. */
function contractItem(body: Json) {
  const copy = structuredClone(body);
  expect(typeof overlay.$comment).toBe('string');
  if (copy.assign) {
    const extras = Object.fromEntries(['roles', 'evidence_kind', 'next'].filter((k) => k in copy.assign).map((k) => [k, copy.assign[k]]));
    expect(assignExtra(extras), ajv.errorsText(assignExtra.errors)).toBe(true);
    for (const key of Object.keys(extras)) delete copy.assign[key];
  }
  return copy;
}

describe('the fixtures', () => {
  const names = readdirSync(workDir).filter((name) => /^W-330[1-6](\.[a-z]+)?\.json$/.test(name));

  it('the set is W-3301 to W-3306 with their .next and W-3306.assign files', () => {
    expect(names).toEqual(['W-3301.json', 'W-3301.next.json', 'W-3302.json', 'W-3302.next.json', 'W-3303.json', 'W-3303.next.json', 'W-3304.json', 'W-3305.json', 'W-3306.assign.json', 'W-3306.json', 'W-3306.next.json']);
  });

  it.each(names.filter((name) => !name.endsWith('.assign.json')))('%s is a sample item that validates once the overlay keys are removed', (name) => {
    const body = fixture(name);
    expect(body.sample).toBe(true);
    expect(itemSchema(contractItem(body)), `${name}: ${ajv.errorsText(itemSchema.errors)}`).toBe(true);
  });

  it('only W-3302 carries the overlay, and the candidates are the board’s', () => {
    expect(Object.keys(fixture('W-3301.json').assign).sort()).toEqual(['candidates', 'note_required', 'role']);
    expect(Object.keys(fixture('W-3302.json').assign).sort()).toEqual(['candidates', 'evidence_kind', 'next', 'note_required', 'role', 'roles']);
    expect(fixture('W-3301.json').assign.candidates.map((c: Json) => c.name)).toEqual(['Tunde Bello', 'Sola Martins', 'Ife Okoro']);
    expect(fixture('W-3301.json').assign.candidates[2]).not.toHaveProperty('hint');
    expect(fixture('W-3304.json').assign.candidates).toEqual([]);
    expect(fixture('W-3305.json')).not.toHaveProperty('assign');
    expect(fixture('W-3303.json').assign).toMatchObject({ note_required: true });
  });

  it('every .next item has no assign and names the PM', () => {
    for (const name of names.filter((n) => n.endsWith('.next.json'))) {
      const body = fixture(name);
      expect(body).not.toHaveProperty('assign');
      expect(body.revision).toBe(2);
      expect(body.rfp.pm.name).toBeTruthy();
    }
  });

  it('the request overlay validates on its own', () => {
    expect(requestExtra({ acting_role: 'ceo', evidence_id: 'EV-1', case_revision: 2 })).toBe(true);
    expect(requestExtra({ acting_role: '' })).toBe(false);
    expect(requestExtra({ case_revision: 0 })).toBe(false);
  });
});

describe('E-WORK-ASSIGN on an item with no workspace', () => {
  it('writes against the item’s own revision: 1 is current, a stale revision is 409', async () => {
    const stale = await assign('W-3301', { expected_revision: 2, person_id: 'P-0007' });
    expect(stale.status).toBe(409);
    const ok = await assign('W-3301', { expected_revision: 1, person_id: 'P-0007' });
    expect(ok).toMatchObject({ status: 200, body: { work_id: 'W-3301', state: 'waiting', revision: 2, assigned_to: 'Tunde Bello' } });
    expect((await get('/api/v1/work/W-3301')).body).not.toHaveProperty('assign');
  });

  it('the cookie psl_mock_assign=stale serves the next revision and answers 409, then the new revision works', async () => {
    expect((await assign('W-3301', { expected_revision: 1, person_id: 'P-0007' }, '; psl_mock_assign=stale')).status).toBe(409);
    expect((await get('/api/v1/work/W-3301')).body.revision).toBe(2);
    expect((await assign('W-3301', { expected_revision: 2, person_id: 'P-0007' })).status).toBe(200);
  });

  it('a typed request with an extra key is 422, and a person outside the candidates is 422', async () => {
    expect(await assign('W-3301', { expected_revision: 1, person_id: 'P-0007', acting_role: 'pmo_lead' })).toMatchObject({ status: 422 });
    expect(await assign('W-3301', { expected_revision: 1, person_id: 'P-0007', evidence_id: 'EV-1' })).toMatchObject({ status: 422 });
    const outside = await assign('W-3301', { expected_revision: 1, person_id: 'P-9999' });
    expect(outside.status).toBe(422);
    expect(outside.body.fields.map((f: Json) => f.name)).toEqual(['person_id']);
    expect((await log()).assignments).toEqual([]);
  });

  it('an overlay request is accepted only for an overlay item', async () => {
    expect((await assign('W-3302', { expected_revision: 1, person_id: 'P-0007', acting_role: 'pmo_lead' })).status).toBe(200);
  });

  it('an acting_role outside roles and an evidence_id not uploaded are 422', async () => {
    const role = await assign('W-3302', { expected_revision: 1, person_id: 'P-0007', acting_role: 'cto' });
    expect(role.status).toBe(422);
    expect(role.body.fields.map((f: Json) => f.name)).toEqual(['acting_role']);
    const proof = await assign('W-3302', { expected_revision: 1, person_id: 'P-0007', evidence_id: 'EV-C-3302-1', case_revision: 1 });
    expect(proof.status).toBe(422);
    expect(proof.body.fields.map((f: Json) => f.name)).toEqual(['evidence_id']);
    expect((await log()).assignments).toEqual([]);
  });

  it('proof: only an overlay item takes the upload, then the evidence id and the new case revision are accepted; an old case_revision is 409', async () => {
    expect((await upload('C-3301', 'assignment_proof', 1)).status).toBe(422);
    expect((await upload('C-3302', 'rule_proof', 1)).status).toBe(422);
    const up = await upload('C-3302', 'assignment_proof', 1);
    expect(up).toMatchObject({ status: 200, body: { evidence_id: 'EV-C-3302-1', case_revision: 2 } });
    const old = await assign('W-3302', { expected_revision: 1, person_id: 'P-0007', acting_role: 'pmo_lead', evidence_id: 'EV-C-3302-1', case_revision: 1 });
    expect(old.status).toBe(409);
    const ok = await assign('W-3302', { expected_revision: 1, person_id: 'P-0007', acting_role: 'ceo', evidence_id: 'EV-C-3302-1', case_revision: 2 });
    expect(ok.status).toBe(200);
    expect((await log()).assignments.at(-1)).toMatchObject({ work_id: 'W-3302', status: 200, written: true, acting_role: 'ceo', evidence_id: 'EV-C-3302-1' });
  });

  it('W-3306 is written and then answers 500; the cookie uncertain answers 500 and writes nothing', async () => {
    expect((await assign('W-3306', { expected_revision: 1, person_id: 'P-0007' })).status).toBe(500);
    expect((await get('/api/v1/work/W-3306')).body).not.toHaveProperty('assign');
    expect((await assign('W-3301', { expected_revision: 1, person_id: 'P-0007' }, '; psl_mock_assign=uncertain')).status).toBe(500);
    expect((await get('/api/v1/work/W-3301')).body).toHaveProperty('assign');
    expect((await log()).assignments.map((a) => [a.work_id, a.status, a.written])).toEqual([['W-3306', 500, true], ['W-3301', 500, false]]);
  });

  it('W-3399 has no fixture: 404', async () => {
    expect((await assign('W-3399', { expected_revision: 1, person_id: 'P-0007' })).status).toBe(404);
  });
});

describe('the Unassigned list for persona pmo_lead', () => {
  it('lists the W-33xx RFP rows, and other personas keep their own answer', async () => {
    const body = await unassigned();
    expect(body.items.map((i: Json) => i.id)).toEqual(['W-3302', 'W-3301', 'W-3303', 'W-3304', 'W-3305', 'W-3306']);
    expect(body.counts.unassigned).toBe(6);
    expect((await get('/api/v1/work?queue=unassigned', { ...HEADERS, Cookie: 'psl_mock_persona=pm' })).status).toBe(403);
    const finance = (await get('/api/v1/work?queue=unassigned', { ...HEADERS, Cookie: 'psl_mock_persona=finance_lead' })).body;
    expect(finance.items.map((i: Json) => i.id)).toEqual(['W-1137', 'W-1138']);
  });

  it('the board sample is the single W-3302 row with the board’s counts', async () => {
    const body = await unassigned('; psl_mock_worklist=board');
    expect(body.items.map((i: Json) => i.id)).toEqual(['W-3302']);
    expect(body.counts).toEqual({ needs_me: 3, waiting_on_others: 2, done: 28, unassigned: 1 });
  });

  it('a written assignment drops the row and the count, and /__mock/reset restores it', async () => {
    await assign('W-3301', { expected_revision: 1, person_id: 'P-0007' });
    const after = await unassigned();
    expect(after.items.map((i: Json) => i.id)).not.toContain('W-3301');
    expect(after.counts.unassigned).toBe(5);
    const board = await unassigned('; psl_mock_worklist=board');
    expect(board.counts.unassigned).toBe(1);
    await assign('W-3302', { expected_revision: 1, person_id: 'P-0007' });
    expect((await unassigned('; psl_mock_worklist=board')).counts.unassigned).toBe(0);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await unassigned()).counts.unassigned).toBe(6);
    expect((await get('/api/v1/work/W-3301')).body).toHaveProperty('assign');
  });

  it('an assignment that failed before writing keeps the row', async () => {
    await assign('W-3301', { expected_revision: 1, person_id: 'P-0007' }, '; psl_mock_assign=uncertain');
    expect((await unassigned()).counts.unassigned).toBe(6);
  });
});
