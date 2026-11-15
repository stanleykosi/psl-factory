// E-CLIENTS, E-CLIENT and E-CLIENT-CONTACT in the contract mock (architecture v7, D-CLIENTS-VIEW r1, proposed).
// The list comes from fixtures/clients/list.json, or from cookie psl_mock_clients = empty | many (25 generated rows,
// cursor o<N>, limit 10 | 20 | 50). A detail comes from fixtures/clients/<client_id>.json; the list's other clients
// get a minimal detail built from their row. CL-3599 is the reserved no-access id. CL-3508 answers its first PUT with
// 409 and then serves CL-3508.next.json (the newer revision). Sample data only; no business rules.
// Check order: persona none (403), 404, request shape (422), field (422), stale revision (409), success.
// A saved contact is kept in memory per persona and client (revision + 1, billing_contact.set true, blocked removed);
// resetClients() clears it. Every reply is validated against the v7 schema before it is sent.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, 'fixtures', 'clients');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const list = readJson(join(dir, 'list.json'));
const details = Object.fromEntries(
  readdirSync(dir)
    .filter((name) => /^CL-\d+(\.next)?\.json$/.test(name))
    .map((name) => [name.slice(0, -5), readJson(join(dir, name))]),
);

const openapi = readJson(join(here, '..', '..', 'architecture', 'packages', 'v7', 'openapi.json'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path, method, status) => openapi.paths[path][method].responses[status].content['application/json'].schema;
const validators = {
  'E-CLIENTS': ajv.compile(schemaOf('/api/v1/clients', 'get', '200')),
  'E-CLIENT': ajv.compile(schemaOf('/api/v1/clients/{client_id}', 'get', '200')),
  'E-CLIENT-CONTACT': ajv.compile(schemaOf('/api/v1/clients/{client_id}/billing-contact', 'put', '200')),
};

export const CLIENT_OPERATIONS = ['E-CLIENTS', 'E-CLIENT', 'E-CLIENT-CONTACT'];
export const NO_ACCESS_CLIENT_ID = 'CL-3599';
const LIMITS = [10, 20, 50];
const MANY_ROWS = 25;
const STALE_FIRST_ID = 'CL-3508';

const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const INVALID = { code: 'invalid', message: 'Check the highlighted details and try again.' };
const STALE = { code: 'stale_revision', message: 'This client changed since you opened it. Reload to see the latest version.' };

// persona:client_id -> { name, email, revision } after a save; persona:client_id that have answered their first 409.
const saved = new Map();
const staled = new Set();

export function resetClients() {
  saved.clear();
  staled.clear();
}

const decodeId = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

function decodeCursor(cursor) {
  const match = /^o(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : null;
}

function manyRows() {
  return Array.from({ length: MANY_ROWS }, (_, i) => ({
    client_id: `CL-4${String(i + 1).padStart(3, '0')}`,
    name: `Sample client ${i + 1}`,
    projects: i % 4,
    billing_contact_set: i % 3 !== 0,
    sample: true,
  }));
}

function rowsFor(cookies) {
  if (cookies.psl_mock_clients === 'empty') return { items: [], as_of: list.as_of };
  if (cookies.psl_mock_clients === 'many') return { items: manyRows(), as_of: list.as_of };
  return list;
}

function clientList(url, cookies, persona) {
  const params = url.searchParams;
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  if (!LIMITS.includes(limit) || offset === null || params.get('q') === '') return { status: 404, body: INVALID_QUERY };
  const { items, as_of } = rowsFor(cookies);
  const body = { items: items.slice(offset, offset + limit).map((row) => withSaved(row, persona)), as_of };
  if (offset + limit < items.length) body.next_cursor = `o${offset + limit}`;
  return { status: 200, body };
}

/** A list row after a save: the contact is now set. */
function withSaved(row, persona) {
  return saved.has(`${persona}:${row.client_id}`) ? { ...row, billing_contact_set: true } : row;
}

/** The detail now served: the fixture (or its .next after the first 409), or a minimal one for the list's other rows. */
function baseDetail(clientId, persona) {
  if (staled.has(`${persona}:${clientId}`) && details[`${clientId}.next`]) return details[`${clientId}.next`];
  if (Object.hasOwn(details, clientId)) return details[clientId];
  const row = list.items.find((r) => r.client_id === clientId);
  if (!row) return undefined;
  return { client_id: clientId, name: row.name, revision: 1, billing_contact: { set: row.billing_contact_set }, projects: [] };
}

function currentDetail(clientId, persona) {
  const base = baseDetail(clientId, persona);
  const own = saved.get(`${persona}:${clientId}`);
  if (!base || !own) return base;
  const rest = Object.fromEntries(Object.entries(base).filter(([key]) => key !== 'blocked'));
  return { ...rest, revision: own.revision, billing_contact: { name: own.name, email: own.email, set: true } };
}

function readBody(raw) {
  try {
    const body = JSON.parse(raw);
    return body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  } catch {
    return null;
  }
}

function setContact(clientId, raw, persona) {
  const detail = currentDetail(clientId, persona);
  const key = `${persona}:${clientId}`;
  if (clientId === NO_ACCESS_CLIENT_ID || !detail) return { status: 404, body: NOT_FOUND };
  const body = readBody(raw);
  const keys = body ? Object.keys(body) : [];
  const shaped =
    body &&
    Number.isInteger(body.expected_revision) &&
    typeof body.name === 'string' &&
    typeof body.email === 'string' &&
    keys.every((key) => ['expected_revision', 'name', 'email', 'reason'].includes(key)) &&
    (body.reason === undefined || typeof body.reason === 'string');
  if (!shaped) return { status: 422, body: { ...INVALID, message: 'We could not read that request.' } };
  const fields = [];
  if (body.name.trim() === '') fields.push({ name: 'name', message: 'Enter the billing contact’s name.' });
  if (body.email.trim() === '') fields.push({ name: 'email', message: 'Enter the billing email.' });
  else if (!body.email.includes('@')) fields.push({ name: 'email', message: 'Enter a valid email address.' });
  if (fields.length) return { status: 422, body: { ...INVALID, fields } };
  if (clientId === STALE_FIRST_ID && !staled.has(key)) {
    staled.add(key);
    return { status: 409, body: STALE };
  }
  if (body.expected_revision !== detail.revision) return { status: 409, body: STALE };
  const revision = detail.revision + 1;
  saved.set(key, { name: body.name.trim(), email: body.email.trim(), revision });
  return { status: 200, body: { client_id: clientId, revision } };
}

function validated(operationId, result) {
  if (result.status !== 200) return result;
  const validate = validators[operationId];
  if (!validate(result.body)) throw new Error(`clients mock: ${operationId} reply is not valid: ${ajv.errorsText(validate.errors)}`);
  return result;
}

export function clients({ operationId, url, raw, persona, cookies = {} }) {
  if (persona === 'none') return { status: 403, body: FORBIDDEN };
  if (operationId === 'E-CLIENTS') return validated(operationId, clientList(url, cookies, persona));
  const clientId = decodeId(url.pathname.split('/')[4] ?? '');
  if (operationId === 'E-CLIENT-CONTACT') return validated(operationId, setContact(clientId, raw, persona));
  const detail = clientId === NO_ACCESS_CLIENT_ID ? undefined : currentDetail(clientId, persona);
  return validated(operationId, detail ? { status: 200, body: detail } : { status: 404, body: NOT_FOUND });
}
