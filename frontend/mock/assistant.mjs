// Assistant in the contract mock (F-24, PROPOSAL D-ASSISTANT-VIEW and D-CONVERSATION-MODEL): E-CONVERSATIONS,
// E-CONVERSATION, E-CONVERSATION-NEW, E-MESSAGE and E-MENTION-OPTIONS, plus the draft's start. Local use only:
// no agent runs, nothing is sent to anyone, and every answer is fixture text or labelled sample text.
//
// Order of checks (as workspace.mjs): scenario, CSRF, request body against the v7 schema (422 naming the fields),
// ownership (404 for another persona's or an unknown conversation), then the script. Every reply is checked against
// its v7 response schema (500 mock_invalid_reply otherwise).
// Fixtures: fixtures/assistant/index.json (the list; `_persona` and `_hidden` are the mock's own and are not served),
// CV-xxxx.json (each a full v7 E-CONVERSATION), mentions.json (`_personas` stripped).
// Working advances on reads: CV-2405 shows step 3, then 4, then 5, then the sample answer; a message containing
// "[working]" does the same from step 1. A message containing [409], [422] or [500] answers that status once.
// The two POSTs have no idempotency key in the contract, so the mock keeps a log of them (GET /__mock/assistant-log)
// to prove one POST per press. A draft's start (simulates G-SCR05-1) is recognised only after the persona read the
// draft's conversation; it sets `draft.started`, and a second start of the same draft is a 409.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

export const ASSISTANT_OPERATIONS = ['E-CONVERSATIONS', 'E-CONVERSATION', 'E-CONVERSATION-NEW', 'E-MESSAGE', 'E-MENTION-OPTIONS'];
export const ASSISTANT_LOG_PATH = '/__mock/assistant-log';

const dir = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'assistant');
const readJson = (name) => JSON.parse(readFileSync(join(dir, `${name}.json`), 'utf8'));

const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const SAMPLE = 'Sample answer from the contract mock. No agent ran.';
// F-55: the HR stand-in's answer to a new message; it never shows pay amounts.
const HR_SAMPLE = 'Sample answer from the contract mock. No agent ran. I can help with staff lists and business units. I do not show pay amounts: who can see payroll has not been set up yet.';
// D-150: the CEO stand-in's answer to a new message; it shows no pay amounts.
const CEO_SAMPLE = 'Sample answer from the contract mock. No agent ran. I can show what waits for your decision and how the projects are doing. I do not show pay amounts: who can see payroll has not been set up yet.';
const STARTED = { work_id: 'W-1401', reference: 'INV-0415' };
const HOOKS = { '[409]': 409, '[422]': 422, '[500]': 500 };
const HOOK_BODIES = {
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' },
  422: { code: 'invalid', message: 'The mock refused this message: check the text and try again.' },
  500: { code: 'server_error', message: 'The mock answered with a scripted server error.' },
};
const LIMITS = [10, 20, 50];
const NOW = '2026-11-16T14:30:00Z';

const decode = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};
const strip = (row) => Object.fromEntries(Object.entries(row).filter(([key]) => !key.startsWith('_')));
const fieldNames = (errors) => [...new Set(errors.map((e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body')))];
const invalid = (names) => [422, { code: 'invalid', message: `Check these fields: ${names.join(', ')}.` }];

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}

export function createAssistantMock({ openapi }) {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const ops = {};
  for (const methods of Object.values(openapi.paths)) {
    for (const op of Object.values(methods)) {
      if (!op?.operationId) continue;
      const replies = {};
      for (const [status, reply] of Object.entries(op.responses)) {
        const schema = reply.content?.['application/json']?.schema;
        if (schema) replies[status] = ajv.compile(schema);
      }
      const body = op.requestBody?.content?.['application/json']?.schema;
      if (ASSISTANT_OPERATIONS.includes(op.operationId)) ops[op.operationId] = { replies, request: body ? ajv.compile(body) : undefined };
      if (op.operationId === 'E-WORK-START') ops[op.operationId] = { replies, request: ajv.compile(body) };
    }
  }

  const index = readJson('index');
  const fixtures = Object.fromEntries(
    readdirSync(dir).filter((n) => /^CV-\d+\.json$/.test(n)).map((n) => [n.slice(0, -5), readJson(n.slice(0, -5))]),
  );
  const mentions = readJson('mentions');
  // CV-2406 is reachable by URL for the pm only, and is not in the list.
  const owners = { ...Object.fromEntries(index.items.map((row) => [row.conversation_id, row._persona])), 'CV-2406': 'pm' };

  // State, cleared by reset(): one record per conversation (the fixtures, then the ones made here).
  let store, armed, started, startReplies, counter, hooks, log;
  function reset() {
    store = new Map(
      Object.entries(fixtures).map(([id, body]) => {
        const row = index.items.find((r) => r.conversation_id === id);
        const rec = { id, persona: owners[id], agent: body.agent, title: body.title, status: body.status, line: row?.status_line, context: body.context, messages: structuredClone(body.messages), at: row?.updated_at ?? index.as_of, listed: Boolean(row) };
        // The planning packet is a working run: it moves one step on each read (the board's step 3 first).
        if (id === 'CV-2405') rec.run = { steps: body.messages[1].step_details.map((d) => ({ text: d.text, label: d.reference?.label })), from: 2, reads: 0, at: body.messages[0].at, at_index: 1, text: body.messages[1].text };
        return [id, rec];
      }),
    );
    armed = new Set();
    started = new Map();
    startReplies = new Map();
    counter = 0;
    hooks = new Set();
    log = [];
  }
  reset();

  /** A working run at its n-th read: steps done, the one in progress, the rest to do; answered past the end. */
  function runAt(run, n) {
    const now = run.from + n;
    const answered = now >= run.steps.length;
    const state = (i) => (i < now ? 'done' : i === now ? 'now' : 'next');
    return {
      status: answered ? 'answered' : 'working',
      line: answered ? 'Answered' : `Working · step ${now + 1} of ${run.steps.length}`,
      agent: {
        role: 'agent',
        text: answered ? SAMPLE : run.text,
        steps: run.steps.map((x) => x.text),
        sources: [],
        at: run.at,
        step_details: run.steps.map((x, i) => ({ text: x.text, state: answered ? 'done' : state(i), ...(x.label ? { reference: { label: x.label } } : {}) })),
      },
    };
  }

  function readConversation(id, persona) {
    const rec = store.get(id);
    if (!rec || rec.persona !== persona) return null;
    armed.add(`${persona}:${id}`);
    const body = { conversation_id: id, ...(rec.agent ? { agent: rec.agent } : {}), title: rec.title, status: rec.status, ...(rec.context ? { context: structuredClone(rec.context) } : {}), messages: structuredClone(rec.messages) };
    const mark = started.get(id);
    if (mark) for (const m of body.messages) if (m.draft?.start) m.draft.started = { ...mark };
    if (rec.run) {
      const n = rec.run.reads;
      rec.run.reads += 1;
      const run = runAt(rec.run, n);
      body.status = rec.status = run.status;
      rec.line = run.line;
      body.messages[rec.run.at_index] = run.agent;
      rec.messages[rec.run.at_index] = structuredClone(run.agent);
    }
    return body;
  }

  function list(url, persona) {
    const mine = [...store.values()].filter((rec) => rec.persona === persona && rec.listed);
    // The conversations made here come first, newest first; the fixtures follow in the list's order.
    const made = mine.filter((rec) => rec.id.startsWith('CV-N')).sort((x, y) => Number(y.id.slice(4)) - Number(x.id.slice(4)));
    const rows = [...made, ...mine.filter((rec) => !rec.id.startsWith('CV-N'))]
      .map((rec) => ({
        conversation_id: rec.id,
        title: rec.title,
        agent: rec.agent,
        status: rec.status,
        ...(started.has(rec.id) ? { status_line: `Started · ${started.get(rec.id).reference}` } : rec.line ? { status_line: rec.line } : {}),
        updated_at: rec.at,
      }));
    const limit = LIMITS.includes(Number(url.searchParams.get('limit'))) ? Number(url.searchParams.get('limit')) : 20;
    const match = /^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '');
    const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
    const page = { items: rows.slice(offset, offset + limit), as_of: index.as_of };
    if (offset + limit < rows.length) page.next_cursor = `o:${offset + limit}`;
    return [200, page];
  }

  function mentionOptions(url, persona) {
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const kind = url.searchParams.get('kind');
    const rows = mentions.items.filter((r) => r._personas.includes(persona) && (!kind || r.kind === kind) && r.label.toLowerCase().includes(q));
    const limit = LIMITS.includes(Number(url.searchParams.get('limit'))) ? Number(url.searchParams.get('limit')) : 20;
    return [200, { items: rows.slice(0, limit).map(strip), as_of: mentions.as_of }];
  }

  const logPost = (entry, reply) => {
    log.push({ ...entry, status: reply[0] });
    return reply;
  };

  function newConversation(raw, persona, agents) {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return logPost({ operation: 'E-CONVERSATION-NEW' }, invalid(['body']));
    }
    const { request } = ops['E-CONVERSATION-NEW'];
    if (!request(body)) return logPost({ operation: 'E-CONVERSATION-NEW' }, invalid(fieldNames(request.errors)));
    const entry = { operation: 'E-CONVERSATION-NEW', agent: body.agent };
    if (!agents.includes(body.agent)) return logPost(entry, [403, { code: 'forbidden', message: 'That agent is not available to you.' }]);
    counter += 1;
    const id = `CV-N${counter}`;
    store.set(id, { id, persona, agent: body.agent, title: 'New request', status: 'answered', messages: [], at: NOW, listed: true });
    return logPost({ ...entry, conversation_id: id }, [200, { conversation_id: id }]);
  }

  function message(url, raw, persona) {
    const id = decode(url.pathname.split('/')[5] ?? '');
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return logPost({ operation: 'E-MESSAGE', conversation_id: id }, invalid(['body']));
    }
    const { request } = ops['E-MESSAGE'];
    const entry = { operation: 'E-MESSAGE', conversation_id: id, text: body?.text, mentions: body?.mentions };
    if (!request(body) || body.text.length > 4000) return logPost(entry, invalid(request(body) ? ['text'] : fieldNames(request.errors)));
    const own = store.get(id);
    if (!own || own.persona !== persona) return logPost(entry, [404, NOT_FOUND]);
    for (const [token, status] of Object.entries(HOOKS)) {
      if (body.text.includes(token) && !hooks.has(`${id}:${token}`)) {
        hooks.add(`${id}:${token}`);
        return logPost(entry, [status, HOOK_BODIES[status]]);
      }
    }
    const at = NOW;
    own.messages.push({ role: 'person', text: body.text, steps: [], sources: [], at });
    if (own.title === 'New request') own.title = body.text.replace(/\s+/g, ' ').slice(0, 60);
    own.at = at;
    const wantsWork = body.text.includes('[working]');
    const steps = wantsWork
      ? [{ text: 'Read your request' }, { text: 'Looked up the records you can see' }, { text: 'Wrote the answer' }]
      : [{ text: 'Read your question' }];
    const placeholder = {
      role: 'agent',
      text: wantsWork ? 'Working on it.' : persona === 'hr' || persona === 'hr_lead' ? HR_SAMPLE : persona === 'ceo' ? CEO_SAMPLE : SAMPLE,
      steps: steps.map((s) => s.text),
      sources: [],
      at,
      step_details: steps.map((s, i) => ({ text: s.text, state: wantsWork ? (i === 0 ? 'now' : 'next') : 'done' })),
    };
    own.messages.push(placeholder);
    own.status = wantsWork ? 'working' : 'answered';
    own.line = wantsWork ? `Working · step 1 of ${steps.length}` : 'Answered';
    own.run = wantsWork ? { steps, from: 0, reads: 0, at, at_index: own.messages.length - 1, text: 'Working on it.' } : undefined;
    return logPost(entry, [200, { message_id: `M-${own.messages.length}`, agent_run_id: `R-${counter}-${own.messages.length}`, status: wantsWork ? 'working' : 'answered' }]);
  }

  /**
   * The draft's start, or null when this request is not one (the caller then uses start-work.mjs unchanged). A request
   * is the draft's start only when this persona has read the draft's conversation since the last reset and the
   * line, case and project and milestone equal that draft's `start`.
   */
  function draftStart(raw, persona) {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return null;
    }
    const { request } = ops['E-WORK-START'];
    if (!request(body)) return null;
    const hit = Object.entries(fixtures).find(([id, conv]) =>
      armed.has(`${persona}:${id}`) && conv.messages.some((m) => {
        const s = m.draft?.start;
        return s && s.line_key === body.line && s.case_id === body.case_id && s.intake?.project === body.intake?.project && s.intake?.milestone === body.intake?.milestone;
      }),
    );
    if (!hit) return null;
    const previous = startReplies.get(body.idempotency_key);
    if (previous) return canonical(previous.body) === canonical(body) ? previous.reply : null;
    const [id] = hit;
    // Every reply is checked against the v7 E-WORK-START schema, as the other mock replies are.
    const checked = (reply) => {
      const validate = ops['E-WORK-START'].replies[String(reply[0])];
      return validate && !validate(reply[1]) ? [500, { code: 'mock_invalid_reply', message: `The mock's E-WORK-START ${reply[0]} reply does not match v7.` }] : reply;
    };
    if (started.has(id)) return checked([409, { code: 'draft_already_started', message: 'This draft was already started.' }]);
    started.set(id, { ...STARTED });
    const reply = checked([201, { work_id: STARTED.work_id, state: 'processing' }]);
    startReplies.set(body.idempotency_key, { body, reply });
    return reply;
  }

  return {
    reset,
    log: () => ({ entries: log.map((e) => ({ ...e })) }),
    draftStart,
    /** One reply for an assistant operation, validated against its v7 schema. */
    handle({ operationId, url, raw, persona, agents }) {
      let reply;
      if (operationId === 'E-CONVERSATIONS') reply = list(url, persona);
      else if (operationId === 'E-MENTION-OPTIONS') reply = mentionOptions(url, persona);
      else if (operationId === 'E-CONVERSATION-NEW') reply = newConversation(raw, persona, agents);
      else if (operationId === 'E-MESSAGE') reply = message(url, raw, persona);
      else {
        const body = readConversation(decode(url.pathname.split('/')[5] ?? ''), persona);
        reply = body ? [200, body] : [404, NOT_FOUND];
      }
      const validate = ops[operationId].replies[String(reply[0])];
      if (validate && !validate(reply[1])) return [500, { code: 'mock_invalid_reply', message: `The mock's ${operationId} ${reply[0]} reply does not match v7.` }];
      return reply;
    },
  };
}
