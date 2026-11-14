import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createStartWorkMock } from '../mock/start-work.mjs';

type Operation = {
  operationId: string;
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
const PERSONAS = ['pm', 'finance_lead', 'ceo', 'none'];

type Field = { name: string; label: string; type: string; required: boolean; options_source?: string; depends_on?: string };
type Line = { key: string; intake: Field[] };
type Option = { value: string; label: string; case_id?: string; case_revision?: number; disabled_reason?: string };
type Page = { items: Option[]; next_cursor?: string; as_of: string };

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

async function get(path: string, persona = 'pm') {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  const text = await response.text();
  return { status: response.status, text, body: JSON.parse(text) };
}

async function post(body: unknown, persona = 'pm', csrf = `mock-csrf-${persona}`) {
  const response = await fetch(`${base}/api/v1/work`, {
    method: 'POST',
    headers: { Cookie: `psl_mock_persona=${persona}`, 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
}

const optionsPath = (line: string, field: string, query = '') =>
  `/api/v1/lines/${encodeURIComponent(line)}/fields/${encodeURIComponent(field)}/options${query}`;

let keySeq = 0;
const key = () => `test-key-${++keySeq}`;

/** One valid start per line, as pm, with the case each line resolves to. */
const VALID: Record<string, { case_id: string; case_revision: number; intake: Record<string, unknown>; work_id: string }> = {
  invoice: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', milestone: 'M-0103' }, work_id: 'W-1401' },
  weekly_report: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', week: { from: '2026-11-09', to: '2026-11-13' } }, work_id: 'W-1402' },
  minutes: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', meeting: 'MTG-0417', audience: 'client' }, work_id: 'W-1403' },
  issue_followup: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', issue: 'ISS-0233' }, work_id: 'W-1404' },
  change_request: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', request: 'Add WhatsApp reminders' }, work_id: 'W-1405' },
  emergency_change: { case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', incident: 'INC-0031', plan: 'Fall back to the old router.' }, work_id: 'W-1406' },
  escalation: { case_id: 'C-0101', case_revision: 6, intake: { project: 'P-0101', from_issue: 'ISS-0241', escalate_to: 'client' }, work_id: 'W-1407' },
  leadership_report: { case_id: 'C-PMO-REPORTING', case_revision: 4, intake: { report: 'internal_tuesday', report_date: '2026-11-17' }, work_id: 'W-1408' },
};
const startBody = (line: string, overrides: Record<string, unknown> = {}) => {
  const { case_id, case_revision, intake } = VALID[line];
  return { line, case_id, case_revision, intake, idempotency_key: key(), ...overrides };
};

describe('E-LINES', () => {
  it.each(PERSONAS)('%s: schema-valid, and /me startable_lines equals its line keys', async (persona) => {
    const lines = await get('/api/v1/lines', persona);
    expect(lines.status).toBe(200);
    expectValid('E-LINES', 200, lines.body);
    const me = await get('/api/v1/me', persona);
    expect(me.body.startable_lines).toEqual(lines.body.items.map((l: Line) => l.key));
  });

  it('pm and finance_lead open invoice directly; the ceo has all 8 lines and no default_line; none has none', async () => {
    const pm = (await get('/api/v1/lines', 'pm')).body;
    expect(pm.default_line).toBe('invoice');
    expect(pm.items.map((l: Line) => l.key)).toEqual(Object.keys(VALID));
    const finance = (await get('/api/v1/lines', 'finance_lead')).body;
    expect([finance.default_line, finance.items.map((l: Line) => l.key)]).toEqual(['invoice', ['invoice']]);
    const ceo = (await get('/api/v1/lines', 'ceo')).body;
    expect(ceo).not.toHaveProperty('default_line');
    expect(ceo.items).toHaveLength(8);
    expect((await get('/api/v1/lines', 'none')).body.items).toEqual([]);
  });

  it('no line starts another way, no field is money, and the only evidence is the optional Proof on minutes and change', async () => {
    const { items } = (await get('/api/v1/lines', 'ceo')).body as { items: (Line & { start_via?: string })[] };
    expect(items.every((l) => l.start_via === undefined || l.start_via === 'work_start')).toBe(true);
    expect(items.flatMap((l) => l.intake).filter((f) => f.type === 'money')).toEqual([]);
    const evidence = items.flatMap((l) => l.intake.filter((f) => f.type === 'evidence').map((f) => [l.key, f.name, f.label, f.required]));
    expect(evidence).toEqual([
      ['minutes', 'proof', 'Proof', false],
      ['change_request', 'proof', 'Proof', false],
    ]);
  });
});

describe('E-LINE-OPTIONS', () => {
  it('every line, field and persona answers schema-valid pages (both pages) and never sends mock-only keys', async () => {
    let checked = 0;
    for (const persona of PERSONAS) {
      const { items } = (await get('/api/v1/lines', persona)).body as { items: Line[] };
      for (const line of items) {
        const projects = ((await get(optionsPath(line.key, 'project', '?limit=50'), persona)).body as Page).items;
        for (const field of line.intake.filter((f) => f.options_source === 'line_options')) {
          const parents = field.depends_on ? projects.map((p) => p.value) : [undefined];
          for (const parent of parents) {
            let cursor: string | undefined;
            do {
              const query = new URLSearchParams({ limit: '20' });
              if (parent) query.set('parent', parent);
              if (cursor) query.set('cursor', cursor);
              const page = await get(optionsPath(line.key, field.name, `?${query}`), persona);
              expect(page.status).toBe(200);
              expectValid('E-LINE-OPTIONS', 200, page.body);
              expect(page.text).not.toMatch(/"_personas"|"_parent"/);
              cursor = (page.body as Page).next_cursor;
              checked += 1;
            } while (cursor);
          }
        }
      }
    }
    expect(checked).toBeGreaterThan(50);
  });

  it('pm has 2 projects, finance_lead only Lagoon, and the ceo 26 over two pages of 20', async () => {
    const labels = async (persona: string, query = '?limit=20') =>
      ((await get(optionsPath('invoice', 'project', query), persona)).body as Page).items.map((o) => o.label);
    expect(await labels('pm')).toEqual(['Lagoon Health · patient app', 'Harmattan Bank · mobile onboarding']);
    expect(await labels('finance_lead')).toEqual(['Lagoon Health · patient app']);
    const first = (await get(optionsPath('invoice', 'project', '?limit=20'), 'ceo')).body as Page;
    expect([first.items.length, first.next_cursor]).toEqual([20, 'o:20']);
    const second = (await get(optionsPath('invoice', 'project', '?limit=20&cursor=o%3A20'), 'ceo')).body as Page;
    expect(second.items).toHaveLength(6);
    expect(second).not.toHaveProperty('next_cursor');
    expect(second.items.at(-1)).toEqual({ value: 'P-0126', label: 'Ojo Foods · ordering app', sample: true });
    expect(await labels('ceo', '?q=harm&limit=20')).toEqual(['Harmattan Bank · mobile onboarding']);
  });

  it('a dependent field is narrowed by parent, empty without one, and shows a disabled reason', async () => {
    expect((await get(optionsPath('invoice', 'milestone', '?limit=20'))).body.items).toEqual([]);
    const lagoon = ((await get(optionsPath('invoice', 'milestone', '?parent=P-0101&limit=20'))).body as Page).items;
    expect(lagoon.map((o) => o.value)).toEqual(['M-0103', 'M-0104']);
    expect(lagoon[1].disabled_reason).toBe("Milestone 4 isn't marked complete yet. Record its completion and proof first.");
    const harmattan = ((await get(optionsPath('invoice', 'milestone', '?parent=P-0102&limit=20'))).body as Page).items;
    expect(harmattan.map((o) => o.value)).toEqual(['M-0202']);
  });

  it('404 for a line the persona was not given, and for a field that has no options', async () => {
    expect((await get(optionsPath('invoice', 'project'), 'none')).status).toBe(404);
    expect((await get(optionsPath('weekly_report', 'project'), 'finance_lead')).status).toBe(404);
    expect((await get(optionsPath('invoice', 'note'))).status).toBe(404);
    expect((await get(optionsPath('invoice', 'nope'))).status).toBe(404);
  });
});

describe('E-WORK-START', () => {
  it.each(Object.keys(VALID))('a valid %s start answers 201 with its work item', async (line) => {
    const result = await post(startBody(line));
    expect(result).toEqual({ status: 201, body: { work_id: VALID[line].work_id, state: 'processing' } });
    expectValid('E-WORK-START', 201, result.body);
  });

  it('the same key and body replays the stored 201 and creates nothing; a different body is 409', () => {
    const mock = createStartWorkMock(openapi);
    const body = startBody('invoice');
    const send = (b: unknown) => mock.handle('E-WORK-START', { url: new URL('http://mock.local/api/v1/work'), raw: JSON.stringify(b), persona: 'pm' });
    const first = send(body);
    // Same content in another key order is the same body.
    const again = send(Object.fromEntries(Object.entries(body).reverse()));
    expect(first).toEqual([201, { work_id: 'W-1401', state: 'processing' }]);
    expect(again).toEqual(first);
    expect(mock.started.size).toBe(1);
    const changed = send({ ...body, intake: { ...body.intake, note: 'changed' } });
    expect(changed).toEqual([
      409,
      { code: 'idempotency_key_reused', message: 'This start was already sent with different details. Close the form and start again.' },
    ]);
    expect(mock.started.size).toBe(1);
    mock.reset();
    expect(mock.started.size).toBe(0);
  });

  it('over HTTP, two posts with the same key and body return identical 201 bodies', async () => {
    const body = startBody('invoice');
    const [a, b] = [await post(body), await post(body)];
    expect(a).toEqual(b);
    expect(a.status).toBe(201);
    const reused = await post({ ...body, case_revision: 7 });
    expect(reused.status).toBe(409);
    expect(reused.body.code).toBe('idempotency_key_reused');
    expectValid('E-WORK-START', 409, reused.body);
  });

  it('403 for a line the persona was not given (finance_lead, weekly_report)', async () => {
    const result = await post(startBody('weekly_report'), 'finance_lead');
    expect(result.status).toBe(403);
    expect(result.body.code).toBe('forbidden');
    expectValid('E-WORK-START', 403, result.body);
  });

  it("404 for a case not served to the persona: pm with Kora's case (ceo only), and a wrong fixed case", async () => {
    const kora = await post(startBody('invoice', { case_id: 'C-0103', case_revision: 1, intake: { project: 'P-0103', milestone: 'M-0103' } }));
    expect(kora).toEqual({ status: 404, body: { code: 'not_found', message: 'We could not find that record.' } });
    expectValid('E-WORK-START', 404, kora.body);
    expect((await post(startBody('invoice', { case_id: 'C-0102' }))).status).toBe(404);
    expect((await post(startBody('leadership_report', { case_id: 'C-0101' }))).status).toBe(404);
  });

  it('409 stale_revision for an old case revision', async () => {
    const result = await post(startBody('invoice', { case_revision: 5 }));
    expect(result.status).toBe(409);
    expect(result.body.code).toBe('stale_revision');
    expectValid('E-WORK-START', 409, result.body);
    expect((await post(startBody('leadership_report', { case_revision: 3 }))).body.code).toBe('stale_revision');
  });

  it('422 names each intake problem', async () => {
    const intake = async (line: string, value: Record<string, unknown>) => {
      const result = await post(startBody(line, { intake: value }));
      expect(result.status).toBe(422);
      expectValid('E-WORK-START', 422, result.body);
      expect(result.body.message).toBe('Check the highlighted fields and try again.');
      return result.body.fields;
    };
    expect(await intake('invoice', { project: 'P-0101' })).toEqual([{ name: 'milestone', message: 'Completed milestone is required.' }]);
    expect(await intake('invoice', { project: 'P-0101', milestone: 'M-0104' })).toEqual([
      { name: 'milestone', message: "Milestone 4 isn't marked complete yet. Record its completion and proof first." },
    ]);
    expect(await intake('invoice', { project: 'P-0101', milestone: 'M-0202' })).toEqual([{ name: 'milestone', message: 'Choose one from the list.' }]);
    expect(await intake('weekly_report', { project: 'P-0101', week: { from: '17/11/2026' }, template: 'x', extra: 1 })).toEqual([
      { name: 'template', message: "This field can't be sent." },
      { name: 'extra', message: "This field can't be sent." },
      { name: 'week', message: 'Enter a valid date range.' },
    ]);
    expect(await intake('minutes', { project: 'P-0101', meeting: 'MTG-0417', audience: 'everyone' })).toEqual([
      { name: 'audience', message: 'Choose one from the list.' },
    ]);
    expect(await intake('change_request', { project: 'P-0101', request: '   ' })).toEqual([
      { name: 'request', message: 'What the client asked for is required.' },
    ]);
    expect(await intake('leadership_report', { report: 'internal_tuesday', report_date: '2026-13-45' })).toEqual([
      { name: 'report_date', message: 'Enter a valid date.' },
    ]);
  });

  it('an invoice on Harmattan also names the billing contact, a field the drawer does not render', async () => {
    const result = await post(startBody('invoice', { case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' } }));
    expect(result.status).toBe(422);
    expect(result.body.fields).toEqual([
      { name: 'billing_contact', message: "The client register has no billing contact for Harmattan Bank. Add one in the project's client details." },
    ]);
  });

  it('422 for a body that is not the request schema, naming the property', async () => {
    const extra = await post({ ...startBody('invoice'), priority: 'high' });
    expect(extra.status).toBe(422);
    expect(extra.body.fields.map((f: { name: string }) => f.name)).toEqual(['priority']);
    expectValid('E-WORK-START', 422, extra.body);
    const { idempotency_key: _omit, ...missing } = startBody('invoice');
    void _omit;
    expect((await post(missing)).body.fields.map((f: { name: string }) => f.name)).toEqual(['idempotency_key']);
    expect((await post('{not json')).status).toBe(422);
  });

  it("a write with another persona's CSRF token gets 403 csrf_failed", async () => {
    const result = await post(startBody('invoice'), 'pm', 'mock-csrf-ceo');
    expect(result).toEqual({ status: 403, body: { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' } });
  });

  it('the ceo can start on any of their 26 projects that carries a case, and not on Ojo Foods', async () => {
    const kora = await post(startBody('change_request', { case_id: 'C-0103', case_revision: 1, intake: { project: 'P-0103', request: 'x' } }), 'ceo');
    expect(kora.body).toEqual({ work_id: 'W-1405', state: 'processing' });
    const ojo = await post(startBody('change_request', { case_id: 'C-0126', case_revision: 1, intake: { project: 'P-0126', request: 'x' } }), 'ceo');
    expect(ojo.status).toBe(404);
  });
});

describe('started work items', () => {
  it('W-1401 to W-1408 are schema-valid E-WORK-ITEMs in processing, marked sample, and served by E-WORK-ITEM', async () => {
    for (const { work_id } of Object.values(VALID)) {
      const item = readJson(`work/${work_id}.json`);
      expectValid('E-WORK-ITEM', 200, item);
      expect([item.id, item.state, item.sample, item.stations[0].status]).toEqual([work_id, 'processing', true, 'current_agent']);
      expect((await get(`/api/v1/work/${work_id}`)).body).toEqual(item);
    }
    expect(readJson('work/W-1408.json').title).toBe('PMO · Leadership report');
  });
});
