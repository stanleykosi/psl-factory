// F-47 (FE-M2A-PROOF): the start-work branch of the evidence mock, its revision map shared with E-LINES,
// E-LINE-OPTIONS and E-WORK-START, the two Finance lines and the uncertain fixtures. Real mock server, over HTTP.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Operation = {
  operationId: string;
  requestBody?: { content: { 'application/json': { schema: object } } };
  responses: Record<string, { content: { 'application/json': { schema: object } } }>;
};
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const byId = (id: string) => Object.values(openapi.paths).flatMap((ops) => Object.values(ops)).find((op) => op?.operationId === id)!;

function expectValid(id: string, status: number, body: unknown) {
  const validate = ajv.compile(byId(id).responses[String(status)].content['application/json'].schema);
  expect(validate(body), `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

const fixtures = join(__dirname, '../mock/fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(join(fixtures, path), 'utf8'));

type Line = { key: string; case_id?: string; case_revision?: number; intake: { name: string; type: string; evidence_kind?: string }[] };

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${base}/__mock/reset`, { method: 'POST' });
});

const cookie = (persona: string, extra = '') => `psl_mock_persona=${persona}${extra ? `; ${extra}` : ''}`;

async function get(path: string, persona = 'finance_lead') {
  const response = await fetch(base + path, { headers: { Cookie: cookie(persona) } });
  return { status: response.status, body: await response.json() };
}

type Send = { persona?: string; csrf?: string | null; extra?: string; scenario?: string };
async function write(path: string, body: unknown, { persona = 'finance_lead', csrf, extra, scenario }: Send = {}) {
  const headers: Record<string, string> = { Cookie: cookie(persona, extra), 'Content-Type': 'application/json' };
  const token = csrf === undefined ? `mock-csrf-${persona}` : csrf;
  if (token !== null) headers['X-CSRFToken'] = token;
  if (scenario) headers['X-Mock-Scenario'] = scenario;
  const response = await fetch(base + path, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: await response.json() };
}

const bytes = Buffer.from('ledger export bytes');
const upload = (caseId: string, body: Record<string, unknown>, send: Send = {}) =>
  write(`/api/v1/cases/${encodeURIComponent(caseId)}/evidence`, { filename: 'qb_export_je7741.pdf', content_base64: bytes.toString('base64'), ...body }, send);
const start = (body: Record<string, unknown>, send: Send = {}) => write('/api/v1/work', body, send);

let keySeq = 0;
const key = () => `proof-key-${++keySeq}`;
const ledgerStart = (proof: unknown, revision: number, extra: Record<string, unknown> = {}) => ({
  line: 'ledger_sources',
  case_id: 'C-FIN-LEDGER',
  case_revision: revision,
  intake: { key: 'QB-JE-7741', ...(proof === undefined ? {} : { proof }) },
  idempotency_key: key(),
  ...extra,
});

const lineOf = async (persona: string, lineKey: string) => ((await get('/api/v1/lines', persona)).body.items as Line[]).find((l) => l.key === lineKey)!;

describe('the two Finance lines, their options and their landing items', () => {
  it('finance_lead is served invoice, income_schedules and ledger_sources, schema-valid, with /me startable_lines equal to them', async () => {
    const lines = await get('/api/v1/lines');
    expectValid('E-LINES', 200, lines.body);
    expect(lines.body.items.map((l: Line) => l.key)).toEqual(['invoice', 'income_schedules', 'ledger_sources', 'fixed_assets', 'cash_forecast']);
    for (const persona of ['pm', 'finance_lead', 'ceo', 'none']) {
      const served = (await get('/api/v1/lines', persona)).body.items.map((l: Line) => l.key);
      expect((await get('/api/v1/me', persona)).body.startable_lines).toEqual(served);
    }
    const schedules = lines.body.items[1];
    expect([schedules.group, schedules.case_scope, schedules.case_id, schedules.case_revision, schedules.next]).toEqual(['Finance back office', 'fixed', 'C-FIN-SCHEDULES', 3, undefined]);
    expect(schedules.intake.map((f: { name: string; type: string; required: boolean }) => [f.name, f.type, f.required])).toEqual([
      ['kind', 'choice', true],
      ['reference', 'text', true],
      ['mapping_run', 'record', true],
      ['proof', 'evidence', true],
    ]);
    const ledger = lines.body.items[2];
    expect([ledger.case_id, ledger.case_revision, ledger.next]).toEqual(['C-FIN-LEDGER', 2, undefined]);
    expect(ledger.intake.map((f: { name: string; evidence_kind?: string }) => [f.name, f.evidence_kind])).toEqual([
      ['key', undefined],
      ['proof', 'ledger_source'],
      ['continues', undefined],
    ]);
  });

  it('the Finance lines are not served to pm or ceo (Conflicts 7)', async () => {
    for (const persona of ['pm', 'ceo']) {
      const keys = (await get('/api/v1/lines', persona)).body.items.map((l: Line) => l.key);
      expect(keys).not.toContain('income_schedules');
      expect(keys).not.toContain('ledger_sources');
    }
  });

  it('mapping_run and continues options are schema-valid and served only to finance_lead', async () => {
    const mapping = await get('/api/v1/lines/income_schedules/fields/mapping_run/options');
    expectValid('E-LINE-OPTIONS', 200, mapping.body);
    expect(mapping.body.items.map((o: { value: string }) => o.value)).toEqual(['MR-0044', 'MR-0043']);
    const continues = await get('/api/v1/lines/ledger_sources/fields/continues/options');
    expectValid('E-LINE-OPTIONS', 200, continues.body);
    expect(continues.body.items).toEqual([{ value: 'LED-0051', label: 'LED-0051 · QB-JE-7702 · 06 Nov', sample: true }]);
    expect((await get('/api/v1/lines/ledger_sources/fields/continues/options', 'pm')).status).toBe(404);
  });

  it('W-4401 and W-4402 are schema-valid E-WORK-ITEMs in processing, sample, served by E-WORK-ITEM', async () => {
    for (const [id, caseId, step] of [
      ['W-4401', 'C-FIN-SCHEDULES', 'Reading income_detail_oct.xlsx'],
      ['W-4402', 'C-FIN-LEDGER', 'Reading qb_export_je7741.pdf'],
    ]) {
      const item = readJson(`work/${id}.json`);
      expectValid('E-WORK-ITEM', 200, item);
      expect([item.id, item.state, item.sample, item.case_id, item.agent.name, item.agent.steps[0].text, item.tasks]).toEqual([id, 'processing', true, caseId, 'Chidi', step, []]);
      expect((await get(`/api/v1/work/${id}`)).body).toEqual(item);
    }
  });
});

describe('uploads on a start-work case', () => {
  it('an upload validates against the request schema, answers a schema-valid 200 and moves the revision on, seen by E-LINES', async () => {
    const body = { kind: 'ledger_source', filename: 'qb_export_je7741.pdf', content_base64: bytes.toString('base64'), case_revision: 2 };
    const validate = ajv.compile(byId('E-EVIDENCE-UPLOAD').requestBody!.content['application/json'].schema);
    expect(validate(body)).toBe(true);
    const first = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 });
    expect(first.status).toBe(200);
    expectValid('E-EVIDENCE-UPLOAD', 200, first.body);
    expect(first.body).toEqual({ evidence_id: 'EV-SW-C-FIN-LEDGER-1', sha256: createHash('sha256').update(bytes).digest('hex'), case_revision: 3 });
    expect((await lineOf('finance_lead', 'ledger_sources')).case_revision).toBe(3);
    const second = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 3 });
    expect(second.body).toMatchObject({ evidence_id: 'EV-SW-C-FIN-LEDGER-2', case_revision: 4 });
    // the other Finance case is apart
    expect((await lineOf('finance_lead', 'income_schedules')).case_revision).toBe(3);
  });

  it('a project case: the revision moves on in E-LINE-OPTIONS, and only for that persona', async () => {
    const first = await upload('C-0101', { kind: 'meeting_notes', case_revision: 6 }, { persona: 'pm' });
    expect(first.body).toMatchObject({ evidence_id: 'EV-SW-C-0101-1', case_revision: 7 });
    const page = await get('/api/v1/lines/minutes/fields/project/options', 'pm');
    expect(page.body.items.find((o: { value: string }) => o.value === 'P-0101').case_revision).toBe(7);
    const ceo = await get('/api/v1/lines/minutes/fields/project/options', 'ceo');
    expect(ceo.body.items.find((o: { value: string }) => o.value === 'P-0101').case_revision).toBe(6);
  });

  it('only a case the line starts on is start work\'s: a project not served or a case nobody has answers 404; 409 on a stale revision', async () => {
    expect((await upload('C-0102', { kind: 'ledger_source', case_revision: 3 })).status).toBe(404);
    expect((await upload('C-0103', { kind: 'meeting_notes', case_revision: 1 }, { persona: 'pm' })).status).toBe(404);
    expect((await upload('C-NOPE', { kind: 'ledger_source', case_revision: 2 })).status).toBe(404);
    // the ledger kind on the schedules case is not start work's (TECH-1-2): its work-item owner (F-09) refuses the kind
    const elsewhere = await upload('C-FIN-SCHEDULES', { kind: 'ledger_source', case_revision: 3 });
    expect(elsewhere.status).toBe(422);
    expect((await lineOf('finance_lead', 'income_schedules')).case_revision).toBe(3);
    const stale = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 1 });
    expect(stale.status).toBe(409);
    expectValid('E-EVIDENCE-UPLOAD', 409, stale.body);
  });

  it('422: empty content, and the backend-stated .exe sample, each with a message; nothing stored or moved', async () => {
    const empty = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2, content_base64: '' });
    expect(empty.status).toBe(422);
    expectValid('E-EVIDENCE-UPLOAD', 422, empty.body);
    const exe = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2, filename: 'setup.EXE' });
    expect([exe.status, exe.body]).toEqual([422, { code: 'invalid', message: "EXE files can't be used as proof." }]);
    expect((await lineOf('finance_lead', 'ledger_sources')).case_revision).toBe(2);
  });

  it('CSRF missing or wrong: 403; a scenario answers first, as on the M1 path', async () => {
    expect((await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 }, { csrf: null })).status).toBe(403);
    expect((await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 }, { csrf: 'mock-csrf-pm' })).status).toBe(403);
    const scenario = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 }, { scenario: '422' });
    expect(scenario.status).toBe(422);
    expect((await lineOf('finance_lead', 'ledger_sources')).case_revision).toBe(2);
  });

  it('uploads to C-SETUP-* and to work-item cases still go to their F-11 and F-09 owners', async () => {
    // F-09: C-1601's response proof keeps its own ids (EV-<case>-<n>) and its own revision.
    const f09 = await upload('C-1601', { kind: 'client_response_proof', case_revision: 4 }, { persona: 'pm' });
    expect([f09.status, f09.body.evidence_id, f09.body.case_revision]).toEqual([200, 'EV-C-1601-1', 5]);
    // a kind no Start work line has, on C-0101, is not this branch's: the start-work revision does not move
    await upload('C-0101', { kind: 'client_response_proof', case_revision: 6 }, { persona: 'pm' });
    const page = await get('/api/v1/lines/minutes/fields/project/options', 'pm');
    expect(page.body.items.find((o: { value: string }) => o.value === 'P-0101').case_revision).toBe(6);
    const setup = await upload('C-SETUP-ANY', { kind: 'ledger_source', case_revision: 1 });
    expect(setup.body.evidence_id ?? '').not.toMatch(/^EV-SW-/);
  });
});

describe('routing (TECH-1-2)', () => {
  it('ownsUpload needs the kind of a served line and a case that line starts on', async () => {
    // @ts-expect-error plain ESM module without type declarations
    const { createStartWorkMock } = await import('../mock/start-work.mjs');
    const mock = createStartWorkMock(openapi);
    const owns = (caseId: string, kind: string, persona = 'finance_lead') =>
      mock.ownsUpload(new URL(`http://x/api/v1/cases/${caseId}/evidence`), JSON.stringify({ kind }), persona);
    expect(owns('C-FIN-LEDGER', 'ledger_source')).toBe(true);
    expect(owns('C-FIN-SCHEDULES', 'schedule_source')).toBe(true);
    expect(owns('C-FIN-SCHEDULES', 'ledger_source')).toBe(false);
    expect(owns('C-0102', 'ledger_source')).toBe(false);
    expect(owns('C-0101', 'meeting_notes', 'pm')).toBe(true);
    expect(owns('C-0103', 'meeting_notes', 'pm')).toBe(false);
    expect(owns('C-0103', 'meeting_notes', 'ceo')).toBe(true);
    expect(owns('C-1601', 'client_response_proof', 'pm')).toBe(false);
    expect(owns('C-FIN-LEDGER', 'ledger_source', 'pm')).toBe(false);
  });
});

describe('starts carrying proof', () => {
  it('the ledger start after two uploads: case_revision 4 and the second id answer 201 W-4201 (F-45 repoint)', async () => {
    await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 });
    await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 3 });
    expect((await start(ledgerStart('EV-SW-C-FIN-LEDGER-2', 2))).status).toBe(409);
    const ok = await start(ledgerStart('EV-SW-C-FIN-LEDGER-2', 4));
    expect([ok.status, ok.body]).toEqual([201, { work_id: 'W-4201', state: 'processing' }]);
  });

  it('the schedule and minutes starts with proof answer W-4401 and W-1403', async () => {
    await upload('C-FIN-SCHEDULES', { kind: 'schedule_source', case_revision: 3, filename: 'income_detail_oct.xlsx' });
    const schedule = await start({
      line: 'income_schedules',
      case_id: 'C-FIN-SCHEDULES',
      case_revision: 4,
      intake: { kind: 'income_detail', reference: 'SCH-INC-2026-10', mapping_run: 'MR-0044', proof: 'EV-SW-C-FIN-SCHEDULES-1' },
      idempotency_key: key(),
    });
    expect([schedule.status, schedule.body.work_id]).toEqual([201, 'W-4401']);
    await upload('C-0101', { kind: 'meeting_notes', case_revision: 6 }, { persona: 'pm' });
    const minutes = await start(
      { line: 'minutes', case_id: 'C-0101', case_revision: 7, intake: { project: 'P-0101', meeting: 'MTG-0417', audience: 'client', proof: 'EV-SW-C-0101-1' }, idempotency_key: key() },
      { persona: 'pm' },
    );
    expect([minutes.status, minutes.body.work_id]).toEqual([201, 'W-1403']);
  });

  it('proof from another case, another persona, or never issued answers 422 "That proof isn\'t on this record. Add it again."', async () => {
    const wrong = { name: 'proof', message: "That proof isn't on this record. Add it again." };
    await upload('C-FIN-SCHEDULES', { kind: 'schedule_source', case_revision: 3 });
    const otherCase = await start(ledgerStart('EV-SW-C-FIN-SCHEDULES-1', 2));
    expect([otherCase.status, otherCase.body.fields]).toEqual([422, [wrong]]);
    await upload('C-0101', { kind: 'meeting_notes', case_revision: 6 }, { persona: 'pm' });
    const otherPersona = await start(
      { line: 'minutes', case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', meeting: 'MTG-0417', audience: 'client', proof: 'EV-SW-C-0101-1' }, idempotency_key: key() },
      { persona: 'ceo' },
    );
    expect([otherPersona.status, otherPersona.body.fields]).toEqual([422, [wrong]]);
    expect((await start(ledgerStart('EV-SW-C-FIN-LEDGER-9', 2))).body.fields).toEqual([wrong]);
    expect((await start(ledgerStart(['EV-SW-C-FIN-LEDGER-1'], 2))).body.fields).toEqual([wrong]);
  });

  it('a required proof left empty answers "Proof is required."', async () => {
    const empty = await start(ledgerStart(undefined, 2));
    expect([empty.status, empty.body.fields]).toEqual([422, [{ name: 'proof', message: 'Proof is required.' }]]);
  });

  it('reset restores revision 6 on C-0101, 3 on C-FIN-SCHEDULES and 2 on C-FIN-LEDGER, and forgets issued ids', async () => {
    await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 });
    await upload('C-FIN-SCHEDULES', { kind: 'schedule_source', case_revision: 3 });
    await upload('C-0101', { kind: 'meeting_notes', case_revision: 6 }, { persona: 'pm' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await lineOf('finance_lead', 'ledger_sources')).case_revision).toBe(2);
    expect((await lineOf('finance_lead', 'income_schedules')).case_revision).toBe(3);
    const page = await get('/api/v1/lines/minutes/fields/project/options', 'pm');
    expect(page.body.items.find((o: { value: string }) => o.value === 'P-0101').case_revision).toBe(6);
    expect((await start(ledgerStart('EV-SW-C-FIN-LEDGER-1', 2))).status).toBe(422);
  });
});

describe('uncertain fixtures (psl_mock_start_work)', () => {
  it('upload_uncertain: the first upload is stored and moves the revision on, then answers 500; the second gets a new id and the start accepts it', async () => {
    const extra = 'psl_mock_start_work=upload_uncertain';
    const lost = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 }, { extra });
    expect(lost.status).toBe(500);
    expect((await lineOf('finance_lead', 'ledger_sources')).case_revision).toBe(3);
    const again = await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 3 }, { extra });
    expect([again.status, again.body.evidence_id, again.body.case_revision]).toEqual([200, 'EV-SW-C-FIN-LEDGER-2', 4]);
    expect((await start(ledgerStart('EV-SW-C-FIN-LEDGER-2', 4), { extra })).status).toBe(201);
  });

  it('start_uncertain: the first start is stored and answers 500; a replay with the same key and body answers its 201', async () => {
    const extra = 'psl_mock_start_work=start_uncertain';
    await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 }, { extra });
    const body = ledgerStart('EV-SW-C-FIN-LEDGER-1', 3);
    expect((await start(body, { extra })).status).toBe(500);
    const replay = await start(body, { extra });
    expect([replay.status, replay.body]).toEqual([201, { work_id: 'W-4201', state: 'processing' }]);
    expect((await start({ ...body, intake: { key: 'other' } }, { extra })).status).toBe(409);
  });
});
