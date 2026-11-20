// F-41: the contract mock for SCR-20 (E-INVOICES, mock/invoices.mjs) and SCR-32 (the W-3801 to W-3813 reminder items on
// E-WORK-ITEM, E-WORK-STEP and E-WORK-ACTION). Mock evidence only: the mock sends no email and writes no money record.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody } from '../mock/invoices.mjs';

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schema = (path: string, method: string) => openapi.paths[path][method].responses['200'].content['application/json'].schema;
const validInvoices = ajv.compile(schema('/api/v1/finance/invoices', 'get'));
const validItem = ajv.compile(schema('/api/v1/work/{work_id}', 'get'));
const workDir = join(__dirname, '../mock/fixtures/work');
const responseDir = join(__dirname, '../mock/fixtures/response');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(() => fetch(`${base}/__mock/reset`, { method: 'POST' }));

type Body = { items: { reference: string; invoice_id: string }[]; next_cursor?: string; total?: number } & Record<string, unknown>;
async function list(query = '', cookies: Record<string, string> = {}) {
  const cookie = Object.entries({ psl_mock_persona: 'finance_lead', ...cookies }).map(([k, v]) => `${k}=${v}`).join('; ');
  const response = await fetch(`${base}/api/v1/finance/invoices${query}`, { headers: { Cookie: cookie } });
  return { status: response.status, body: (await response.json()) as Body };
}
const refs = (body: Body) => body.items.map((r) => r.reference);

async function step(workId: string, body: Record<string, unknown>) {
  const response = await fetch(`${base}/api/v1/work/${workId}/steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-finance_lead', Cookie: 'psl_mock_persona=finance_lead' },
    body: JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
}
const getItem = async (workId: string) => (await fetch(`${base}/api/v1/work/${workId}`, { headers: { Cookie: 'psl_mock_persona=finance_lead' } })).json();
const log = async () => (await fetch(`${base}/__mock/workspace-log`)).json();
const key = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

/** PROPOSAL G-SCR32-3 `attachment` is checked on its own, then removed before the schema check. */
function attachmentStripped(body: Record<string, unknown>) {
  const copy = structuredClone(body) as { workspace?: { sections: { items: { attachment?: unknown }[] }[]; steps?: { submit_label?: unknown }[] } };
  // PROPOSAL (UX-2-3) `steps[].submit_label` is removed the same way
  for (const step of copy.workspace?.steps ?? []) {
    if (step.submit_label !== undefined) expect(typeof step.submit_label).toBe('string');
    delete step.submit_label;
  }
  for (const section of copy.workspace?.sections ?? []) {
    for (const item of section.items) {
      if (item.attachment === undefined) continue;
      expect(item.attachment).toEqual({ label: expect.any(String), size_bytes: expect.any(Number) });
      delete item.attachment;
    }
  }
  return copy;
}

describe('E-INVOICES (AC 26)', () => {
  it.each(['board', 'known', 'unknown', 'contract', 'empty', 'paged'])('variant %s is valid against the v7 200 schema once the proposal fields are stripped', async (variant) => {
    const { status, body } = await list('', { psl_mock_invoices: variant });
    expect(status).toBe(200);
    expect(validInvoices(contractBody(body)), ajv.errorsText(validInvoices.errors)).toBe(true);
    for (const row of body.items as unknown as Record<string, { amount?: string; unknown: boolean }>[]) {
      for (const name of ['invoiced', 'received', 'owed']) {
        const amount = row[name];
        // a money value is a decimal string when known, and no amount (never 0) when not
        if (amount.unknown) expect(amount).not.toHaveProperty('amount');
        else expect(amount.amount).toMatch(/^\d+\.\d{2}$/);
      }
    }
  });

  it('the board variant is the SCR-20 desktop board: four rows, totals with "+ Unknown" on owed only, the note and the filters', async () => {
    const { body } = await list();
    expect(refs(body)).toEqual(['INV-0398', 'INV-0391', 'INV-0402', 'INV-0388']);
    expect(body.total).toBe(4);
    expect(body.totals_detail).toEqual({
      owed: { known: { amount: '7300000.00', currency: 'NGN' }, has_unknown: true },
      overdue: { known: { amount: '6800000.00', currency: 'NGN' }, has_unknown: false },
      received_this_month: { known: { amount: '4700000.00', currency: 'NGN' }, has_unknown: false },
    });
    expect(body.agent_note).toMatchObject({ agent: 'chidi', work_id: 'W-3801', strong_lines: [1] });
    expect((body.items as unknown as { sample: boolean }[]).every((r) => r.sample === true)).toBe(true);
  });

  it('contract: the overlay is gone and totals.owed is unknown with no amount', async () => {
    const { body } = await list('', { psl_mock_invoices: 'contract' });
    for (const k of ['totals_detail', 'period', 'bank_data_as_of', 'coverage', 'agent_note']) expect(body).not.toHaveProperty(k);
    for (const row of body.items) {
      expect(row).not.toHaveProperty('overdue');
      expect(row).not.toHaveProperty('milestone_label');
    }
    expect(body.totals).toEqual({ owed: { currency: 'NGN', unknown: true } });
  });

  it.each([
    ['pm', 403],
    ['none', 403],
    ['finance_lead', 200],
    ['ceo', 200],
    ['admin', 200],
  ])('persona %s answers %i', async (persona, status) => {
    expect((await list('', { psl_mock_persona: persona })).status).toBe(status);
  });

  it.each(['401', '403', '404'])('the scenario cookie %s answers that status', async (scenario) => {
    expect((await list('', { psl_mock_scenario: scenario })).status).toBe(Number(scenario));
  });

  it('error answers 500 with the server error body', async () => {
    const { status, body } = await list('', { psl_mock_invoices: 'error' });
    expect(status).toBe(500);
    expect(body).toMatchObject({ code: 'server_error' });
  });

  it('q and status narrow the rows on the server, and total follows', async () => {
    expect(refs((await list('?q=harm')).body)).toEqual(['INV-0391']);
    expect(refs((await list('?q=INV-04')).body)).toEqual(['INV-0402']);
    expect((await list('?q=harm')).body.total).toBe(1);
    expect(refs((await list('?status=issued')).body)).toHaveLength(4);
    expect(refs((await list('?status=overdue')).body)).toEqual(['INV-0391']);
    expect(refs((await list('?status=part_paid')).body)).toEqual(['INV-0398']);
    expect(refs((await list('?status=paid')).body)).toEqual(['INV-0388']);
    const bogus = (await list('?status=written_off')).body;
    expect(bogus.items).toEqual([]);
    expect(bogus.total).toBe(0);
  });

  it('paged: two rows and a cursor, then the rest and no cursor', async () => {
    const first = (await list('', { psl_mock_invoices: 'paged' })).body;
    expect(refs(first)).toEqual(['INV-0398', 'INV-0391']);
    expect(first.next_cursor).toBe('o2');
    const rest = (await list(`?cursor=${first.next_cursor}`, { psl_mock_invoices: 'paged' })).body;
    expect(refs(rest)).toEqual(['INV-0402', 'INV-0388']);
    expect(rest).not.toHaveProperty('next_cursor');
  });
});

describe('reminder work fixtures (AC 26)', () => {
  const names = readdirSync(workDir).filter((name) => /^W-38\d\d(\.[a-z_.]+)?\.json$/.test(name) && !name.includes('.steps'));
  const outcomes = readdirSync(responseDir).filter((name) => /^W-38\d\d\./.test(name));

  it('every item, sidecar and reconcile outcome is valid against E-WORK-ITEM once attachment is removed, and sample unless W-3813', () => {
    expect(names.filter((n) => /^W-38\d\d\.json$/.test(n))).toHaveLength(13);
    expect(outcomes).toHaveLength(9);
    for (const name of names) {
      const body = readJson(join(workDir, name));
      expect(validItem(attachmentStripped(body)), `${name}: ${ajv.errorsText(validItem.errors)}`).toBe(true);
      expect(body.sample, name).toBe(name !== 'W-3813.json');
      expect(body.workspace.line_key, name).toBe('payment_reminder');
    }
    for (const name of outcomes) expect(validItem(attachmentStripped(readJson(join(responseDir, name)))), name).toBe(true);
  });

  it('no reminder item offers a resend, and no fact or sentence names the second-reminder interval', () => {
    for (const name of [...names.map((n) => join(workDir, n)), ...outcomes.map((n) => join(responseDir, n))]) {
      const text = readFileSync(name, 'utf8');
      expect(text, name).not.toMatch(/7 days|second reminder|"resend"/);
    }
  });

  it('send_reminder, edit_draft and set_aside on W-3801 each serve their own next version', async () => {
    expect((await step('W-3801', { expected_revision: 1, step: 'edit_draft', inputs: { subject: 's', message: 'm' }, idempotency_key: key(1) })).status).toBe(200);
    expect((await getItem('W-3801')).workspace.version).toEqual({ label: 'Draft v2', number: 2 });
    expect((await step('W-3801', { expected_revision: 2, step: 'send_reminder', idempotency_key: key(2) })).status).toBe(200);
    const sentItem = await getItem('W-3801');
    expect(sentItem.workspace.status.label).toBe('SENT · CHECKING DELIVERY');
    expect(sentItem.workspace.sections.find((s: { kind: string }) => s.kind === 'recipients').items.map((i: { receipt: string }) => i.receipt)).toEqual(['not_yet', 'not_yet']);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await step('W-3801', { expected_revision: 1, step: 'set_aside', idempotency_key: key(3) })).status).toBe(200);
    expect((await getItem('W-3801')).workspace.status.label).toBe('SET ASIDE');
  });

  it('a repeated key is a replay with no second send; reset clears the item and the log', async () => {
    const body = { expected_revision: 1, step: 'send_reminder', idempotency_key: key(4) };
    const first = await step('W-3801', body);
    const again = await step('W-3801', body);
    expect(again).toEqual(first);
    const entries = (await log()).entries as { idempotency_key: string; replay: boolean; step: string }[];
    expect(entries.map((e) => e.replay)).toEqual([false, true]);
    expect((await log()).sends).toEqual({ [key(4)]: 1 });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await log()).entries).toEqual([]);
    expect((await getItem('W-3801')).workspace.version.label).toBe('Draft v1');
  });

  it('W-3803: the send answers effect_uncertain and the item is then locked for reconcile; a reconcile serves the chosen outcome; no second send', async () => {
    const sentReply = await step('W-3803', { expected_revision: 1, step: 'send_reminder', idempotency_key: key(5) });
    expect(sentReply.body).toMatchObject({ outcome: 'effect_uncertain' });
    const uncertain = await getItem('W-3803');
    expect(uncertain.state).toBe('effect_uncertain');
    expect(uncertain.allowed_actions).toEqual(['reconcile']);
    expect(uncertain.reconcile.outcomes).toEqual(['delivered', 'not_delivered', 'unknown']);
    const action = await fetch(`${base}/api/v1/work/W-3803/actions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-finance_lead', Cookie: 'psl_mock_persona=finance_lead' },
      body: JSON.stringify({ expected_revision: uncertain.revision, action: 'reconcile', outcome: 'not_delivered' }),
    });
    expect(action.status).toBe(200);
    expect(await getItem('W-3803')).toEqual(readJson(join(responseDir, 'W-3803.not_delivered.json')));
    const sends = (await log()).entries.filter((e: { step: string }) => e.step === 'send_reminder');
    expect(sends).toHaveLength(1);
  });

  it('W-3804: the send answers 500 and the item it serves after is the uncertain one; W-3807 answers 409 once and then serves Draft v2', async () => {
    expect((await step('W-3804', { expected_revision: 1, step: 'send_reminder', idempotency_key: key(6) })).status).toBe(500);
    expect((await getItem('W-3804')).state).toBe('effect_uncertain');
    expect((await step('W-3807', { expected_revision: 1, step: 'send_reminder', idempotency_key: key(7) })).status).toBe(409);
    expect((await getItem('W-3807')).workspace.version.label).toBe('Draft v2');
    expect((await step('W-3807', { expected_revision: 2, step: 'send_reminder', idempotency_key: key(8) })).status).toBe(200);
  });

  it('W-3808 offers no send step a press could take: its send carries the disabled reason; W-3809 has no steps', () => {
    const w8 = readJson(join(workDir, 'W-3808.json'));
    expect(w8.workspace.steps.find((s: { key: string }) => s.key === 'send_reminder').disabled_reason).toMatch(/no billing contact/);
    expect(readJson(join(workDir, 'W-3809.json')).workspace).not.toHaveProperty('steps');
  });
});
