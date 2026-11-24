// Alerts in the contract mock (F-12, reshaped for F-61): the four live operations of API 1.24.0 -
// GET /api/v1/notifications?page=, POST /api/v1/notifications/{id}/read, GET and POST /api/v1/me/alert-preferences.
// Sample data only; nothing is sent anywhere. server.mjs hands these paths here before its v7 routes (ALERT_PATH).
//
// Scenario: cookie psl_mock_alerts, else env MOCK_ALERTS_SCENARIO, else board
// (board | empty | many | stale | invalid | readfail | gone). many has 60 alerts over three pages of 25. stale answers the
// first save with 409 after another person saved; invalid answers every save with 422; readfail answers a mark-read
// with 500; gone answers it with 404. State is in memory per persona:scenario; reset() clears it.
// The persona fixtures under fixtures/alerts are in the v7 shape; they are converted to live items here.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', path), 'utf8'));

export const ALERT_PATH = /^\/api\/v1\/(notifications|notifications\/[^/]+\/read|me\/alert-preferences)$/;
export const ALERT_SCENARIOS = ['board', 'empty', 'many', 'stale', 'invalid', 'readfail', 'gone'];
const PAGE_SIZE = 25;
const DAY_MS = 86_400_000;
const MIN_MS = 60_000;

const BAD_PAGE = { code: 'invalid', message: 'Check the page number.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const UNAVAILABLE = { code: 'server_error', message: 'Something went wrong on our side.' };
const invalid = (message) => [422, { code: 'invalid', message }];

const lagosDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });
const dayNumber = (value) => Date.parse(`${lagosDay.format(new Date(value))}T00:00:00Z`) / DAY_MS;
const iso = (ms) => new Date(ms).toISOString().replace('.000Z', 'Z');

/** A v7 item (what the persona fixtures and the demo's line runs hold) as a live item. */
function live(item) {
  const project = item.case_id;
  return {
    id: item.id,
    title: item.text,
    subject: item.reference ?? '',
    detail: '',
    group: item.needs_you === true ? 'action' : 'update',
    read: item.read,
    django_url: `/work/${item.work_id}/`,
    at: item.at ?? null,
    agent: item.agent ?? null,
    target_kind: project ? 'project' : 'work',
    api_url: project ? `/api/v1/projects/${project}` : `/api/v1/work/${item.work_id}`,
  };
}

/** The persona's list with every date moved by the whole days between its as_of and today (Africa/Lagos). */
function shifted(list) {
  const ms = (dayNumber(Date.now()) - dayNumber(list.as_of)) * DAY_MS;
  return list.items.map((item) => (item.at ? { ...item, at: iso(Date.parse(item.at) + ms) } : item));
}

/** Six alerts as the board draws them: needs-you and information, with and without an agent, a time and a link. */
function boardItems(now) {
  const base = { detail: '', read: false, target_kind: 'work' };
  return [
    { ...base, id: 'a1'.padEnd(64, '0'), title: 'Invoice ready for review', subject: 'Lagoon Health', detail: 'INV-LH-002', group: 'action', django_url: '/work/4103/', at: iso(now - 18 * MIN_MS), agent: 'chidi', api_url: '/api/v1/work/4103' },
    { ...base, id: 'a2'.padEnd(64, '0'), title: 'Project plan to sign off', subject: 'Kestrel Logistics', group: 'action', django_url: '/work/4102/', at: iso(now - 95 * MIN_MS), agent: 'tola', api_url: '/api/v1/work/4102' },
    { ...base, id: 'a3'.padEnd(64, '0'), title: 'Assistant reply', subject: 'Lagoon Health', detail: 'Tola', group: 'update', django_url: '/assistant/7/', at: iso(now - 4 * MIN_MS), agent: 'tola', target_kind: 'conversation', api_url: '/api/v1/assistant/conversations/7' },
    { ...base, id: 'a4'.padEnd(64, '0'), title: 'Milestone 2 is complete', subject: 'Kestrel Logistics', group: 'update', read: true, django_url: '/work/4101/', at: iso(now - DAY_MS - 3 * 3_600_000), agent: 'zainab', target_kind: 'project', api_url: '/api/v1/projects/6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f' },
    { ...base, id: 'a5'.padEnd(64, '0'), title: 'Invoice review', subject: 'Ojo Foods', detail: 'INV-0398', group: 'action', django_url: '/work/4105/', at: null, agent: null, api_url: null },
    { ...base, id: 'a6'.padEnd(64, '0'), title: 'Reminder: month-end close', subject: '', group: 'update', django_url: '/reminders/9/', at: null, agent: null, target_kind: null, api_url: null },
  ];
}

function manyItems(now) {
  return Array.from({ length: 60 }, (_, i) => ({
    id: `m${String(i + 1).padStart(2, '0')}`.padEnd(64, '0'),
    title: `Update ${i + 1} for Lagoon Health`,
    subject: 'Lagoon Health',
    detail: `INV-${String(i + 1).padStart(2, '0')}`,
    group: i % 5 === 0 ? 'action' : 'update',
    read: i >= 40,
    django_url: `/work/${5000 + i}/`,
    at: iso(now - (i + 1) * 17 * MIN_MS),
    agent: ['tola', 'chidi', 'zainab'][i % 3],
    target_kind: 'work',
    api_url: `/api/v1/work/${5000 + i}`,
  }));
}

function prefs() {
  const now = Date.now();
  return {
    revision: 3,
    email_requested: true,
    whatsapp_requested: false,
    email_ready: true,
    whatsapp_ready: false,
    recent_deliveries: [
      { channel: 'email', state: 'delivered', created_at: iso(now - 3 * 3_600_000), delivered_at: iso(now - 3 * 3_600_000 + 4000), receipt: 'r-77' },
      { channel: 'whatsapp', state: 'uncertain', created_at: iso(now - DAY_MS), delivered_at: null, receipt: null },
      { channel: 'email', state: 'queued', created_at: iso(now - 2 * DAY_MS), delivered_at: null, receipt: null },
      { channel: 'whatsapp', state: 'held', created_at: iso(now - 3 * DAY_MS), delivered_at: null, receipt: null },
    ],
  };
}

/** The data a persona starts with: the board's six alerts for finance_lead (all scenarios but many and empty), the persona's fixture for the others. */
function initialState(persona, scenario) {
  const now = Date.now();
  let items;
  if (scenario === 'empty') items = [];
  else if (scenario === 'many') items = manyItems(now);
  else if (persona === 'finance_lead') items = boardItems(now);
  else {
    const who = ['admin', 'pmo_lead'].includes(persona) ? 'none' : persona;
    items = shifted(read(`alerts/notifications.${who}.json`)).map(live);
  }
  return { items, prefs: prefs(), staleDone: false };
}

function listResponse(state, url) {
  const raw = url.searchParams.get('page');
  const page = raw === null ? 1 : /^\d+$/.test(raw) ? Number(raw) : 0;
  const pages = Math.max(1, Math.ceil(state.items.length / PAGE_SIZE));
  // Live: a page of 0, above 10000 or not a number is a 422; a page past the last is an empty 200.
  if (page < 1 || page > 10000) return [422, BAD_PAGE];
  const all = state.items;
  const today = dayNumber(Date.now());
  const unreadItems = all.filter((item) => !item.read);
  return [
    200,
    {
      items: all.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
      as_of: iso(Date.now()),
      page,
      next_page: page < pages ? page + 1 : null,
      unread: unreadItems.length,
      daily_summary: {
        date: lagosDay.format(new Date()),
        actions_open: all.filter((item) => item.group === 'action' && !item.read).length,
        unread_updates_today: unreadItems.filter((item) => item.group === 'update' && item.at && dayNumber(item.at) === today).length,
        unread_without_timestamp: unreadItems.filter((item) => !item.at).length,
        scope: 'current_inbox',
      },
    },
  ];
}

function markRead(state, url, raw, scenario) {
  let body;
  try {
    body = JSON.parse(raw || '{}');
  } catch {
    return invalid('Check the request.');
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body) || Object.keys(body).length) return invalid('The request body must be empty.');
  if (scenario === 'readfail') return [500, UNAVAILABLE];
  const id = decodeURIComponent(url.pathname.split('/')[4] ?? '');
  const item = state.items.find((row) => row.id === id);
  if (!item || scenario === 'gone') return [404, NOT_FOUND];
  item.read = true;
  return [200, { id, read: true }];
}

function savePrefs(state, raw, scenario) {
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid('Check the request.');
  }
  const keys = typeof body === 'object' && body !== null ? Object.keys(body).sort().join() : '';
  if (keys !== 'email_requested,revision,whatsapp_requested' || typeof body.revision !== 'number' || typeof body.email_requested !== 'boolean' || typeof body.whatsapp_requested !== 'boolean') {
    return invalid('Check the settings and try again.');
  }
  if (scenario === 'invalid') return invalid('Check the settings and try again.');
  const { prefs: held } = state;
  if (scenario === 'stale' && !state.staleDone) {
    // Another person saves first: the next revision, with email off.
    state.staleDone = true;
    held.revision += 1;
    held.email_requested = false;
    return [409, STALE];
  }
  if (body.revision !== held.revision) return [409, STALE];
  held.email_requested = body.email_requested;
  held.whatsapp_requested = body.whatsapp_requested;
  held.revision += 1;
  // The live save answers the switches and readiness without the receipts.
  const { recent_deliveries: receipts, ...saved } = held;
  void receipts;
  return [200, saved];
}

export function createAlertsMock() {
  const states = new Map();
  // D-155: alerts the live demo's runs raised (line-runs.mjs, v7 items), by persona; they join that persona's list on its next read.
  const raised = new Map();

  return {
    raise(persona, item) {
      raised.set(persona, [item, ...(raised.get(persona) ?? [])]);
    },
    /** [status, body] for one of the four paths; the caller has checked sign-in and CSRF. */
    handle({ method, url, raw, persona, cookies = {} }) {
      const chosen = cookies.psl_mock_alerts ?? process.env.MOCK_ALERTS_SCENARIO;
      const scenario = ALERT_SCENARIOS.includes(chosen) ? chosen : 'board';
      const key = `${persona}:${scenario}`;
      if (!states.has(key)) states.set(key, initialState(persona, scenario));
      const state = states.get(key);
      const added = raised.get(persona);
      if (added) {
        state.items.unshift(...added.map(live));
        raised.delete(persona);
      }
      const path = url.pathname;
      if (path === '/api/v1/notifications') return method === 'get' ? listResponse(state, url) : [405, { code: 'method_not_allowed', message: 'Not allowed.' }];
      if (path === '/api/v1/me/alert-preferences') {
        if (method === 'get') return [200, state.prefs];
        return method === 'post' ? savePrefs(state, raw, scenario) : [405, { code: 'method_not_allowed', message: 'Not allowed.' }];
      }
      return method === 'post' ? markRead(state, url, raw, scenario) : [405, { code: 'method_not_allowed', message: 'Not allowed.' }];
    },
    reset() {
      states.clear();
      raised.clear();
    },
  };
}
