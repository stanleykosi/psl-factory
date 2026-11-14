// Alerts in the contract mock (F-12): E-NOTIFICATIONS, E-NOTIFICATION-READ, E-ALERT-PREFS-READ and E-ALERT-PREFS,
// shaped by the v7 overlay in proposals/alerts.json. Sample data only; nothing is sent anywhere.
//
// Scenario: cookie psl_mock_alerts, else env MOCK_ALERTS_SCENARIO, else board
// (board | phone | empty | many | bare | stale | invalid | locked). State is in memory per persona:scenario;
// reset() clears it. bare drops every proposal field and answers 404 to the two v7-only operations. Dates are moved by whole days so that each fixture's as_of falls on today in Africa/Lagos.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', path), 'utf8'));

export const ALERT_OPERATIONS = ['E-NOTIFICATIONS', 'E-NOTIFICATION-READ', 'E-ALERT-PREFS-READ', 'E-ALERT-PREFS'];
export const ALERT_SCENARIOS = ['board', 'phone', 'empty', 'many', 'bare', 'stale', 'invalid', 'locked'];
const AGENTS = ['tola', 'chidi', 'zainab'];
const LIMITS = [10, 20, 50];
const DAY_MS = 86_400_000;
const ITEM_PROPOSALS = ['reference', 'delivered_via', 'delivered_at', 'digest_at', 'in_app_reason'];

const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const invalid = (fields) => ({ status: 422, body: { code: 'invalid', message: `Check these fields: ${[...new Set(fields)].join(', ')}.` } });

/** Field names from Ajv errors, as errorFields in server.mjs: the missing or extra property, else the failing path. */
function errorFields(errors) {
  return errors.map(
    (e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body'),
  );
}

const lagosDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });
const dayNumber = (value) => Date.parse(`${lagosDay.format(new Date(value))}T00:00:00Z`) / DAY_MS;

/** The list with every date moved by the whole days between its as_of and today (Africa/Lagos). */
function shifted(list) {
  const ms = (dayNumber(Date.now()) - dayNumber(list.as_of)) * DAY_MS;
  const move = (value) => new Date(Date.parse(value) + ms).toISOString().replace('.000Z', 'Z');
  const items = list.items.map((item) => {
    const out = { ...item, at: move(item.at) };
    if (item.delivered_at) out.delivered_at = move(item.delivered_at);
    if (item.digest_at) out.digest_at = move(item.digest_at);
    return out;
  });
  return { ...list, items, as_of: move(list.as_of) };
}

/** The data a persona starts with: finance_lead's follows the scenario, the others keep their own records. */
function initialState(persona, scenario) {
  const own = persona !== 'finance_lead';
  let list = own ? read(`alerts/notifications.${persona}.json`) : read('E-NOTIFICATIONS.json');
  if (scenario === 'empty') list = read('alerts/notifications.empty.json');
  else if (scenario === 'many' && !own) list = read('alerts/notifications.many.json');
  const prefsFile = { phone: 'phone', locked: 'locked', invalid: 'invalid' }[scenario];
  const prefs = own ? read(`alerts/prefs.${persona}.json`) : prefsFile ? read(`alerts/prefs.${prefsFile}.json`) : read('E-ALERT-PREFS-READ.json');
  return { list: shifted(list), prefs, staleDone: false };
}

function putValidator(overlay) {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const op = overlay.paths['/api/v1/me/alert-preferences'].put;
  return ajv.compile(op.requestBody.content['application/json'].schema);
}

function listResponse(state, url, bare) {
  const params = url.searchParams;
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const cursor = params.get('cursor');
  const match = cursor === null ? ['', '0'] : /^o(\d+)$/.exec(cursor);
  const q = params.get('q');
  const agent = params.get('agent');
  const unread = params.get('unread');
  if (!LIMITS.includes(limit) || !match) return { status: 404, body: INVALID_QUERY };
  const all = state.list.items;
  let rows = all;
  // A v4 backend knows only cursor and limit; bare ignores the v7 parameters as such a backend would.
  if (!bare) {
    if (q === '' || (agent !== null && !AGENTS.includes(agent)) || (unread !== null && !['true', 'false'].includes(unread))) {
      return { status: 404, body: INVALID_QUERY };
    }
    const needle = q?.toLowerCase();
    rows = rows
      .filter((item) => !needle || [item.text, item.reference ?? ''].some((text) => text.toLowerCase().includes(needle)))
      .filter((item) => !agent || item.agent === agent)
      .filter((item) => unread === null || item.read === (unread === 'false'));
  }
  const offset = Number(match[1]);
  let items = rows.slice(offset, offset + limit);
  if (bare) items = items.map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => !ITEM_PROPOSALS.includes(key))));
  const body = { items };
  if (offset + limit < rows.length) body.next_cursor = `o${offset + limit}`;
  body.as_of = state.list.as_of;
  if (!bare) {
    body.total = rows.length;
    body.unread_count = all.filter((item) => !item.read).length;
  }
  return { status: 200, body };
}

function markRead(state, url) {
  const id = decodeURIComponent(url.pathname.split('/')[4] ?? '');
  const item = state.list.items.find((row) => row.id === id);
  if (!item) return { status: 404, body: NOT_FOUND };
  item.read = true;
  return { status: 200, body: { id, read: true, unread_count: state.list.items.filter((row) => !row.read).length } };
}

function savePrefs(state, raw, validate, scenario) {
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid(['body']);
  }
  if (!validate(body)) return invalid(errorFields(validate.errors));
  const { prefs } = state;
  const byKey = new Map(prefs.events.map((event) => [event.key, event]));
  for (const sent of body.events ?? []) {
    const event = byKey.get(sent.key);
    const changed = event && ['whatsapp', 'email'].some((ch) => ch in sent && sent[ch] !== event[ch]);
    if (!event || (event.locked_reason && changed)) return invalid(['events']);
  }
  const fields = [];
  if ('digest_at' in body && !prefs.digest_at?.options.some((o) => o.value === body.digest_at)) fields.push('digest_at');
  if ('quiet_hours' in body && !prefs.quiet_hours?.options.some((o) => o.value === body.quiet_hours)) fields.push('quiet_hours');
  if (fields.length) return invalid(fields);
  if (scenario === 'stale' && !state.staleDone) {
    // Another person saves first: the next revision, with "Work I started is stuck" email off.
    state.staleDone = true;
    prefs.revision += 1;
    const stuck = byKey.get('work_stuck');
    if (stuck) stuck.email = false;
    return { status: 409, body: STALE };
  }
  if ('expected_revision' in body && body.expected_revision !== prefs.revision) return { status: 409, body: STALE };
  prefs.channel = body.channel;
  prefs.frequency = body.frequency;
  for (const sent of body.events ?? []) {
    const event = byKey.get(sent.key);
    if ('whatsapp' in sent) event.whatsapp = sent.whatsapp;
    if ('email' in sent) event.email = sent.email;
  }
  if ('digest_at' in body) prefs.digest_at.value = body.digest_at;
  if ('quiet_hours' in body) prefs.quiet_hours.value = body.quiet_hours;
  prefs.revision += 1;
  return { status: 200, body: prefs };
}

export function createAlertsMock({ overlay }) {
  const validate = putValidator(overlay);
  const states = new Map();

  return {
    handle({ operationId, url, raw, persona, cookies = {} }) {
      const chosen = cookies.psl_mock_alerts ?? process.env.MOCK_ALERTS_SCENARIO;
      const scenario = ALERT_SCENARIOS.includes(chosen) ? chosen : 'board';
      const key = `${persona}:${scenario}`;
      if (!states.has(key)) states.set(key, initialState(persona, scenario));
      const state = states.get(key);
      const bare = scenario === 'bare';
      if (operationId === 'E-NOTIFICATIONS') return listResponse(state, url, bare);
      if (bare && operationId !== 'E-ALERT-PREFS') return { status: 404, body: NOT_FOUND };
      if (operationId === 'E-NOTIFICATION-READ') return markRead(state, url);
      if (operationId === 'E-ALERT-PREFS-READ') return { status: 200, body: state.prefs };
      return savePrefs(state, raw, validate, scenario);
    },
    reset() {
      states.clear();
    },
  };
}
