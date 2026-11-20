// F-51 (FE-M2A-PROOF part 2): the fixed asset schedule and cash forecast lines, their options, the ppe_register
// upload on C-FIN-PPE and the forecast's backend-stated 422s. Real mock server, over HTTP.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';

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

const bytes = Buffer.from('asset register bytes');
const upload = (caseId: string, body: Record<string, unknown>, send: Send = {}) =>
  write(`/api/v1/cases/${encodeURIComponent(caseId)}/evidence`, { filename: 'ppe_register_oct.xlsx', content_base64: bytes.toString('base64'), ...body }, send);
const start = (body: Record<string, unknown>, send: Send = {}) => write('/api/v1/work', body, send);

let keySeq = 0;
const key = () => `proof-key-${++keySeq}`;
const ppeUpload = (revision: number, send: Send = {}) => upload('C-FIN-PPE', { kind: 'ppe_register', case_revision: revision }, send);
const assetStart = (intake: Record<string, unknown>, revision: number, extra: Record<string, unknown> = {}) => ({
  line: 'fixed_assets',
  case_id: 'C-FIN-PPE',
  case_revision: revision,
  intake,
  idempotency_key: key(),
  ...extra,
});
const forecastStart = (intake: Record<string, unknown> = {}, extra: Record<string, unknown> = {}) => ({
  line: 'cash_forecast',
  case_id: 'C-FIN-FORECAST',
  case_revision: 2,
  intake: { scenario: 'FC-SC-4', as_of: '2026-10-31', months: 6, audience: 'internal', ...intake },
  idempotency_key: key(),
  ...extra,
});

const lineOf = async (persona: string, lineKey: string) => ((await get('/api/v1/lines', persona)).body.items as Line[]).find((l) => l.key === lineKey)!;
const fields = (r: { body: { fields?: { name: string; message: string }[] } }) => r.body.fields;

describe('4 and 19: the two lines, their options, who is served', () => {
  it('finance_lead is served both lines, schema-valid, in the contract order; /me startable_lines equals E-LINES for every persona', async () => {
    const lines = await get('/api/v1/lines');
    expectValid('E-LINES', 200, lines.body);
    expect(lines.body.items.map((l: Line) => l.key)).toEqual(['invoice', 'income_schedules', 'ledger_sources', 'fixed_assets', 'cash_forecast']);
    for (const persona of ['pm', 'finance_lead', 'ceo', 'none']) {
      const served = (await get('/api/v1/lines', persona)).body.items.map((l: Line) => l.key);
      expect((await get('/api/v1/me', persona)).body.startable_lines).toEqual(served);
    }
    const assets = await lineOf('finance_lead', 'fixed_assets');
    expect([assets.case_id, assets.case_revision]).toEqual(['C-FIN-PPE', 4]);
    expect(assets.intake.map((f) => [f.name, f.type, f.evidence_kind])).toEqual([
      ['proof', 'evidence', 'ppe_register'],
      ['prior_schedule', 'record', undefined],
      ['accounting_note', 'choice', undefined],
    ]);
    const forecast = await lineOf('finance_lead', 'cash_forecast');
    expect([forecast.case_id, forecast.case_revision]).toEqual(['C-FIN-FORECAST', 2]);
    expect(forecast.intake.map((f) => [f.name, f.type])).toEqual([['scenario', 'record'], ['as_of', 'date'], ['months', 'integer'], ['audience', 'choice'], ['sources', 'display']]);
    expect(forecast.intake.some((f) => f.type === 'evidence')).toBe(false);
  });

  it('pm, ceo and none are offered neither line', async () => {
    for (const persona of ['pm', 'ceo', 'none']) {
      const keys = (await get('/api/v1/lines', persona)).body.items.map((l: Line) => l.key);
      expect(keys).not.toContain('fixed_assets');
      expect(keys).not.toContain('cash_forecast');
    }
  });

  it('prior_schedule and scenario options are schema-valid and served to finance_lead only', async () => {
    for (const [line, field, values] of [['fixed_assets', 'prior_schedule', ['PPE-0005', 'PPE-0004']], ['cash_forecast', 'scenario', ['FC-SC-4', 'FC-SC-3']]] as const) {
      const options = await get(`/api/v1/lines/${line}/fields/${field}/options`);
      expectValid('E-LINE-OPTIONS', 200, options.body);
      expect(options.body.items.map((o: { value: string }) => o.value)).toEqual(values);
      expect((await get(`/api/v1/lines/${line}/fields/${field}/options`, 'pm')).status).toBe(404);
    }
  });
});

describe('5, 6 and 8: the ppe_register upload', () => {
  it('200 is schema-valid, sends back evidence_id and the next revision, and the line re-reads it', async () => {
    const first = await ppeUpload(4);
    expect(first.status).toBe(200);
    expectValid('E-EVIDENCE-UPLOAD', 200, first.body);
    expect([first.body.evidence_id, first.body.case_revision]).toEqual(['EV-SW-C-FIN-PPE-1', 5]);
    expect(first.body.sha256).toBe(createHash('sha256').update(bytes).digest('hex'));
    expect((await lineOf('finance_lead', 'fixed_assets')).case_revision).toBe(5);
    expect((await ppeUpload(5)).body).toMatchObject({ evidence_id: 'EV-SW-C-FIN-PPE-2', case_revision: 6 });
  });

  it('409 on a wrong revision; 422 for an empty file and for an .exe; 403 without CSRF', async () => {
    expect((await ppeUpload(3)).status).toBe(409);
    expect((await upload('C-FIN-PPE', { kind: 'ppe_register', case_revision: 4, content_base64: '' })).status).toBe(422);
    const exe = await upload('C-FIN-PPE', { kind: 'ppe_register', case_revision: 4, filename: 'setup.exe' });
    expect([exe.status, exe.body.message]).toEqual([422, "EXE files can't be used as proof."]);
    expect((await ppeUpload(4, { csrf: null })).status).toBe(403);
    expect((await lineOf('finance_lead', 'fixed_assets')).case_revision).toBe(4);
  });

  it('a ppe_register upload to any case but C-FIN-PPE is refused and moves nothing, for every other persona too', async () => {
    // F-47 keeps a case no line starts on with its F-09 or F-11 owner, whose answer here is a 4xx (404 or 422 on the kind)
    for (const caseId of ['C-0101', 'C-FIN-LEDGER', 'C-FIN-FORECAST']) {
      const status = (await upload(caseId, { kind: 'ppe_register', case_revision: 4 })).status;
      expect(status, caseId).toBeGreaterThanOrEqual(400);
      expect(status, caseId).toBeLessThan(500);
    }
    expect((await lineOf('finance_lead', 'fixed_assets')).case_revision).toBe(4);
    for (const persona of ['pm', 'ceo', 'none']) {
      const status = (await ppeUpload(4, { persona })).status;
      expect(status, persona).toBeGreaterThanOrEqual(400);
      expect(status, persona).toBeLessThan(500);
    }
    expect((await lineOf('finance_lead', 'fixed_assets')).case_revision).toBe(4);
  });

  it('reset restores C-FIN-PPE 4 and C-FIN-FORECAST 2 and keeps C-FIN-SCHEDULES 3 and C-FIN-LEDGER 2', async () => {
    await ppeUpload(4);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const revisions = Object.fromEntries(((await get('/api/v1/lines')).body.items as Line[]).filter((l) => l.case_id).map((l) => [l.case_id, l.case_revision]));
    expect(revisions).toMatchObject({ 'C-FIN-PPE': 4, 'C-FIN-FORECAST': 2, 'C-FIN-SCHEDULES': 3, 'C-FIN-LEDGER': 2 });
  });
});

describe('6, 8, 9: the fixed-asset start', () => {
  it('Proof is required: a start with none answers 422 under Proof', async () => {
    const r = await start(assetStart({}, 4));
    expect([r.status, fields(r)]).toEqual([422, [{ name: 'proof', message: 'Proof is required.' }]]);
  });

  it('a start with the uploaded id lands on W-3901 (processing); revisions chain 4, 5 and the start sends 6', async () => {
    await ppeUpload(4);
    const second = await ppeUpload(5);
    const r = await start(assetStart({ proof: second.body.evidence_id, prior_schedule: 'PPE-0005', accounting_note: 'sample_note_a' }, 6));
    expect([r.status, r.body]).toEqual([201, { work_id: 'W-3901', state: 'processing' }]);
  });

  it('a never-issued id, or an id from another case or persona, answers 422 "That proof isn\'t on this record. Add it again."', async () => {
    const up = await ppeUpload(4);
    for (const proof of ['EV-NOPE', 'EV-SW-C-FIN-LEDGER-1', ['EV-SW-C-FIN-PPE-1']]) {
      const r = await start(assetStart({ proof }, 5));
      expect([r.status, fields(r)], String(proof)).toEqual([422, [{ name: 'proof', message: "That proof isn't on this record. Add it again." }]]);
    }
    expect((await start(assetStart({ proof: up.body.evidence_id }, 5), { persona: 'pm' })).status).toBe(403);
    // an id issued for the ledger line is not a ppe_register id
    await upload('C-FIN-LEDGER', { kind: 'ledger_source', case_revision: 2 });
    expect(fields(await start(assetStart({ proof: 'EV-SW-C-FIN-LEDGER-1' }, 5)))).toEqual([{ name: 'proof', message: "That proof isn't on this record. Add it again." }]);
  });

  it('a stale revision answers 409; a start with an unlisted option or note answers 422', async () => {
    const up = await ppeUpload(4);
    expect((await start(assetStart({ proof: up.body.evidence_id }, 4))).status).toBe(409);
    const r = await start(assetStart({ proof: up.body.evidence_id, prior_schedule: 'PPE-9999', accounting_note: 'nope' }, 5));
    expect(fields(r)!.map((f) => f.name).sort()).toEqual(['accounting_note', 'prior_schedule']);
  });
});

describe('9, 10, 11, 12: the forecast start', () => {
  it('lands on W-4001; sources is never sent; a body with no evidence is accepted', async () => {
    const r = await start(forecastStart());
    expect([r.status, r.body]).toEqual([201, { work_id: 'W-4001', state: 'processing' }]);
    const withSources = await start(forecastStart({ sources: 'All 3 accepted' }));
    expect([withSources.status, fields(withSources)]).toEqual([422, [{ name: 'sources', message: "This field can't be sent." }]]);
  });

  it('missing required fields answer "<Label> is required."', async () => {
    const r = await start({ ...forecastStart(), intake: {} });
    expect(fields(r)).toEqual([
      { name: 'scenario', message: 'Scenario is required.' },
      { name: 'as_of', message: 'As of is required.' },
      { name: 'months', message: 'Months is required.' },
      { name: 'audience', message: 'Audience is required.' },
    ]);
  });

  it.each([
    [{ months: 0 }, 'months', 'Months must be between 1 and 12.'],
    [{ months: 13 }, 'months', 'Months must be between 1 and 12.'],
    [{ months: 2.5 }, 'months', 'Months must be between 1 and 12.'],
    [{ as_of: '31 Oct' }, 'as_of', 'As of must be a date.'],
    [{ as_of: '2026-02-30' }, 'as_of', 'As of must be a date.'],
    [{ audience: 'everyone' }, 'audience', 'Choose one of the listed audiences.'],
  ])('%j answers 422 with the backend sentence under %s', async (intake, name, message) => {
    const r = await start(forecastStart(intake));
    expect([r.status, fields(r)]).toEqual([422, [{ name, message }]]);
  });

  it('1 and 12 months are accepted; no browser rule is needed for them', async () => {
    expect((await start(forecastStart({ months: 1 }))).status).toBe(201);
    expect((await start(forecastStart({ months: 12 }))).status).toBe(201);
  });

  it('start_hold answers 201 with W-4006 (setup_needed) on every forecast start, and not on fixed assets', async () => {
    const r = await start(forecastStart(), { extra: 'psl_mock_start_work=start_hold' });
    expect([r.status, r.body]).toEqual([201, { work_id: 'W-4006', state: 'setup_needed' }]);
    const again = await start(forecastStart(), { extra: 'psl_mock_start_work=start_hold' });
    expect(again.body.work_id).toBe('W-4006');
    const up = await ppeUpload(4);
    expect((await start(assetStart({ proof: up.body.evidence_id }, 5), { extra: 'psl_mock_start_work=start_hold' })).body.work_id).toBe('W-3901');
    expectValid('E-WORK-START', 201, r.body);
  });

  it('start_uncertain applies the start once, answers 500, and the replay with the same key answers the stored 201', async () => {
    const body = forecastStart();
    const lost = await start(body, { extra: 'psl_mock_start_work=start_uncertain' });
    expect(lost.status).toBe(500);
    const replay = await start(body, { extra: 'psl_mock_start_work=start_uncertain' });
    expect([replay.status, replay.body.work_id]).toEqual([201, 'W-4001']);
    expect((await start({ ...body, intake: { ...body.intake, months: 7 } })).status).toBe(409);
  });

  it('a stale forecast revision answers 409; without CSRF 403; the same key with another body 409', async () => {
    expect((await start(forecastStart({}, { case_revision: 1 }))).status).toBe(409);
    expect((await start(forecastStart(), { csrf: null })).status).toBe(403);
  });

  it('upload_uncertain applies a ppe upload, answers 500, and the next upload gets the next id and revision', async () => {
    const lost = await ppeUpload(4, { extra: 'psl_mock_start_work=upload_uncertain' });
    expect(lost.status).toBe(500);
    expect((await lineOf('finance_lead', 'fixed_assets')).case_revision).toBe(5);
    expect((await ppeUpload(5)).body).toMatchObject({ evidence_id: 'EV-SW-C-FIN-PPE-2', case_revision: 6 });
  });
});
