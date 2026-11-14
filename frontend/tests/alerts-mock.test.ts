import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

import type { AlertPrefs } from '@/features/alerts/types';
import { buildPrefsBody, draftFrom } from '@/features/alerts/model';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

const root = join(__dirname, '..');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
type Op = { operationId: string; requestBody?: { content: { 'application/json': { schema: object } } }; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
type Spec = { paths: Record<string, Record<string, Op>> };
const v7 = readJson(OPENAPI_PATH) as Spec;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const find = (spec: Spec, id: string) => Object.values(spec.paths).flatMap((ops) => Object.values(ops)).find((op) => op?.operationId === id)!;
const response = (spec: Spec, id: string) => find(spec, id).responses['200'].content['application/json'].schema;
function expectValid(schema: object, body: unknown, label: string) {
  const validate = ajv.compile(schema);
  expect(validate(body), `${label}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

describe('the alerts fixtures match the v7 contract', () => {
  const fixtures = join(root, 'mock/fixtures');
  const alertFiles = readdirSync(join(fixtures, 'alerts')).map((name) => `alerts/${name}`);

  it('every alerts fixture and the four default fixtures validate against the v7 200 schema', () => {
    expect(alertFiles.length).toBeGreaterThanOrEqual(9);
    for (const name of [...alertFiles, 'E-NOTIFICATIONS.json', 'E-ALERT-PREFS-READ.json']) {
      expectValid(response(v7, name.includes('notifications') || name.startsWith('E-NOTIFICATIONS') ? 'E-NOTIFICATIONS' : 'E-ALERT-PREFS-READ'), readJson(join(fixtures, name)), name);
    }
    expectValid(response(v7, 'E-NOTIFICATION-READ'), readJson(join(fixtures, 'E-NOTIFICATION-READ.json')), 'E-NOTIFICATION-READ');
    expectValid(response(v7, 'E-ALERT-PREFS'), readJson(join(fixtures, 'E-ALERT-PREFS.json')), 'E-ALERT-PREFS');
  });

  it('the PUT bodies the UI builds validate against the v7 request schema', () => {
    const putSchema = find(v7, 'E-ALERT-PREFS').requestBody!.content['application/json'].schema;
    for (const name of alertFiles.filter((n) => n.includes('prefs') && !n.includes('invalid'))) {
      const body = readJson(join(fixtures, name)) as AlertPrefs;
      for (const phone of [false, true]) expectValid(putSchema, buildPrefsBody(body, draftFrom(body), phone), `${name} PUT`);
    }
  });
});

let server: Server;
let origin: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${origin}/__mock/reset`, { method: 'POST' });
});

type Init = { persona?: string; scenario?: string; method?: string; body?: unknown; csrf?: string | null };
async function api(path: string, init: Init = {}) {
  const persona = init.persona ?? 'finance_lead';
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}${init.scenario ? `; psl_mock_alerts=${init.scenario}` : ''}` };
  const method = init.method ?? 'GET';
  if (method !== 'GET' && init.csrf !== null) headers['X-CSRFToken'] = init.csrf ?? `mock-csrf-${persona}`;
  if (init.body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(origin + path, { method, headers, body: init.body === undefined ? undefined : JSON.stringify(init.body) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> & { items: { id: string; read: boolean }[] } };
}
const ids = (body: { items: { id: string }[] }) => body.items.map((item) => item.id);
const prefsPut = (body: unknown, init: Init = {}) => api('/api/v1/me/alert-preferences', { ...init, method: 'PUT', body });
const boardBody = () => buildPrefsBody(readJson(join(root, 'mock/fixtures/E-ALERT-PREFS-READ.json')), draftFrom(readJson(join(root, 'mock/fixtures/E-ALERT-PREFS-READ.json'))), false);

describe('E-NOTIFICATIONS on the mock', () => {
  it('board: four rows in order, total 4, unread 1, dated today in Lagos', async () => {
    const { status, body } = await api('/api/v1/notifications');
    expect(status).toBe(200);
    expect(ids(body)).toEqual(['N-0001', 'N-0002', 'N-0003', 'N-0004']);
    expect([body.total, body.unread_count]).toEqual([4, 1]);
    const lagos = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos' });
    expect(lagos.format(new Date(body.as_of as string))).toBe(lagos.format(new Date()));
    expectValid(response(v7, 'E-NOTIFICATIONS'), body, 'board');
  });

  it('filters by q (text or reference), agent and unread; total is the filtered count, unread_count is all', async () => {
    expect(ids((await api('/api/v1/notifications?q=PAYROLL')).body)).toEqual(['N-0003']);
    expect(ids((await api('/api/v1/notifications?q=inv-lh')).body)).toEqual(['N-0001']);
    const chidi = (await api('/api/v1/notifications?agent=chidi')).body;
    expect([ids(chidi), chidi.total, chidi.unread_count]).toEqual([['N-0001', 'N-0004'], 2, 1]);
    expect(ids((await api('/api/v1/notifications?unread=true')).body)).toEqual(['N-0001']);
    expect(ids((await api('/api/v1/notifications?unread=false')).body)).toEqual(['N-0002', 'N-0003', 'N-0004']);
  });

  it('answers 404 invalid_query to a bad limit, cursor, empty q or unknown agent', async () => {
    for (const query of ['limit=7', 'cursor=nonsense', 'q=', 'agent=kemi']) {
      expect(await api(`/api/v1/notifications?${query}`), query).toEqual({ status: 404, body: { code: 'invalid_query', message: 'We could not read that list request.' } });
    }
  });

  it('many: 20, then 5 with no next cursor', async () => {
    const first = (await api('/api/v1/notifications', { scenario: 'many' })).body;
    expect([first.items.length, first.next_cursor, first.total]).toEqual([20, 'o20', 25]);
    const rest = (await api('/api/v1/notifications?cursor=o20', { scenario: 'many' })).body;
    expect(rest.items.length).toBe(5);
    expect(rest).not.toHaveProperty('next_cursor');
  });

  it('empty and bare', async () => {
    expect((await api('/api/v1/notifications', { scenario: 'empty' })).body).toMatchObject({ items: [], total: 0, unread_count: 0 });
    const bare = (await api('/api/v1/notifications?q=payroll', { scenario: 'bare' })).body;
    expect(ids(bare)).toEqual(['N-0001', 'N-0002', 'N-0003', 'N-0004']);
    expect(bare).not.toHaveProperty('total');
    expect(bare).not.toHaveProperty('unread_count');
    expectValid(response(v7, 'E-NOTIFICATIONS'), bare, 'bare (v7)');
    expect((await api('/api/v1/me/alert-preferences', { scenario: 'bare' })).status).toBe(404);
    expect((await api('/api/v1/notifications/N-0001/read', { scenario: 'bare', method: 'POST' })).status).toBe(404);
  });
});

describe('own records only (wrong user)', () => {
  it("pm's list never contains an id from finance_lead's list", async () => {
    const mine = ids((await api('/api/v1/notifications')).body);
    const theirs = ids((await api('/api/v1/notifications', { persona: 'pm' })).body);
    expect(theirs).toEqual(['N-0101', 'N-0102']);
    expect(theirs.filter((id) => mine.includes(id))).toEqual([]);
  });

  it("pm marking N-0002 answers 404 and finance_lead's N-0002 stays as it was", async () => {
    expect(await api('/api/v1/notifications/N-0001/read', { persona: 'pm', method: 'POST' })).toEqual({ status: 404, body: { code: 'not_found', message: 'We could not find that record.' } });
    expect((await api('/api/v1/notifications/N-0002/read', { persona: 'pm', method: 'POST' })).status).toBe(404);
    const list = (await api('/api/v1/notifications')).body;
    expect(list.items.map((i) => i.read)).toEqual([false, true, true, true]);
  });

  it("pm's preferences carry pm's masked number, never finance_lead's", async () => {
    const pm = (await api('/api/v1/me/alert-preferences', { persona: 'pm' })).body;
    expect(pm.whatsapp).toEqual({ masked_number: '+234 805 *** 1180', verified: true });
    expect(JSON.stringify(pm)).not.toContain('4412');
  });
});

describe('E-NOTIFICATION-READ on the mock', () => {
  it('marks the own alert read; a repeat answers the same 200', async () => {
    const first = await api('/api/v1/notifications/N-0001/read', { method: 'POST' });
    expect(first).toEqual({ status: 200, body: { id: 'N-0001', read: true, unread_count: 0 } });
    expectValid(response(v7, 'E-NOTIFICATION-READ'), first.body, 'read');
    expect(await api('/api/v1/notifications/N-0001/read', { method: 'POST' })).toEqual(first);
    expect((await api('/api/v1/notifications?unread=true')).body.items).toEqual([]);
  });
});

describe('CSRF on both writes', () => {
  const CSRF_FAILED = { status: 403, body: { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' } };
  it('a mark-read or PUT without X-CSRFToken, or with another persona token, answers 403 csrf_failed', async () => {
    expect(await api('/api/v1/notifications/N-0001/read', { method: 'POST', csrf: null })).toEqual(CSRF_FAILED);
    expect(await api('/api/v1/notifications/N-0101/read', { persona: 'pm', method: 'POST', csrf: 'mock-csrf-finance_lead' })).toEqual(CSRF_FAILED);
    expect(await prefsPut(boardBody(), { csrf: null })).toEqual(CSRF_FAILED);
    expect(await prefsPut(boardBody(), { persona: 'pm', csrf: 'mock-csrf-finance_lead' })).toEqual(CSRF_FAILED);
    expect((await api('/api/v1/notifications')).body.items[0].read).toBe(false);
  });
});

describe('E-ALERT-PREFS on the mock', () => {
  it('a save applies the sent fields and returns revision + 1; a stale revision then answers 409', async () => {
    const body = boardBody();
    body.events = body.events!.map((e) => (e.key === 'work_stuck' ? { ...e, email: false } : e));
    body.digest_at = '09:00';
    const saved = await prefsPut(body);
    expect(saved.status).toBe(200);
    expect(saved.body.revision).toBe(4);
    expect((saved.body.digest_at as { value: string }).value).toBe('09:00');
    expectValid(response(v7, 'E-ALERT-PREFS'), saved.body, 'saved');
    expect((await api('/api/v1/me/alert-preferences')).body).toEqual(saved.body);
    expect((await prefsPut(body)).status).toBe(409);
    expect((await prefsPut({ ...body, expected_revision: 4 })).body.revision).toBe(5);
  });

  it('without expected_revision (a v6 body) the save is accepted', async () => {
    expect((await prefsPut({ channel: 'email', frequency: 'daily' })).status).toBe(200);
  });

  it('422 names the field: schema, unknown event, option not offered', async () => {
    const msg = (fields: string) => ({ status: 422, body: { code: 'invalid', message: `Check these fields: ${fields}.` } });
    expect(await prefsPut({ ...boardBody(), channel: 'sms' })).toEqual(msg('channel'));
    expect(await prefsPut({ ...boardBody(), label: 'x' })).toEqual(msg('label'));
    expect(await prefsPut({ ...boardBody(), events: [{ key: 'nope', email: true }] })).toEqual(msg('events'));
    expect(await prefsPut({ ...boardBody(), digest_at: '10:00', quiet_hours: 'all' })).toEqual(msg('digest_at, quiet_hours'));
  });

  it('stale: the first PUT answers 409 and moves the record to revision 4 with "Work I started is stuck" email off', async () => {
    expect((await prefsPut(boardBody(), { scenario: 'stale' })).status).toBe(409);
    const now = (await api('/api/v1/me/alert-preferences', { scenario: 'stale' })).body as unknown as AlertPrefs;
    expect(now.revision).toBe(4);
    expect(now.events.find((e) => e.key === 'work_stuck')!.email).toBe(false);
    expect((await prefsPut({ ...boardBody(), expected_revision: 4 }, { scenario: 'stale' })).status).toBe(200);
  });

  it('invalid: GET returns channel "sms" and echoing it is a 422 on channel', async () => {
    const read = (await api('/api/v1/me/alert-preferences', { scenario: 'invalid' })).body as unknown as AlertPrefs;
    expect(read.channel).toBe('sms');
    expect((await prefsPut(buildPrefsBody(read, draftFrom(read), false), { scenario: 'invalid' })).body.message).toBe('Check these fields: channel.');
  });

  it('locked: the locked event goes back as read; a changed value is a 422 on events', async () => {
    const read = (await api('/api/v1/me/alert-preferences', { scenario: 'locked' })).body as unknown as AlertPrefs;
    expect(read.events.at(-1)).toMatchObject({ key: 'payroll_problems', locked_reason: 'Only HR can receive payroll alerts outside the app' });
    const body = buildPrefsBody(read, draftFrom(read), false);
    expect((await prefsPut(body, { scenario: 'locked' })).status).toBe(200);
    const changed = { ...body, expected_revision: 4, events: body.events!.map((e) => (e.key === 'payroll_problems' ? { ...e, email: true } : e)) };
    expect((await prefsPut(changed, { scenario: 'locked' })).body.message).toBe('Check these fields: events.');
  });

  it('phone: four events, the phone board wording', async () => {
    const read = (await api('/api/v1/me/alert-preferences', { scenario: 'phone' })).body as unknown as AlertPrefs;
    expect(read.events.map((e) => e.timing_label)).toEqual(['Straight away', 'Straight away', 'Straight away', 'Daily digest']);
    expect(read.quiet_hours!.options[0].label).toBe('20:00 to 07:00 and weekends');
  });
});
