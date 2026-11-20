/* eslint-disable @typescript-eslint/no-explicit-any -- parsed mock replies, checked in mock-contract.test.ts */
// D-150: the CEO's sample data (work rows, items and history, every project, overview, alerts, Assistant).
// Real mock server, over HTTP. Sample data only; no new authority rules, no pay amounts, unknown stays unknown.
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

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

async function call(method: string, path: string, persona = 'ceo', body?: unknown) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}` };
  if (method !== 'GET') headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as any };
}
const get = (path: string, persona = 'ceo') => call('GET', path, persona);
const queue = async (name: string, persona = 'ceo') => (await get(`/api/v1/work?queue=${name}&limit=50`, persona)).body.items as any[];

describe('ceo work rows', () => {
  it('has 5 decisions, 5 waiting and 4 done, with counts that match; unassigned is refused', async () => {
    const needs = await queue('needs_me');
    const waiting = await queue('waiting_on_others');
    const done = await queue('done');
    expect([needs.length, waiting.length, done.length]).toEqual([5, 5, 4]);
    expect((await get('/api/v1/work?queue=needs_me')).body.counts).toEqual({ needs_me: 5, waiting_on_others: 5, done: 4 });
    expect([...needs, ...waiting, ...done].every((i) => i.sample === true)).toBe(true);
    expect((await get('/api/v1/work?queue=unassigned')).status).toBe(403);
  });

  it('puts the CEO in the approval chain for every Needs me row: SOW, costing, emergency change, escalation, report', async () => {
    const needs = await queue('needs_me');
    expect(needs.map((i) => i.id)).toEqual(['W-5003', 'W-5004', 'W-5002', 'W-5005', 'W-5001']);
    expect(new Set(needs.map((i) => i.line_key))).toEqual(new Set(['planning', 'costing', 'emergency_change', 'escalation', 'leadership_report']));
    expect(needs.every((i) => i.waiting_on === 'CEO')).toBe(true);
    const sow = needs.find((i) => i.id === 'W-5001');
    expect([sow.title, sow.reference, sow.station]).toEqual(['Kora Logistics · SOW v3', 'PLN-0050', { index: 5, count: 6, name: 'CEO approval' }]);
  });

  it('filters by line and searches', async () => {
    expect((await get('/api/v1/work?queue=needs_me&line=escalation')).body.items.map((i: any) => i.id)).toEqual(['W-5004']);
    expect((await get('/api/v1/work?queue=waiting_on_others&waiting_on=agent')).body.items.map((i: any) => i.id)).toEqual(['W-5007', 'W-5010']);
    expect((await get('/api/v1/work?queue=done&q=Savanna')).body.items.map((i: any) => i.id)).toEqual(['W-5013']);
  });

  it('gives every row an item page and a history of five or more entries that the History tab filters can use', async () => {
    const rows = [...(await queue('needs_me')), ...(await queue('waiting_on_others')), ...(await queue('done'))];
    for (const row of rows) {
      const item = (await get(`/api/v1/work/${row.id}`)).body;
      expect([item.title, item.reference, item.line, item.state], row.id).toEqual([row.title, row.reference, row.line, row.state]);
      expect(item.stations.length, row.id).toBeGreaterThan(2);
      expect(item.next_step, row.id).toBeTruthy();
      const history = (await get(`/api/v1/work/${row.id}/history?limit=50`)).body.items as any[];
      expect(history.length, row.id).toBeGreaterThanOrEqual(5);
      const kinds = (k: string) => get(`/api/v1/work/${row.id}/history?kind=${k}&limit=50`);
      expect((await kinds('decisions')).body.items.length, row.id).toBeGreaterThan(0);
      expect((await kinds('agent_work')).body.items.length, row.id).toBeGreaterThan(0);
      expect(history.map((h) => h.at), row.id).toEqual([...history.map((h) => h.at)].sort().reverse());
    }
  });

  it('lets the CEO act on the SOW, costing and emergency change decisions, and shows an unknown cost as unknown', async () => {
    for (const id of ['W-5001', 'W-5002', 'W-5003']) {
      const task = (await get(`/api/v1/work/${id}`)).body.tasks[0];
      expect([task.kind, task.required_role, task.you_can_act], id).toEqual(['decide', 'CEO', true]);
      expect(task.decision.chain.steps[task.decision.chain.your_step - 1].is_you, id).toBe(true);
      expect(task.decision.chain.steps.filter((s: any) => s.status === 'approved').length, id).toBe(2);
    }
    expect((await get('/api/v1/work/W-5001')).body.tasks[0].decision.amount).toEqual({ amount: '42500000.00', currency: 'NGN', unknown: false });
    expect((await get('/api/v1/work/W-5003')).body.tasks[0].decision.amount).toEqual({ currency: 'NGN', unknown: true });
  });

  it('waits behind the PMO Lead on the Ojo Foods plan: the CEO is the next step and cannot act yet', async () => {
    const task = (await get('/api/v1/work/W-5006')).body.tasks[0];
    expect([task.you_can_act, task.cannot_act_reason]).toEqual([false, 'not_your_turn']);
    expect(task.decision.chain.steps.map((s: any) => [s.role, s.status])).toEqual([['PM', 'approved'], ['PMO Lead', 'current'], ['CEO', 'not_yet']]);
  });

  it('records no payment exception as a CEO decision, and no pay amount in any CEO fixture', async () => {
    const all = [...(await queue('needs_me')), ...(await queue('waiting_on_others')), ...(await queue('done'))];
    expect(all.filter((i) => i.line_key === 'payment_exception')).toEqual([]);
    const dir = join(__dirname, '../mock/fixtures');
    const files = [
      ...readdirSync(join(dir, 'work')).filter((n) => /^W-50\d\d/.test(n)).map((n) => join(dir, 'work', n)),
      join(dir, 'alerts/notifications.ceo.json'),
      ...readdirSync(join(dir, 'assistant')).filter((n) => /^CV-244\d\.json$/.test(n)).map((n) => join(dir, 'assistant', n)),
    ];
    expect(files.length).toBe(14 * 2 + 1 + 5);
    for (const file of files) {
      const text = readFileSync(file, 'utf8');
      expect(text, file).not.toMatch(/salary|\bN\s?\d[\d,]{4,}|₦/);
      if (/work\/W-50\d\d\.json$/.test(file)) expect(text, file).not.toMatch(/"amount": "0(\.00)?"|[Pp]ayment exception/);
    }
  });

  it('leaves the other personas without any CEO row, and gives them the same item as before for shared ids', async () => {
    for (const persona of ['finance_lead', 'pm', 'pmo_lead', 'hr', 'hr_lead']) {
      for (const name of ['needs_me', 'waiting_on_others', 'done']) {
        const ids = (await queue(name, persona)).map((i) => i.id);
        expect(ids.filter((id: string) => /^W-50/.test(id)), `${persona} ${name}`).toEqual([]);
      }
    }
    expect((await get('/api/v1/work?queue=waiting_on_others', 'pm')).body.items.map((i: any) => i.id)).toEqual(expect.arrayContaining(['W-1302']));
  });
});

describe('ceo projects', () => {
  it('sees every project the Finance Lead sees, and the Finance Lead still sees them', async () => {
    const mine = (await get('/api/v1/projects?status=all&limit=50')).body;
    const lead = (await get('/api/v1/projects?status=all&limit=50', 'finance_lead')).body;
    expect(mine.items.map((i: any) => i.case_id)).toEqual(lead.items.map((i: any) => i.case_id));
    expect(mine.counts).toEqual({ active: 22, closed: 2, all: 24 });
    expect((await get('/api/v1/projects?limit=50')).body.items).toHaveLength(22);
  });

  it('opens a project, its tabs and its money tab; the no-access id stays 404; hr is unchanged and pmo_lead sees projects (D-153)', async () => {
    expect((await get('/api/v1/projects/P-0103')).body.case_id).toBe('P-0103');
    expect((await get('/api/v1/projects/P-0103/milestones')).status).toBe(403); // P-0103 answers 403 on every tab, as before
    expect((await get('/api/v1/projects/P-0101/milestones')).status).toBe(200);
    expect((await get('/api/v1/projects/P-0101/money')).status).toBe(200);
    expect((await get('/api/v1/projects/P-0099')).status).toBe(404);
    expect((await get('/api/v1/projects/P-0101', 'hr')).status).toBe(404);
    expect((await get('/api/v1/projects/P-0101', 'pmo_lead')).status).toBe(200);
  });
});

describe('ceo overview', () => {
  it('is populated: totals, lines with stations, and a note on each line', async () => {
    const overview = (await get('/api/v1/overview')).body;
    expect(Object.values(overview.totals).every((n) => typeof n === 'number')).toBe(true);
    expect(overview.totals.in_progress).toBeGreaterThan(0);
    expect(overview.lines.length).toBeGreaterThanOrEqual(4);
    for (const line of overview.lines) expect(line.stations.length, line.line).toBeGreaterThan(0);
  });
});

describe('ceo alerts', () => {
  it('lists four or more alerts that open the CEO’s items, with the unread count', async () => {
    const list = (await get('/api/v1/notifications')).body;
    expect(list.items.length).toBeGreaterThanOrEqual(4);
    for (const alert of list.items) {
      expect(alert.agent).toBe('tola');
      expect((await get(`/api/v1/work/${alert.work_id}`)).body.id).toBe(alert.work_id);
    }
    expect(list.items.map((a: any) => a.work_id)).toEqual(expect.arrayContaining(['W-5001', 'W-5003', 'W-5004', 'W-5005']));
    expect(list.unread_count).toBe(list.items.filter((a: any) => !a.read).length);
    expect(list.unread_count).toBeGreaterThanOrEqual(4);
  });

  it('marks one read, and the other personas keep their own alerts', async () => {
    expect((await call('POST', '/api/v1/notifications/N-0401/read', 'ceo', {})).status).toBe(200);
    const list = (await get('/api/v1/notifications')).body;
    expect(list.items.find((a: any) => a.id === 'N-0401').read).toBe(true);
    expect((await get('/api/v1/notifications', 'pmo_lead')).body.items.map((a: any) => a.id)).toEqual(['N-0201']);
  });
});

describe('ceo assistant', () => {
  it('lists five conversations across Tola, Chidi and Zainab, each opening a full thread', async () => {
    const list = (await get('/api/v1/assistant/conversations')).body.items as any[];
    expect(list).toHaveLength(5);
    expect(new Set(list.map((c) => c.agent))).toEqual(new Set(['tola', 'chidi', 'zainab']));
    for (const c of list) {
      const thread = (await get(`/api/v1/assistant/conversations/${c.conversation_id}`)).body;
      expect(thread.messages.map((m: any) => m.role), c.conversation_id).toEqual(['person', 'agent']);
      expect(thread.messages[1].step_details.length, c.conversation_id).toBeGreaterThan(0);
      expect(thread.messages[1].source_details.length, c.conversation_id).toBeGreaterThan(0);
    }
  });

  it('answers a SOW question from the records, linked to the item; Zainab declines pay', async () => {
    const sow = (await get('/api/v1/assistant/conversations/CV-2442')).body;
    expect(sow.messages[1].source_details[0].link).toEqual({ work_id: 'W-5001' });
    expect(sow.messages[1].text).toMatch(/unknown/);
    const pay = (await get('/api/v1/assistant/conversations/CV-2444')).body;
    expect([pay.status, pay.agent]).toEqual(['cannot_answer', 'zainab']);
    expect(pay.messages[1].text).toMatch(/has not been set up yet/);
  });

  it('answers a new message, shows no pay amount, and keeps the thread private to the CEO', async () => {
    const reply = await call('POST', '/api/v1/assistant/conversations/CV-2441/messages', 'ceo', { text: 'And what is waiting on others?' });
    expect(reply.status).toBe(200);
    const thread = (await get('/api/v1/assistant/conversations/CV-2441')).body;
    expect(thread.messages).toHaveLength(4);
    expect(thread.messages[3].text).toMatch(/what waits for your decision/);
    expect(thread.messages[3].text).not.toMatch(/₦|NGN/);
    expect((await get('/api/v1/assistant/conversations/CV-2441', 'pm')).status).toBe(404);
    expect((await get('/api/v1/assistant/conversations', 'pm')).body.items.map((c: any) => c.conversation_id)).not.toContain('CV-2441');
  });
});
