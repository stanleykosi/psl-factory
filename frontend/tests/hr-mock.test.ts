/* eslint-disable @typescript-eslint/no-explicit-any -- parsed mock replies, checked in mock-contract.test.ts */
// F-55: the HR stand-in persona's sample data (work rows, items and history, alerts, Assistant, one line to start).
// Real mock server, over HTTP. Sample data only; no pay amount appears anywhere.
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

async function call(method: string, path: string, persona = 'hr', body?: unknown) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}` };
  if (method !== 'GET') headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as any };
}
const get = (path: string, persona = 'hr') => call('GET', path, persona);

const queue = async (name: string) => (await get(`/api/v1/work?queue=${name}&limit=50`)).body.items as any[];

describe('hr work rows', () => {
  it('shows rows in all three queues, with counts that match', async () => {
    const needs = await queue('needs_me');
    const waiting = await queue('waiting_on_others');
    const done = await queue('done');
    expect([needs.length >= 3, waiting.length >= 3, done.length >= 2]).toEqual([true, true, true]);
    expect((await get('/api/v1/work?queue=needs_me')).body.counts).toEqual({ needs_me: needs.length, waiting_on_others: waiting.length, done: done.length });
    expect([...needs, ...waiting, ...done].every((i) => i.sample === true)).toBe(true);
  });

  it('filters by line and searches', async () => {
    const byLine = (await get('/api/v1/work?queue=needs_me&line=hr_staff_records')).body.items;
    expect(byLine.map((i: any) => i.id)).toEqual(['W-4602']);
    expect((await get('/api/v1/work?queue=waiting_on_others&q=Adaeze')).body.items.map((i: any) => i.id)).toEqual(['W-4606']);
    expect((await get('/api/v1/work?queue=waiting_on_others&waiting_on=agent')).body.items.map((i: any) => i.id)).toEqual(['W-4607']);
  });

  it('leaves the other personas without any HR row', async () => {
    for (const persona of ['finance_lead', 'pm', 'pmo_lead', 'ceo']) {
      for (const name of ['needs_me', 'waiting_on_others', 'done']) {
        const ids = (await call('GET', `/api/v1/work?queue=${name}&limit=50`, persona)).body.items.map((i: any) => i.id);
        expect(ids.filter((id: string) => /^W-46/.test(id)), `${persona} ${name}`).toEqual([]);
      }
    }
  });

  it('gives every row an item page and a history with five or more entries, one of them Restricted', async () => {
    const rows = [...(await queue('needs_me')), ...(await queue('waiting_on_others')), ...(await queue('done'))];
    for (const row of rows) {
      const item = (await get(`/api/v1/work/${row.id}`)).body;
      expect(item.title, row.id).toBe(row.title);
      expect(item.reference, row.id).toBe(row.reference);
      expect(item.stations.length, row.id).toBeGreaterThan(2);
      expect(item.agent.name, row.id).toBe('Zainab');
      expect(item.next_step, row.id).toBeTruthy();
      const history = (await get(`/api/v1/work/${row.id}/history?limit=50`)).body.items as any[];
      expect(history.length, row.id).toBeGreaterThanOrEqual(5);
      expect(history.filter((h) => h.restricted).map((h) => h.event), row.id).toEqual(['Restricted']);
      expect(new Set(history.map((h) => h.actor_kind)), row.id).toContain('person');
      expect(new Set(history.map((h) => h.actor_kind)), row.id).toContain('agent');
    }
  });

  it('shows no pay amount in any HR fixture', () => {
    const dir = join(__dirname, '../mock/fixtures');
    const files = [
      ...readdirSync(join(dir, 'work')).filter((n) => /^W-46\d\d/.test(n)).map((n) => join(dir, 'work', n)),
      join(dir, 'alerts/notifications.hr.json'),
      join(dir, 'start-work/lines.hr.json'),
      ...readdirSync(join(dir, 'assistant')).filter((n) => /^CV-242\d\.json$/.test(n)).map((n) => join(dir, 'assistant', n)),
    ];
    expect(files.length).toBeGreaterThan(20);
    for (const file of files) {
      const text = readFileSync(file, 'utf8');
      expect(text, file).not.toMatch(/"money"|"amount"|₦|\bNGN\b|\bN\s?\d[\d,]{4,}/);
    }
  });
});

describe('hr alerts', () => {
  it('lists at least three alerts that open HR items', async () => {
    const list = (await get('/api/v1/notifications')).body;
    expect(list.items.length).toBeGreaterThanOrEqual(3);
    for (const alert of list.items) expect((await get(`/api/v1/work/${alert.work_id}`)).body.id).toBe(alert.work_id);
    expect(list.items.every((a: any) => /^W-46/.test(a.work_id) && a.agent === 'zainab')).toBe(true);
    expect(list.unread_count).toBe(3);
  });
});

describe('hr assistant', () => {
  it('lists four or more conversations with Zainab, each opening a full thread', async () => {
    const list = (await get('/api/v1/assistant/conversations')).body.items as any[];
    expect(list.length).toBeGreaterThanOrEqual(4);
    expect(list.every((c) => c.agent === 'zainab')).toBe(true);
    for (const c of list) {
      const thread = (await get(`/api/v1/assistant/conversations/${c.conversation_id}`)).body;
      expect(thread.messages.map((m: any) => m.role), c.conversation_id).toEqual(['person', 'agent']);
      expect(thread.messages[1].step_details.length, c.conversation_id).toBeGreaterThan(0);
      expect(thread.messages[1].source_details.length, c.conversation_id).toBeGreaterThan(0);
    }
  });

  it('has a draft card, and a salary question Zainab declines, saying payroll visibility is not set up', async () => {
    const draft = (await get('/api/v1/assistant/conversations/CV-2422')).body.messages[1];
    expect(draft.draft.rows.length).toBeGreaterThan(1);
    const salary = (await get('/api/v1/assistant/conversations/CV-2424')).body;
    expect(salary.status).toBe('cannot_answer');
    expect(salary.messages[1].cannot_reason).toBeTruthy();
    expect(salary.messages[1].text).toMatch(/has not been set up yet/);
  });

  it('answers a new message and keeps pay amounts out of the reply', async () => {
    const reply = await call('POST', '/api/v1/assistant/conversations/CV-2421/messages', 'hr', { text: 'Who left in October?' });
    expect(reply.status).toBe(200);
    const thread = (await get('/api/v1/assistant/conversations/CV-2421')).body;
    expect(thread.messages).toHaveLength(4);
    expect(thread.messages[3].text).toMatch(/do not show pay amounts/);
  });

  it('keeps other personas out of the HR conversations', async () => {
    expect((await get('/api/v1/assistant/conversations/CV-2421', 'pm')).status).toBe(404);
  });
});

describe('hr start work', () => {
  it('offers the stand-in line, marked as one, and starts it on a new work item', async () => {
    expect((await get('/api/v1/me')).body.startable_lines).toEqual(['hr_staff_list']);
    const lines = (await get('/api/v1/lines')).body;
    expect(lines.items.map((l: any) => l.key)).toEqual(['hr_staff_list']);
    const line = lines.items[0];
    expect(line.title).toBe('Send the staff list for payroll');
    expect(line.subtitle).toMatch(/Stand-in/);
    const upload = await call('POST', `/api/v1/cases/${line.case_id}/evidence`, 'hr', { kind: 'staff_list', filename: 'staff.xlsx', content_base64: 'AAEC', case_revision: line.case_revision });
    expect(upload.status).toBe(200);
    const started = await call('POST', '/api/v1/work', 'hr', {
      line: 'hr_staff_list', case_id: line.case_id, case_revision: upload.body.case_revision, idempotency_key: 'hr-1',
      intake: { month: '2026-11', proof: upload.body.evidence_id },
    });
    expect(started.status).toBe(201);
    expect(started.body.work_id).toBe('W-4611');
    expect((await get('/api/v1/work/W-4611')).body.line).toBe('Send the staff list for payroll');
  });

  it('refuses the line to every other persona', async () => {
    const body = { line: 'hr_staff_list', case_id: 'C-HR-STAFF', case_revision: 1, idempotency_key: 'x', intake: { month: '2026-11', proof: 'EV-1' } };
    for (const persona of ['finance_lead', 'pm', 'pmo_lead']) expect((await call('POST', '/api/v1/work', persona, body)).status, persona).toBe(403);
  });
});

describe('hr is still refused Exceptions', () => {
  it('answers 403 where it did before; Projects and Setup stay out of the destinations', async () => {
    expect((await get('/api/v1/exceptions')).status).toBe(403);
    expect((await get('/api/v1/me')).body.destinations).toEqual(['my_work', 'assistant']);
  });
});
