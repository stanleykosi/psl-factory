/* eslint-disable @typescript-eslint/no-explicit-any -- parsed mock replies, checked against the v7 schemas */
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { ASSISTANT_OPERATIONS } from '../mock/assistant.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// F-24: the assistant in the contract mock. Every reply is checked against its v7 schema here again, so a fixture that
// drifts from the contract fails this suite and not only the mock's own check.
type Op = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const op = (id: string) => Object.values(openapi.paths).flatMap((m) => Object.values(m)).find((o) => o?.operationId === id)!;
const check = (id: string, status: number, body: unknown) => {
  const schema = op(id).responses[String(status)]?.content['application/json'].schema;
  expect(schema, `${id} declares ${status}`).toBeTruthy();
  const validate = ajv.compile(schema!);
  expect(validate(body), `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
};

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

type Reply = { status: number; body: any };
async function call(method: string, path: string, init: { persona?: string; body?: unknown; csrf?: string | null } = {}): Promise<Reply> {
  const persona = init.persona ?? 'pm';
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}` };
  if (method !== 'GET' && init.csrf !== null) headers['X-CSRFToken'] = init.csrf ?? `mock-csrf-${persona}`;
  if (init.body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(base + path, { method, headers, body: init.body === undefined ? undefined : JSON.stringify(init.body) });
  return { status: response.status, body: await response.json() };
}
const get = (path: string, persona?: string) => call('GET', path, { persona });
const conversation = (id: string, persona?: string) => get(`/api/v1/assistant/conversations/${id}`, persona);
const log = async () => ((await (await fetch(`${base}/__mock/assistant-log`)).json()) as { entries: any[] }).entries;

describe('fixtures', () => {
  const dir = join(__dirname, '../mock/fixtures/assistant');
  const ids = readdirSync(dir).filter((n) => /^CV-\d+\.json$/.test(n)).map((n) => n.slice(0, -5));

  it('there are the eight board conversations, minus the reserved no-access id', () => {
    expect(ids).toEqual(['CV-2401', 'CV-2402', 'CV-2403', 'CV-2404', 'CV-2405', 'CV-2406', 'CV-2411', 'CV-2421', 'CV-2422', 'CV-2423', 'CV-2424', 'CV-2425']);
  });

  for (const id of ids) {
    it(`${id} validates against the v7 E-CONVERSATION schema as written (nothing stripped)`, () => {
      check('E-CONVERSATION', 200, JSON.parse(readFileSync(join(dir, `${id}.json`), 'utf8')));
    });
  }

  it('the list index and mentions carry only the mock’s own underscore keys beyond the schema, never served', async () => {
    for (const persona of ['pm', 'finance_lead', 'ceo']) {
      const page = await get('/api/v1/assistant/conversations', persona);
      expect(page.status).toBe(200);
      check('E-CONVERSATIONS', 200, page.body);
      expect(JSON.stringify(page.body)).not.toContain('_persona');
    }
    const found = await get('/api/v1/assistant/mentions?q=harm');
    check('E-MENTION-OPTIONS', 200, found.body);
    expect(JSON.stringify(found.body)).not.toContain('_personas');
  });
});

describe('E-CONVERSATIONS and E-CONVERSATION', () => {
  it('each persona is served its own list: pm five, finance_lead one, ceo none', async () => {
    const pm = (await get('/api/v1/assistant/conversations')).body;
    expect(pm.items.map((r: any) => [r.conversation_id, r.status_line])).toEqual([
      ['CV-2401', 'Drafted · ready to start'],
      ['CV-2402', 'Drafted · 3 open questions'],
      ['CV-2403', 'Answered'],
      ['CV-2404', 'Can’t share'],
      ['CV-2405', 'Working · step 3 of 5'],
    ]);
    expect((await get('/api/v1/assistant/conversations', 'finance_lead')).body.items.map((r: any) => r.conversation_id)).toEqual(['CV-2411']);
    expect((await get('/api/v1/assistant/conversations', 'ceo')).body.items).toEqual([]);
  });

  it('pages by limit and cursor', async () => {
    const first = (await get('/api/v1/assistant/conversations?limit=10')).body;
    expect(first.next_cursor).toBeUndefined();
    const sheet = (await get('/api/v1/assistant/conversations?limit=10&cursor=o:2')).body;
    expect(sheet.items).toHaveLength(3);
  });

  it("another persona's conversation, an unknown id and the reserved CV-2499 are 404 with nothing of the conversation", async () => {
    for (const [id, persona] of [['CV-2401', 'finance_lead'], ['CV-2411', 'pm'], ['CV-9999', 'pm'], ['CV-2499', 'pm'], ['CV-2499', 'finance_lead']] as const) {
      const reply = await conversation(id, persona);
      expect(reply.status, `${id} as ${persona}`).toBe(404);
      check('E-CONVERSATION', 404, reply.body);
      expect(JSON.stringify(reply.body)).not.toMatch(/Invoice|Chidi|Harmattan/);
    }
  });

  it('CV-2406 is reachable by URL for pm and not in the list', async () => {
    expect((await conversation('CV-2406')).status).toBe(200);
    expect((await get('/api/v1/assistant/conversations')).body.items.map((r: any) => r.conversation_id)).not.toContain('CV-2406');
  });
});

describe('a working conversation advances on reads and ends', () => {
  it('CV-2405: step 3, then 4, then 5, then the labelled sample answer; the list follows; reset restores it', async () => {
    const stepOf = (c: any) => c.messages[1].step_details.findIndex((s: any) => s.state === 'now') + 1;
    const first = (await conversation('CV-2405')).body;
    check('E-CONVERSATION', 200, first);
    expect([first.status, stepOf(first)]).toEqual(['working', 3]);
    expect(stepOf((await conversation('CV-2405')).body)).toBe(4);
    const third = (await conversation('CV-2405')).body;
    expect(stepOf(third)).toBe(5);
    expect((await get('/api/v1/assistant/conversations')).body.items.find((r: any) => r.conversation_id === 'CV-2405').status_line).toBe('Working · step 5 of 5');
    const last = (await conversation('CV-2405')).body;
    check('E-CONVERSATION', 200, last);
    expect(last.status).toBe('answered');
    expect(last.messages[1].text).toBe('Sample answer from the contract mock. No agent ran.');
    expect(last.messages[1].step_details.every((s: any) => s.state === 'done')).toBe(true);
    expect((await conversation('CV-2405')).body.status).toBe('answered');
    expect((await get('/api/v1/assistant/conversations')).body.items.find((r: any) => r.conversation_id === 'CV-2405').status_line).toBe('Answered');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(stepOf((await conversation('CV-2405')).body)).toBe(3);
  });
});

describe('E-CONVERSATION-NEW and E-MESSAGE', () => {
  it('a new conversation for an allowed agent, then a message answered with labelled sample text; both are logged', async () => {
    const made = await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola' } });
    expect(made.status).toBe(200);
    check('E-CONVERSATION-NEW', 200, made.body);
    expect(made.body).toEqual({ conversation_id: 'CV-N1' });
    const sent = await call('POST', '/api/v1/assistant/conversations/CV-N1/messages', { body: { text: 'Plan the Kora phase', mentions: [{ kind: 'project', id: 'P-0102' }] } });
    check('E-MESSAGE', 200, sent.body);
    expect(sent.body.status).toBe('answered');
    const read = (await conversation('CV-N1')).body;
    check('E-CONVERSATION', 200, read);
    expect(read.messages.map((m: any) => [m.role, m.text])).toEqual([['person', 'Plan the Kora phase'], ['agent', 'Sample answer from the contract mock. No agent ran.']]);
    expect(read.messages[1].step_details).toHaveLength(1);
    expect(read.messages[1].sources).toEqual([]);
    const list = (await get('/api/v1/assistant/conversations')).body;
    check('E-CONVERSATIONS', 200, list);
    expect(list.items[0]).toMatchObject({ conversation_id: 'CV-N1', title: 'Plan the Kora phase', agent: 'tola' });
    expect((await log()).map((e) => [e.operation, e.conversation_id, e.text, e.status])).toEqual([
      ['E-CONVERSATION-NEW', 'CV-N1', undefined, 200],
      ['E-MESSAGE', 'CV-N1', 'Plan the Kora phase', 200],
    ]);
  });

  it('403 for an agent not in the persona’s list; 404 for another persona’s conversation', async () => {
    const refused = await call('POST', '/api/v1/assistant/conversations', { persona: 'finance_lead', body: { agent: 'tola' } });
    expect(refused.status).toBe(403);
    check('E-CONVERSATION-NEW', 403, refused.body);
    await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola' } });
    const stranger = await call('POST', '/api/v1/assistant/conversations/CV-N1/messages', { persona: 'ceo', body: { text: 'hi' } });
    expect(stranger.status).toBe(404);
    expect((await call('POST', '/api/v1/assistant/conversations/CV-2401/messages', { persona: 'finance_lead', body: { text: 'hi' } })).status).toBe(404);
  });

  it('a bad body is 422 naming the field; a missing token is 403; neither changes anything', async () => {
    const noAgent = await call('POST', '/api/v1/assistant/conversations', { body: {} });
    expect(noAgent.status).toBe(422);
    expect(noAgent.body.message).toContain('agent');
    check('E-CONVERSATION-NEW', 422, noAgent.body);
    expect((await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola', idempotency_key: 'x' } })).body.message).toContain('idempotency_key');
    await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'chidi' } });
    const path = '/api/v1/assistant/conversations/CV-N1/messages';
    expect((await call('POST', path, { body: { text: '' } })).body.message).toContain('text');
    expect((await call('POST', path, { body: { text: 'ok', mentions: [{ kind: 'meeting', id: 'x' }] } })).status).toBe(422);
    expect((await call('POST', path, { body: { text: 'a'.repeat(4001) } })).body.message).toContain('text');
    const noToken = await call('POST', path, { body: { text: 'ok' }, csrf: null });
    expect(noToken.status).toBe(403);
    expect(noToken.body.code).toBe('csrf_failed');
    expect((await conversation('CV-N1')).body.messages).toEqual([]);
  });

  it('[working] answers working and advances on reads like CV-2405', async () => {
    await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola' } });
    const sent = await call('POST', '/api/v1/assistant/conversations/CV-N1/messages', { body: { text: 'Please [working]' } });
    expect(sent.body.status).toBe('working');
    const states = [];
    for (let i = 0; i < 4; i += 1) {
      const c = (await conversation('CV-N1')).body;
      check('E-CONVERSATION', 200, c);
      states.push([c.status, c.messages[1].step_details.map((s: any) => s.state).join(',')]);
    }
    expect(states).toEqual([
      ['working', 'now,next,next'],
      ['working', 'done,now,next'],
      ['working', 'done,done,now'],
      ['answered', 'done,done,done'],
    ]);
  });

  for (const [token, status] of [['[409]', 409], ['[422]', 422], ['[500]', 500]] as const) {
    it(`${token} answers ${status} once, writes nothing, and the same text then goes through`, async () => {
      const path = '/api/v1/assistant/conversations/CV-2401/messages';
      const first = await call('POST', path, { body: { text: `Try ${token}` } });
      expect(first.status).toBe(status);
      if (status !== 500) check('E-MESSAGE', status, first.body);
      expect((await conversation('CV-2401')).body.messages).toHaveLength(2);
      expect((await call('POST', path, { body: { text: `Try ${token}` } })).status).toBe(200);
      expect((await conversation('CV-2401')).body.messages).toHaveLength(4);
    });
  }

  it('the log records every POST once, in order, with its status', async () => {
    await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola' } });
    await call('POST', '/api/v1/assistant/conversations/CV-N1/messages', { body: { text: 'one [500]' } });
    await call('POST', '/api/v1/assistant/conversations/CV-N1/messages', { body: { text: 'two' } });
    expect((await log()).map((e) => [e.operation, e.status])).toEqual([['E-CONVERSATION-NEW', 200], ['E-MESSAGE', 500], ['E-MESSAGE', 200]]);
  });
});

describe('E-MENTION-OPTIONS', () => {
  it('filters by q and kind for the persona; a missing q is not served', async () => {
    const harm = (await get('/api/v1/assistant/mentions?q=harm')).body;
    expect(harm.items.map((i: any) => i.id)).toEqual(['P-0102', 'W-1005', 'D-0042']);
    expect(harm.items.every((i: any) => i.sample === true)).toBe(true);
    expect((await get('/api/v1/assistant/mentions?q=harm&kind=document')).body.items.map((i: any) => i.kind)).toEqual(['document']);
    expect((await get('/api/v1/assistant/mentions?q=zzz')).body.items).toEqual([]);
  });
});

describe('a draft’s start (simulates G-SCR05-1)', () => {
  const start = (extra: Record<string, unknown> = {}, persona = 'pm') =>
    call('POST', '/api/v1/work', {
      persona,
      body: { line: 'invoice', case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' }, idempotency_key: 'k-1', ...extra },
    });

  it('an unarmed start (the draft was not read) falls through to Start work’s pinned billing-contact 422', async () => {
    const reply = await start();
    expect(reply.status).toBe(422);
    expect(reply.body.fields.map((f: any) => f.name)).toEqual(['billing_contact']);
  });

  it('after the persona reads the draft, the matching start is 201 and sets draft.started and the list line', async () => {
    await conversation('CV-2401');
    const reply = await start();
    expect(reply).toEqual({ status: 201, body: { work_id: 'W-1401', state: 'processing' } });
    check('E-WORK-START', 201, reply.body);
    const read = (await conversation('CV-2401')).body;
    check('E-CONVERSATION', 200, read);
    expect(read.messages[1].draft.started).toEqual({ work_id: 'W-1401', reference: 'INV-0415' });
    expect((await get('/api/v1/assistant/conversations')).body.items[0].status_line).toBe('Started · INV-0415');
  });

  it('a repeat of the same key and body replays the 201; a second start with another key is 409; one start exists', async () => {
    await conversation('CV-2401');
    expect((await start()).status).toBe(201);
    expect(await start()).toEqual({ status: 201, body: { work_id: 'W-1401', state: 'processing' } });
    const second = await start({ idempotency_key: 'k-2' });
    expect(second.status).toBe(409);
    expect(second.body).toEqual({ code: 'draft_already_started', message: 'This draft was already started.' });
    check('E-WORK-START', 409, second.body);
  });

  it('a start that differs from the draft (another milestone, line or case) is not the draft’s and goes to Start work unchanged', async () => {
    await conversation('CV-2401');
    const other = await start({ intake: { project: 'P-0101', milestone: 'M-0103' }, case_id: 'C-0101', case_revision: 6 });
    // Start work's own answer (a valid Lagoon start), and the draft is untouched
    expect(other).toEqual({ status: 201, body: { work_id: 'W-1401', state: 'processing' } });
    expect((await conversation('CV-2401')).body.messages[1].draft.started).toBeUndefined();
    expect((await get('/api/v1/assistant/conversations')).body.items[0].status_line).toBe('Drafted · ready to start');
  });

  it('reading is per persona: finance_lead reading CV-2411 does not arm pm’s draft', async () => {
    await conversation('CV-2411', 'finance_lead');
    expect((await start()).status).toBe(422);
  });

  it('a missing token is 403 as for any write', async () => {
    await conversation('CV-2401');
    const reply = await call('POST', '/api/v1/work', { csrf: null, body: { line: 'invoice', case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' }, idempotency_key: 'k-3' } });
    expect(reply.status).toBe(403);
  });

  it('reset restores every override, read mark, log and created conversation', async () => {
    await conversation('CV-2401');
    await start();
    await call('POST', '/api/v1/assistant/conversations', { body: { agent: 'tola' } });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await conversation('CV-2401')).body.messages[1].draft.started).toBeUndefined();
    expect((await get('/api/v1/assistant/conversations')).body.items[0].status_line).toBe('Drafted · ready to start');
    expect((await conversation('CV-N1')).status).toBe(404);
    expect(await log()).toEqual([]);
    // and the read mark is gone: a start now is unarmed again... after this read it is armed
    expect((await start({ idempotency_key: 'k-4' })).status).toBe(201);
  });
});

describe('operations', () => {
  it('the mock owns exactly the five assistant operations', () => {
    expect(ASSISTANT_OPERATIONS).toEqual(['E-CONVERSATIONS', 'E-CONVERSATION', 'E-CONVERSATION-NEW', 'E-MESSAGE', 'E-MENTION-OPTIONS']);
  });
});
