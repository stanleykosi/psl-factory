// SCR-35 clients in the live shape (contracts/psl-factory.openapi.json 1.24.0): GET /clients, /clients/groups/{group},
// /clients/{case_id} and /clients/{case_id}/contacts/history. The write routes are held and not served here.
// Fixtures: fixtures/clients/live.json (groups with their projects and debt, ungrouped projects, workspace contacts).
// Harmattan Bank is generated: 27 projects, so its group page has two pages and its debt is "limited". Cookie
// psl_mock_clients = empty | many (30 groups and 30 ungrouped projects, two pages each). Workspace 0b6f...0103 has 28
// billing contact versions (two history pages). Persona none: 403. Every other unknown key or id: 404. Pages of 25.
// Sample data only; no business rules. Every 200 is validated against the live contract's schemas.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const fixture = readJson(join(here, 'fixtures', 'clients', 'live.json'));

const contract = readJson(join(here, '..', '..', 'contracts', 'psl-factory.openapi.json'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path) => contract.paths[path].get.responses['200'].content['application/json'].schema;
const validators = {
  directory: ajv.compile(schemaOf('/api/v1/clients')),
  group: ajv.compile(schemaOf('/api/v1/clients/groups/{group}')),
  workspace: ajv.compile(schemaOf('/api/v1/clients/{case_id}')),
  history: ajv.compile(schemaOf('/api/v1/clients/{case_id}/contacts/history')),
};

export const CLIENT_OPERATIONS = ['E-CLIENTS', 'E-CLIENT'];
export const PAGE_SIZE = 25;
const BILLING = ['recorded', 'needed', 'unknown'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const KEY = /^[a-f0-9]{64}$/;

const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const BAD_REQUEST = { code: 'bad_request', message: 'We could not read that request.' };

const id = (n) => `0b6f9e1a-3c44-4d0a-9d52-${String(n).padStart(12, '0')}`;
const hex = (n) => n.toString(16).padStart(8, '0').repeat(8);

const harmattan = {
  key: hex(0xb2c3d4e5),
  label: 'Harmattan Bank',
  projects: Array.from({ length: 27 }, (_, i) => ({ case_id: id(1000 + i), title: `Branch rollout ${i + 1}`, client: 'Harmattan Bank', billing: BILLING[i % 3] })),
  debt: { as_of: '2026-11-23', workspace_count: 27, limited: true, totals: [{ currency: 'NGN', basis: 'sample basis', known_owed: '480000.00', unknown_owed_count: 0 }] },
};

const manyGroups = () =>
  Array.from({ length: 30 }, (_, i) => ({
    key: hex(0x10000000 + i),
    label: `Sample group ${i + 1}`,
    projects: [{ case_id: id(2000 + i), title: `Sample group ${i + 1} project`, client: `Sample group ${i + 1}`, billing: BILLING[i % 3] }],
    debt: null,
  }));
const manyProjects = () => Array.from({ length: 30 }, (_, i) => ({ case_id: id(3000 + i), title: `Sample project ${i + 1}`, client: i % 5 === 0 ? null : `Sample client ${i + 1}`, billing: BILLING[i % 3] }));

function dataset(cookies) {
  if (cookies.psl_mock_clients === 'empty') return { groups: [], ungrouped: [] };
  if (cookies.psl_mock_clients === 'many') return { groups: manyGroups(), ungrouped: manyProjects() };
  return { groups: [...fixture.groups.slice(0, 1), harmattan, ...fixture.groups.slice(1)], ungrouped: fixture.ungrouped };
}

const projectsOf = (groups, ungrouped) => [...groups.flatMap((g) => g.projects), ...ungrouped];
const contactsNeeded = (group) => group.projects.filter((p) => p.billing === 'needed').length;
const groupRow = (g) => ({ key: g.key, label: g.label, project_count: g.projects.length, contacts_needed: contactsNeeded(g), api_url: `/api/v1/clients/groups/${g.key}` });

const pageOf = (value) => {
  if (value === null) return 1;
  return /^[1-9]\d{0,8}$/.test(value) ? Number(value) : null;
};
function slice(rows, page) {
  const start = (page - 1) * PAGE_SIZE;
  return { rows: rows.slice(start, start + PAGE_SIZE), next: start + PAGE_SIZE < rows.length ? page + 1 : null };
}
const matches = (text, q) => text !== null && text.toLowerCase().includes(q.toLowerCase());

function directory(url, cookies) {
  const params = url.searchParams;
  const billing = params.get('billing');
  const q = params.get('q') ?? '';
  const groupPage = pageOf(params.get('clients_page'));
  const projectPage = pageOf(params.get('page'));
  if (groupPage === null || projectPage === null || (billing !== null && !BILLING.includes(billing)) || q.length > 100) return { status: 400, body: BAD_REQUEST };
  const { groups, ungrouped } = dataset(cookies);
  const shownGroups = groups.filter((g) => (!q || matches(g.label, q) || g.projects.some((p) => matches(p.title, q))) && (!billing || g.projects.some((p) => p.billing === billing)));
  const shownProjects = ungrouped.filter((p) => (!q || matches(p.title, q) || matches(p.client, q)) && (!billing || p.billing === billing));
  const g = slice(shownGroups, groupPage);
  const p = slice(shownProjects, projectPage);
  return { status: 200, check: 'directory', body: { groups: g.rows.map(groupRow), next_group_page: g.next, projects: p.rows, next_page: p.next } };
}

function group(key, url, cookies) {
  const page = pageOf(url.searchParams.get('page'));
  if (page === null || !KEY.test(key)) return { status: page === null ? 400 : 404, body: page === null ? BAD_REQUEST : NOT_FOUND };
  const found = dataset(cookies).groups.find((g) => g.key === key);
  if (!found) return { status: 404, body: NOT_FOUND };
  const p = slice(found.projects, page);
  return { status: 200, check: 'group', body: { key: found.key, label: found.label, projects: p.rows, next_page: p.next, debt: found.debt } };
}

/** Billing contacts of a workspace: the fixture's, or 28 versions for 0103's history. */
function contactsOf(caseId) {
  const own = fixture.workspaces[caseId];
  return own ? own.contacts : [];
}
function versionsOf(caseId, contact) {
  if (contact.version <= 1) return [contact];
  return Array.from({ length: contact.version }, (_, i) => ({ ...contact, contact_id: contact.contact_id + i, version: contact.version - i, role: i === 0 ? contact.role : `${contact.role} (earlier)` }));
}

function workspaceOf(caseId, cookies) {
  const { groups, ungrouped } = dataset(cookies);
  const project = projectsOf(groups, ungrouped).find((p) => p.case_id === caseId);
  if (!project) return undefined;
  const own = fixture.workspaces[caseId];
  return { case_id: caseId, title: project.title, revision: 3, sample: own?.sample ?? false, contacts: contactsOf(caseId), django_url: `/projects/${caseId}/` };
}

function workspace(caseId, cookies) {
  const body = UUID.test(caseId) ? workspaceOf(caseId, cookies) : undefined;
  return body ? { status: 200, check: 'workspace', body } : { status: 404, body: NOT_FOUND };
}

function history(caseId, url, cookies) {
  const params = url.searchParams;
  const purpose = params.get('purpose');
  const page = pageOf(params.get('page'));
  if (purpose !== 'billing' && purpose !== 'project') return { status: 400, body: BAD_REQUEST };
  if (page === null) return { status: 400, body: BAD_REQUEST };
  const base = UUID.test(caseId) ? workspaceOf(caseId, cookies) : undefined;
  if (!base) return { status: 404, body: NOT_FOUND };
  const customer = params.get('customer');
  const all = contactsOf(caseId)
    .filter((c) => c.purpose === purpose && (customer === null || c.customer === customer))
    .flatMap((c) => versionsOf(caseId, c));
  const p = slice(all, page);
  return { status: 200, check: 'history', body: { revision: base.revision, items: p.rows, next_page: p.next } };
}

const decode = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const GROUP_PATH = /^\/api\/v1\/clients\/groups\/([^/]+)$/;
const HISTORY_PATH = /^\/api\/v1\/clients\/([^/]+)\/contacts\/history$/;

/** The reads the v7 route table has no route for (the group page and the history). */
export const isClientsExtraPath = (pathname) => GROUP_PATH.test(pathname) || HISTORY_PATH.test(pathname);

export function clients({ url, persona, cookies = {} }) {
  if (persona === 'none') return { status: 403, body: FORBIDDEN };
  const { pathname } = url;
  let result;
  if (pathname === '/api/v1/clients') result = directory(url, cookies);
  else if (GROUP_PATH.test(pathname)) result = group(decode(GROUP_PATH.exec(pathname)[1]), url, cookies);
  else if (HISTORY_PATH.test(pathname)) result = history(decode(HISTORY_PATH.exec(pathname)[1]), url, cookies);
  else result = workspace(decode(pathname.split('/')[4] ?? ''), cookies);
  if (result.check) {
    const validate = validators[result.check];
    if (!validate(result.body)) throw new Error(`clients mock: ${result.check} reply is not valid: ${ajv.errorsText(validate.errors)}`);
  }
  return { status: result.status, body: result.body };
}

export function resetClients() {}
