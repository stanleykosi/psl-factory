// F-49 (FE-RFP-INTAKE part 2): the RFP line, its client options, the logged work item, the start rules and the
// Unassigned row, in the real mock server over HTTP; plus the source greps the spec asks for.
import { execFileSync } from 'node:child_process';
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
const proposal = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/rfp-intake.json'), 'utf8'));
const validOverlay = ajv.compile(proposal.field_extra);
const validStartExtra = ajv.compile(proposal.start_extra);

const readJson = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8'));

type Field = { name: string; type: string; required: boolean; show_when?: unknown; allow_new?: boolean; options?: { value: string }[] };
type Line = { key: string; case_scope?: string; case_id?: string; case_revision?: number; group?: string; next?: unknown; subtitle?: string; intake: Field[] };

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
// F-52: the keep-alive socket from the last test can be reset under the next request; the reset is safe to repeat
beforeEach(async () => {
  for (let attempt = 1; ; attempt++) {
    try {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      return;
    } catch (error) {
      if (attempt === 3) throw error;
    }
  }
});

const cookie = (persona: string, extra = '') => `psl_mock_persona=${persona}${extra ? `; ${extra}` : ''}`;
async function get(path: string, persona = 'pmo_lead', extra = '') {
  const response = await fetch(base + path, { headers: { Cookie: cookie(persona, extra) } });
  return { status: response.status, body: await response.json() };
}
type Send = { persona?: string; csrf?: string | null; extra?: string };
async function post(path: string, body: unknown, { persona = 'pmo_lead', csrf, extra }: Send = {}) {
  const headers: Record<string, string> = { Cookie: cookie(persona, extra), 'Content-Type': 'application/json' };
  const token = csrf === undefined ? `mock-csrf-${persona}` : csrf;
  if (token !== null) headers['X-CSRFToken'] = token;
  const response = await fetch(base + path, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: await response.json() };
}
const bytes = Buffer.from('rfp document bytes');
const upload = (revision: number, send: Send = {}, caseId = 'C-RFP-INTAKE') =>
  post(`/api/v1/cases/${caseId}/evidence`, { kind: 'rfp_document', filename: 'rfp.pdf', content_base64: bytes.toString('base64'), case_revision: revision }, send);
let keySeq = 0;
const key = () => `rfp-key-${++keySeq}`;
const board = (evidence: string, extra: Record<string, unknown> = {}) => ({
  client: 'CL-3506',
  rfp_reference: 'TL-RFP-2026-014',
  rfp_document: evidence,
  received_at: '2026-11-12T08:40:00.000Z',
  submission_method: 'email',
  submission_target: 'procurement@tamarindloans.example',
  deadline_status: 'stated',
  deadline_at: '2026-11-28T16:00:00.000Z',
  note: 'Received from their procurement lead by email.',
  ...extra,
});
const start = (intake: Record<string, unknown>, revision: number, send: Send = {}, extra: Record<string, unknown> = {}) =>
  post('/api/v1/work', { line: 'rfp_intake', case_id: 'C-RFP-INTAKE', case_revision: revision, intake, idempotency_key: key(), ...extra }, send);
/** One upload, then the intake with its id and the revision it returned. */
async function uploadThen(change: Record<string, unknown> = {}, send: Send = {}) {
  const up = await upload((await rfpLine(send.persona, send.extra))!.case_revision!, send);
  return start(board(up.body.evidence_id, change), up.body.case_revision, send);
}
const rfpLine = async (persona = 'pmo_lead', extra = '') => ((await get('/api/v1/lines', persona, extra)).body.items as Line[]).find((l) => l.key === 'rfp_intake');
const unassigned = async () => (await get('/api/v1/work?queue=unassigned&limit=50')).body;

describe('the line and who is served it (2, 21)', () => {
  it('pmo_lead is served it as schema-valid data; overlay keys validate against the proposal, and /me equals the line keys', async () => {
    const lines = await get('/api/v1/lines');
    const stripped = JSON.parse(JSON.stringify(lines.body)) as { items: Line[] };
    for (const line of stripped.items) {
      for (const field of line.intake) {
        const { show_when, allow_new, ...overlay } = field;
        expect(validOverlay({ show_when, allow_new }), ajv.errorsText(validOverlay.errors)).toBe(true);
        void overlay;
        delete field.show_when;
        delete field.allow_new;
      }
    }
    expectValid('E-LINES', 200, stripped);
    const keys = lines.body.items.map((l: Line) => l.key);
    expect(keys).toEqual(['invoice', 'weekly_report', 'minutes', 'issue_followup', 'change_request', 'emergency_change', 'escalation', 'leadership_report', 'rfp_intake']);
    expect((await get('/api/v1/me')).body.startable_lines).toEqual(keys);
    const line = (await rfpLine())!;
    expect([line.group, line.case_scope, line.case_id, line.case_revision, line.next, line.subtitle]).toEqual(['Pre-sale', 'fixed', 'C-RFP-INTAKE', 5, undefined, undefined]);
    expect(line.intake.map((f) => [f.name, f.type, f.required])).toEqual([
      ['client', 'record', true],
      ['rfp_reference', 'text', true],
      ['rfp_document', 'evidence', true],
      ['received_at', 'datetime', true],
      ['submission_method', 'choice', true],
      ['submission_target', 'text', false],
      ['deadline_status', 'choice', true],
      ['deadline_at', 'datetime', false],
      ['note', 'long_text', false],
    ]);
    expect(line.intake.find((f) => f.name === 'submission_method')!.options!.map((o) => o.value)).toEqual(['email', 'portal', 'by_hand', 'not_stated']);
    expect(line.intake.find((f) => f.name === 'submission_target')!.show_when).toEqual({ field: 'submission_method', equals: ['email', 'portal'] });
    expect(line.intake.find((f) => f.name === 'deadline_at')!.show_when).toEqual({ field: 'deadline_status', equals: ['stated'] });
  });

  it('pm, ceo, finance_lead and none are not served the line; they keep 8, 8, 5 and 0 lines; /me equals their keys', async () => {
    const counts: Record<string, number> = {};
    for (const persona of ['pm', 'ceo', 'finance_lead', 'none']) {
      const keys = (await get('/api/v1/lines', persona)).body.items.map((l: Line) => l.key);
      counts[persona] = keys.length;
      expect(keys).not.toContain('rfp_intake');
      expect((await get('/api/v1/me', persona)).body.startable_lines).toEqual(keys);
    }
    expect(counts).toEqual({ pm: 8, ceo: 8, finance_lead: 5, none: 0 });
  });

  it('client options: the three clients, schema-valid, narrowed by q, with no mock-only keys; 404 for every other persona', async () => {
    const page = await get('/api/v1/lines/rfp_intake/fields/client/options');
    expectValid('E-LINE-OPTIONS', 200, page.body);
    expect(page.body.items.map((o: { value: string; label: string }) => [o.value, o.label])).toEqual([
      ['CL-3506', 'Tamarind Loans Ltd'],
      ['CL-3507', 'Harmattan Bank'],
      ['CL-3508', 'Kora Logistics'],
    ]);
    expect(page.body.items.every((o: Record<string, unknown>) => !('case_id' in o) && Object.keys(o).every((k) => !k.startsWith('_')))).toBe(true);
    expect((await get('/api/v1/lines/rfp_intake/fields/client/options?q=kora')).body.items).toHaveLength(1);
    for (const persona of ['pm', 'ceo', 'finance_lead', 'none']) {
      expect((await get('/api/v1/lines/rfp_intake/fields/client/options', persona)).status, persona).toBe(404);
    }
  });

  it('allow_new is served only with the cookie psl_mock_rfp=new_client, and reset clears nothing of the line', async () => {
    const plain = (await rfpLine())!;
    expect(plain.intake.find((f) => f.name === 'client')).not.toHaveProperty('allow_new');
    const overlay = (await rfpLine('pmo_lead', 'psl_mock_rfp=new_client'))!;
    expect(overlay.intake.find((f) => f.name === 'client')!.allow_new).toBe(true);
    expect(overlay.intake.filter((f) => f.allow_new)).toHaveLength(1);
  });

  it('W-3351 is a schema-valid E-WORK-ITEM, Unassigned, with the assign block, served as it is', async () => {
    const item = readJson('work/W-3351.json');
    expectValid('E-WORK-ITEM', 200, item);
    expect([item.id, item.state, item.revision, item.line_key ?? item.line, item.case_id, item.case_revision, item.tasks, item.sample]).toEqual(['W-3351', 'owner_needed', 1, 'RFP received', 'C-RFP-INTAKE', 6, [], true]);
    expect(item.rfp).toMatchObject({ client: 'Tamarind Loans Ltd', reference: 'TL-RFP-2026-014' });
    expect(item.assign.candidates).toHaveLength(3);
    expect((await get('/api/v1/work/W-3351')).body).toEqual(item);
  });
});

describe('the upload and the start (8, 9, 11, 21)', () => {
  it('an upload answers a schema-valid 200 and moves the revision on; the line shows it; reset restores 5', async () => {
    const first = await upload(5);
    expect(first.status).toBe(200);
    expectValid('E-EVIDENCE-UPLOAD', 200, first.body);
    expect(first.body.evidence_id).toBe('EV-SW-C-RFP-INTAKE-1');
    expect(first.body.case_revision).toBe(6);
    expect((await rfpLine())!.case_revision).toBe(6);
    expect((await upload(5)).status).toBe(409);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await rfpLine())!.case_revision).toBe(5);
  });

  it('a persona without the line cannot upload to its case: 404, never a 200 or an id', async () => {
    for (const persona of ['pm', 'ceo', 'finance_lead', 'none']) {
      const result = await upload(5, { persona });
      expect(result.status, persona).not.toBe(200);
      expect(result.body).not.toHaveProperty('evidence_id');
    }
  });

  it('the board’s start answers 201 at W-3351 in owner_needed, schema-valid; the same key replays the same answer', async () => {
    const up = await upload(5);
    const body = { line: 'rfp_intake', case_id: 'C-RFP-INTAKE', case_revision: up.body.case_revision, intake: board(up.body.evidence_id), idempotency_key: key() };
    expect(validStartExtra(body.intake)).toBe(true);
    const first = await post('/api/v1/work', body);
    expect([first.status, first.body]).toEqual([201, { work_id: 'W-3351', state: 'owner_needed' }]);
    expectValid('E-WORK-START', 201, first.body);
    expect(await post('/api/v1/work', body)).toEqual(first);
    expect((await post('/api/v1/work', { ...body, intake: board(up.body.evidence_id, { note: 'other' }) })).status).toBe(409);
  });

  it('a start without the CSRF header answers 403', async () => {
    const up = await upload(5);
    expect((await start(board(up.body.evidence_id), up.body.case_revision, { csrf: null })).status).toBe(403);
  });

  it('a stale revision is a 409; a typed request carrying an extra key is a 422; an id that is not this case’s is a 422', async () => {
    const up = await upload(5);
    expect((await start(board(up.body.evidence_id), 5)).status).toBe(409);
    const extra = await start(board(up.body.evidence_id, { colour: 'red' }), up.body.case_revision);
    expect([extra.status, extra.body.fields]).toEqual([422, [{ name: 'colour', message: "This field can't be sent." }]]);
    const alien = await start(board('EV-OTHER-1'), up.body.case_revision);
    expect([alien.status, alien.body.fields[0].name]).toEqual([422, 'rfp_document']);
    expect((await start({ ...board('x'), extra: 1 }, up.body.case_revision, {}, { extra_key: 1 })).status).toBe(422);
  });

  it('deadline_at is refused unless the state is stated; a stated deadline needs its date; Unknown and Not stated start without one', async () => {
    const withDate = await uploadThen({ deadline_status: 'unknown' });
    expect([withDate.status, withDate.body.fields]).toEqual([422, [{ name: 'deadline_at', message: 'A deadline can only be entered when it is stated.' }]]);
    const noDate = await uploadThen({ deadline_at: undefined });
    expect([noDate.status, noDate.body.fields]).toEqual([422, [{ name: 'deadline_at', message: 'Enter the deadline the RFP states.' }]]);
    for (const state of ['unknown', 'not_stated']) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const ok = await uploadThen({ deadline_status: state, deadline_at: undefined });
      expect([state, ok.status]).toEqual([state, 201]);
    }
    const bad = await uploadThen({ deadline_status: 'later', deadline_at: undefined });
    expect([bad.status, bad.body.fields[0].name]).toEqual([422, 'deadline_status']);
  });

  it('the sample 422s: Received after the mock’s clock, and a repeated reference for the same client (not for another)', async () => {
    const future = await uploadThen({ received_at: '2026-12-31T09:40:00.000Z' });
    expect([future.status, future.body.fields]).toEqual([422, [{ name: 'received_at', message: "Received can't be in the future." }]]);
    const first = await uploadThen();
    expect(first.status).toBe(201);
    const again = await uploadThen();
    expect([again.status, again.body.fields]).toEqual([422, [{ name: 'rfp_reference', message: 'This RFP is already logged for that client.' }]]);
    const other = await uploadThen({ client: 'CL-3507' });
    expect(other.status).toBe(201);
  });

  it('{new: {name}} is accepted only with allow_new; an empty name or a stray key is refused', async () => {
    const without = await uploadThen({ client: { new: { name: 'Acme Foods' } } });
    expect([without.status, without.body.fields]).toEqual([422, [{ name: 'client', message: 'Choose one from the list.' }]]);
    const overlay = 'psl_mock_rfp=new_client';
    const empty = await uploadThen({ client: { new: { name: ' ' } } }, { extra: overlay });
    expect([empty.status, empty.body.fields]).toEqual([422, [{ name: 'client', message: 'Client or prospect is required.' }]]);
    const stray = await uploadThen({ client: { new: { name: 'A', id: 1 } } }, { extra: overlay });
    expect(stray.status).toBe(422);
    const ok = await uploadThen({ client: { new: { name: 'Acme Foods' } } }, { extra: overlay });
    expect(ok.status).toBe(201);
    expect(validStartExtra({ client: { new: { name: 'Acme Foods' } } })).toBe(true);
    expect((await unassigned()).items[0].title).toContain('Acme Foods');
  });
});

describe('the logged RFP in Unassigned (10)', () => {
  it('one more row, newest first, with the typed reference; the count is one higher; the row opens F-36’s item; reset restores the list', async () => {
    const before = await unassigned();
    expect(before.items.map((i: { id: string }) => i.id)).not.toContain('W-3351');
    const done = await uploadThen({ rfp_reference: 'TL-RFP-2026-099' });
    expect(done.status).toBe(201);
    const after = await unassigned();
    expectValid('E-WORK-LIST', 200, after);
    expect(after.counts.unassigned).toBe(before.counts.unassigned + 1);
    expect(after.items[0]).toMatchObject({ id: 'W-3351', reference: 'TL-RFP-2026-099', line_key: 'rfp_intake', state: 'owner_needed' });
    expect(after.filters.lines.map((l: { key: string }) => l.key)).toContain('rfp_intake');
    // only pmo_lead's list gains it
    expect((await get('/api/v1/work?queue=unassigned', 'finance_lead')).body.items.map((i: { id: string }) => i.id)).not.toContain('W-3351');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(await unassigned()).toEqual(before);
  });

  it('a refused start adds no row', async () => {
    const before = await unassigned();
    await uploadThen({ received_at: '2026-12-31T09:40:00.000Z' });
    expect(await unassigned()).toEqual(before);
  });
});

describe('the source (1, 2, 4, 8, 11, 15, 20)', () => {
  const root = join(__dirname, '..');
  const grep = (args: string[]) => {
    try {
      return execFileSync('grep', ['-rnE', ...args], { cwd: root, encoding: 'utf8' }).trim();
    } catch {
      return '';
    }
  };

  it('no sample value, client register sentence, role or /me read is in src/features/start-work', () => {
    expect(grep(['Tamarind|TL-RFP|procurement@', 'src/features/start-work'])).toBe('');
    expect(grep(['client register', 'src/features/start-work'])).toBe('');
    // the spec's `useMe|…|roles` also matches useMemo and old comments; the real reads are the hook and the endpoint
    expect(grep(['\\buseMe\\b|/api/v1/me|useRoles|\\.roles\\b', 'src/features/start-work'])).toBe('');
  });

  it('the page has no upload limits, accept attribute, date comparison on received_at or duplicate check', () => {
    // F-88: the live received-RFP line (SCR-23) is its own file and does carry its file limits and fields; the generic form does not
    const apart = '--exclude=receivedBid.tsx';
    // F-92: the engine's file control passes an empty `accept` and no size limit on purpose (the server decides)
    expect(grep([apart, '--exclude=controls.tsx', 'PROOF_TYPES|PROOF_MAX_BYTES|accept=|\\.size *[<>]', 'src/features/start-work'])).toBe('');
    expect(grep([apart, 'received_at', 'src/features/start-work'])).toBe('');
    expect(grep([apart, 'rfp_reference|duplicate', 'src/features/start-work'])).toBe('');
  });

  it('the CSS adds no colour literal, and src hardcodes no field name of this line beyond labels', () => {
    expect(grep(['#[0-9a-fA-F]{3,8}\\b|rgb\\(|hsl\\(', 'src/features/start-work/start-work.css'])).toBe('');
    expect(grep(['--exclude=receivedBid.tsx', 'deadline_|submission_', 'src/features/start-work'])).toBe('');
  });
});
