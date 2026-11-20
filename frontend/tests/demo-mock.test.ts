/* eslint-disable @typescript-eslint/no-explicit-any -- parsed mock replies, checked against the v7 schemas */
// D-155: the live demo of the mock: the answer delay, the speed cookie, the assistant's run, and the line runs (step clock,
// human hand-off, Return, Reject, History). The clock is faked (Date only), so a run advances by the time that "passes".
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { delayMs, demoOn, speedOf } from '../mock/demo.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createLineRuns, LINE_STEP_MS } from '../mock/line-runs.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, PERSONAS, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { WORK_IDS } from '../mock/start-work.mjs';
// @ts-expect-error plain ESM module without type declarations
import { DEMO_STEP_MS } from '../mock/assistant.mjs';

type Op = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const op = (id: string) => Object.values(openapi.paths).flatMap((m) => Object.values(m)).find((o) => o?.operationId === id)!;
const check = (id: string, status: number, body: unknown) => {
  const validate = ajv.compile(op(id).responses[String(status)].content['application/json'].schema);
  expect(validate(body), `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
};

const fixtures = join(__dirname, '..', 'mock', 'fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(join(fixtures, path), 'utf8'));

describe('demo switches and the answer delay', () => {
  const fixed = (value: number) => () => value;
  it('is off, fast and without delay unless the demo is on', () => {
    expect(demoOn({}, {})).toBe(false);
    expect(speedOf({}, {})).toBe('fast');
    expect(delayMs('get', {}, { env: {}, random: fixed(1) })).toBe(0);
    expect(delayMs('post', { psl_mock_demo: 'off', psl_mock_speed: 'fast' }, { env: { MOCK_DEMO: '1' }, random: fixed(1) })).toBe(0);
  });

  it('waits 0.3-1.2 s to read and 0.8-2 s to write at Normal, and 2.5 times that at Slow', () => {
    const env = { MOCK_DEMO: '1' };
    expect(speedOf({}, env)).toBe('normal');
    expect([delayMs('get', {}, { env, random: fixed(0) }), delayMs('get', {}, { env, random: fixed(1) })]).toEqual([300, 1200]);
    expect([delayMs('post', {}, { env, random: fixed(0) }), delayMs('put', {}, { env, random: fixed(1) })]).toEqual([800, 2000]);
    expect(delayMs('get', { psl_mock_speed: 'slow' }, { env, random: fixed(0) })).toBe(750);
    expect(delayMs('get', { psl_mock_speed: 'fast' }, { env, random: fixed(1) })).toBe(0);
    expect(demoOn({ psl_mock_demo: 'on' }, {})).toBe(true);
  });
});

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${base}/__mock/reset`, { method: 'POST' });
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-20T09:00:00Z'));
});
afterEach(() => vi.useRealTimers());

async function call(method: string, path: string, persona: string, body?: unknown, cookie = 'psl_mock_demo=on; psl_mock_speed=fast') {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}; ${cookie}` };
  if (method !== 'GET') headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as any };
}
const get = (path: string, persona: string) => call('GET', path, persona);
const pass = (ms: number) => vi.setSystemTime(Date.now() + ms);

describe('the answer delay on the server', () => {
  it('holds a read back at Normal and not at Fast', async () => {
    vi.useRealTimers();
    const started = performance.now();
    await call('GET', '/api/v1/me', 'pm', undefined, 'psl_mock_demo=on; psl_mock_speed=normal');
    expect(performance.now() - started).toBeGreaterThanOrEqual(280);
    const quick = performance.now();
    await call('GET', '/api/v1/me', 'pm');
    expect(performance.now() - quick).toBeLessThan(250);
  });
});

describe('assistant run in the demo', () => {
  it('shows one more step each interval, then the answer, sources and a result card', async () => {
    const made = await call('POST', '/api/v1/assistant/conversations', 'pm', { agent: 'tola' });
    const id = made.body.conversation_id;
    const sent = await call('POST', `/api/v1/assistant/conversations/${id}/messages`, 'pm', { text: 'How are my projects?' });
    expect(sent.body.status).toBe('working');
    const states: string[][] = [];
    for (let i = 0; i < 4; i += 1) {
      const read = await get(`/api/v1/assistant/conversations/${id}`, 'pm');
      check('E-CONVERSATION', 200, read.body);
      const last = read.body.messages.at(-1);
      states.push([read.body.status, ...last.step_details.map((s: any) => s.state)]);
      if (i === 3) {
        expect(last.text).toContain('Tola');
        expect(last.sources.length).toBeGreaterThan(0);
        expect(last.draft.rows.length).toBeGreaterThan(0);
      }
      pass(DEMO_STEP_MS);
    }
    expect(states).toEqual([
      ['working', 'now', 'next', 'next'],
      ['working', 'done', 'now', 'next'],
      ['working', 'done', 'done', 'now'],
      ['answered', 'done', 'done', 'done'],
    ]);
    const list = await get('/api/v1/assistant/conversations', 'pm');
    expect(list.body.items[0]).toMatchObject({ conversation_id: id, status: 'answered' });
  });

  it('keeps the old read-driven script when the demo is off', async () => {
    const made = await call('POST', '/api/v1/assistant/conversations', 'pm', { agent: 'tola' }, 'psl_mock_demo=off');
    const sent = await call('POST', `/api/v1/assistant/conversations/${made.body.conversation_id}/messages`, 'pm', { text: 'Hello' }, 'psl_mock_demo=off');
    expect(sent.body.status).toBe('answered');
  });
});

/** A valid start of the weekly report as the PM (a project line with no proof). */
async function startWeekly(key = 'demo-1', persona = 'pm') {
  const options = (await get('/api/v1/lines/weekly_report/fields/project/options', persona)).body.items[0];
  return call('POST', '/api/v1/work', persona, {
    line: 'weekly_report', case_id: options.case_id, case_revision: options.case_revision, idempotency_key: key,
    intake: { project: options.value, week: { from: '2026-11-09', to: '2026-11-13' } },
  });
}
const decide = (taskId: string, revision: number, verdict: string, note?: string, persona = 'pmo_lead') =>
  call('POST', `/api/v1/tasks/${taskId}/decision`, persona, { expected_revision: revision, verdict, ...(note ? { note } : {}) });

describe('a line run in the demo (weekly report: PM starts, PMO Lead decides)', () => {
  it('ticks the agent steps, waits at the human station, and ends verified with a history entry for every step', async () => {
    const started = await startWeekly();
    expect(started.status).toBe(201);
    const id = started.body.work_id;
    expect(id).toMatch(/^W-9\d{3}$/);
    expect((await startWeekly()).body.work_id).toBe(id);

    let item = (await get(`/api/v1/work/${id}`, 'pm')).body;
    check('E-WORK-ITEM', 200, item);
    expect([item.state, item.agent.status, item.agent.steps.map((s: any) => s.status)]).toEqual(['processing', 'working', ['working']]);
    pass(LINE_STEP_MS);
    item = (await get(`/api/v1/work/${id}`, 'pm')).body;
    expect(item.agent.steps.map((s: any) => s.status)).toEqual(['done', 'working']);
    expect((await get('/api/v1/work?queue=waiting_on_others', 'pm')).body.items.map((i: any) => i.id)).toContain(id);
    expect((await get('/api/v1/work?queue=needs_me', 'pmo_lead')).body.items.map((i: any) => i.id)).not.toContain(id);

    // two agent stations (Collect records, Draft report) of three steps each, then PM review is the human one
    pass(LINE_STEP_MS * 6);
    item = (await get(`/api/v1/work/${id}`, 'pmo_lead')).body;
    check('E-WORK-ITEM', 200, item);
    expect([item.state, item.stations.map((s: any) => s.status)]).toEqual(['waiting', ['done', 'done', 'current_person', 'not_started', 'not_started']]);
    expect(item.tasks).toHaveLength(1);
    expect(item.tasks[0]).toMatchObject({ you_can_act: true, required_role: 'PMO Lead' });
    expect((await get(`/api/v1/work/${id}`, 'pm')).body.tasks[0].you_can_act).toBe(false);
    const needs = await get('/api/v1/work?queue=needs_me', 'pmo_lead');
    check('E-WORK-LIST', 200, needs.body);
    expect(needs.body.items.find((i: any) => i.id === id)).toMatchObject({ kind: 'decide', waiting_on: 'PMO Lead' });
    expect(needs.body.counts.needs_me).toBe(needs.body.items.length);
    expect((await get('/api/v1/work?queue=waiting_on_others', 'pm')).body.items.find((i: any) => i.id === id)).toMatchObject({ waiting_on: 'PMO Lead' });
    const alerts = await get('/api/v1/notifications', 'pmo_lead');
    check('E-NOTIFICATIONS', 200, alerts.body);
    expect(alerts.body.items[0]).toMatchObject({ work_id: id, read: false });

    const task = item.tasks[0];
    expect((await call('POST', `/api/v1/tasks/${task.id}/claim`, 'pmo_lead', { expected_revision: task.revision })).status).toBe(200);
    const approved = await decide(task.id, task.revision, 'approve');
    expect(approved.status).toBe(200);
    check('E-TASK-DECIDE', 200, approved.body);
    // a second reviewer on the old copy: 409, and the stale task offers no decision
    expect((await decide(task.id, task.revision, 'approve')).status).toBe(409);

    pass(LINE_STEP_MS * 9);
    item = (await get(`/api/v1/work/${id}`, 'pm')).body;
    check('E-WORK-ITEM', 200, item);
    expect([item.state, item.stations.map((s: any) => s.status)]).toEqual(['verified', ['done', 'done', 'done', 'done', 'verified']]);
    expect((await get('/api/v1/work?queue=done', 'pm')).body.items.map((i: any) => i.id)).toContain(id);
    expect((await get('/api/v1/work?queue=done', 'pmo_lead')).body.items.map((i: any) => i.id)).toContain(id);
    expect((await get('/api/v1/notifications', 'pm')).body.items[0]).toMatchObject({ work_id: id });

    const history = (await get(`/api/v1/work/${id}/history?limit=50`, 'pm')).body;
    check('E-WORK-HISTORY', 200, history);
    const events = history.items.map((e: any) => e.event);
    expect(events[0]).toBe('Verified');
    expect(events).toContain('Approved “PM review”');
    for (const station of ['Collect records', 'Draft report', 'Deliver', 'Verify']) expect(events.some((e: string) => e.includes(`“${station}”`)), station).toBe(true);
    expect(history.items.filter((e: any) => e.actor_kind === 'agent')).toHaveLength(12);
    expect((await get(`/api/v1/work/${id}/history?kind=decisions`, 'pm')).body.items.map((e: any) => e.event)).toEqual(['Approved “PM review”']);
  });

  it('sends the item back for rework on Return, and stops it on Reject', async () => {
    const id = (await startWeekly()).body.work_id;
    pass(LINE_STEP_MS * 6);
    let task = (await get(`/api/v1/work/${id}`, 'pmo_lead')).body.tasks[0];
    expect((await decide(task.id, task.revision, 'return')).status).toBe(422);
    const returned = await decide(task.id, task.revision, 'return', 'Add the milestone dates');
    expect(returned.body.work_state).toBe('processing');
    let item = (await get(`/api/v1/work/${id}`, 'pm')).body;
    expect([item.state, item.stations.map((s: any) => s.status)]).toEqual(['processing', ['done', 'current_agent', 'not_started', 'not_started', 'not_started']]);
    expect(item.tasks).toEqual([]);
    expect(item.agent.steps[0].text).toContain('note that came back');
    expect((await get('/api/v1/work?queue=needs_me', 'pmo_lead')).body.items.map((i: any) => i.id)).not.toContain(id);

    pass(LINE_STEP_MS * 3);
    item = (await get(`/api/v1/work/${id}`, 'pmo_lead')).body;
    expect(item.state).toBe('waiting');
    expect(item.tasks[0]).toMatchObject({ you_can_act: true });
    expect(item.tasks[0].id).not.toBe(task.id);
    expect(item.tasks[0].decision.version.label).toBe('Draft v2');
    expect((await get('/api/v1/work?queue=needs_me', 'pmo_lead')).body.items.map((i: any) => i.id)).toContain(id);
    const history = (await get(`/api/v1/work/${id}/history?limit=50`, 'pm')).body.items;
    expect(history.find((e: any) => e.event === 'Returned “PM review”')).toMatchObject({ detail: 'Note: “Add the milestone dates”', version: 'v1' });

    task = item.tasks[0];
    const rejected = await decide(task.id, task.revision, 'reject', 'Not needed');
    expect(rejected.body.work_state).toBe('cancelled');
    item = (await get(`/api/v1/work/${id}`, 'pm')).body;
    expect([item.state, item.stations[2].status]).toEqual(['cancelled', 'stopped']);
    expect((await get('/api/v1/work?queue=done', 'pm')).body.items.find((i: any) => i.id === id)?.state).toBe('cancelled');
  });

  it('leaves everything as it was with the demo off, and Reset demo clears the runs', async () => {
    const options = (await get('/api/v1/lines/weekly_report/fields/project/options', 'pm')).body.items[0];
    const start = (cookie: string, key: string) => call('POST', '/api/v1/work', 'pm', {
      line: 'weekly_report', case_id: options.case_id, case_revision: options.case_revision, idempotency_key: key,
      intake: { project: options.value, week: { from: '2026-11-09', to: '2026-11-13' } },
    }, cookie);
    expect((await start('psl_mock_demo=off', 'off-1')).body.work_id).toBe('W-1402');
    const id = (await start('psl_mock_demo=on', 'on-1')).body.work_id;
    expect(id).toBe('W-9001');
    expect((await get(`/api/v1/work/${id}`, 'pm')).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await get(`/api/v1/work/${id}`, 'pm')).body.id).not.toBe(id);
  });
});

describe('every startable line in the demo', () => {
  const lineKeys = [...new Set(readdirSync(join(fixtures, 'start-work')).filter((n) => /^lines\./.test(n)).flatMap((n) => readJson(`start-work/${n}`).items.map((l: any) => l.key)))] as string[];
  const me = Object.fromEntries((PERSONAS as string[]).map((p) => [p, readJson(`me.${p}.json`)]));
  const work = Object.fromEntries(Object.values(WORK_IDS as Record<string, string>).map((id) => [id, readJson(`work/${id}.json`)]));

  it('covers the whole fixture table, stand-ins included', () => {
    expect(lineKeys.sort()).toEqual(Object.keys(WORK_IDS).sort());
    expect(lineKeys).toContain('hr_staff_list');
  });

  for (const lineKey of Object.keys(WORK_IDS)) {
    it(`${lineKey} runs through its own stations to verified`, () => {
      let now = 0;
      const raised: [string, any][] = [];
      const runs = createLineRuns({ now: () => now, work, me, raise: (persona: string, alert: any) => raised.push([persona, alert]) });
      const starter = (PERSONAS as string[]).find((p) => me[p].startable_lines.includes(lineKey))!;
      const run = runs.start({ key: 'k', lineKey, persona: starter });
      const stations = work[WORK_IDS[lineKey]].stations.map((s: any) => s.name);
      expect(runs.item(run.id, starter).stations.map((s: any) => s.name)).toEqual(stations);

      now += 60 * 60 * 1000;
      const waiting = runs.item(run.id, starter);
      check('E-WORK-ITEM', 200, waiting);
      expect(waiting.state).toBe('waiting');
      const decider = runs.rows(starter).length === 1 ? raised[0][0] : '';
      expect(raised).toHaveLength(1);
      expect(decider).not.toBe(starter);
      const open = runs.item(run.id, decider);
      expect(open.tasks[0].you_can_act).toBe(true);
      expect(runs.rows(decider)[0]).toMatchObject({ queue: 'needs_me' });
      expect(runs.rows(starter)[0]).toMatchObject({ queue: 'waiting_on_others' });

      runs.decide(open.tasks[0].id, 'approve', undefined, decider);
      now += 60 * 60 * 1000;
      const done = runs.item(run.id, starter);
      check('E-WORK-ITEM', 200, done);
      expect(done.state).toBe('verified');
      expect(runs.rows(starter)[0]).toMatchObject({ queue: 'done' });
      const history = runs.history(run.id);
      check('E-WORK-HISTORY', 200, { items: history.items.map((entry: any) => Object.fromEntries(Object.entries(entry).filter(([key]) => key !== '_kind'))), as_of: history.as_of });
      // every agent station's three steps, the start, the wait, the decision and the verification
      expect(history.items).toHaveLength((stations.length - 1) * 3 + 4);
      expect(raised.map(([persona]) => persona)).toEqual([decider, starter]);
    });
  }
});
