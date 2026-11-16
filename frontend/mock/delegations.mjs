// Delegation mock (E-DELEGATIONS, E-DELEGATION) for F-27. Sample names only; nothing here is PSL policy. Built on
// D-DELEGATION-VIEW, still a proposal, with the overlay in proposals/setup.json (delegations_response,
// delegation_body): from_options and from_person_id (G-SCR13A-1), delegate_options[].for_person_id (G-SCR13A-2),
// list-level can_add, the 200's delegation_id (G-SCR13A-4) and expected_revision 0. The cursor query is v7's.
//
// Scenario: cookie psl_mock_delegations = default | empty | readonly | forbidden | many | authority | single.
// Save: cookie psl_mock_delegations_save = stale (another person adds first, then 409) | invalid (422 naming delegate
// and ends) | uncertain (500, nothing written) | uncertain_written (written, then 500).
// pm and none get 403 on both calls. can_add and every option come from the data, never from the persona.
// The only place a status is worked out from dates is a new row here, against the mock clock (2026-11-16).
// Added rows and the bumped revision are kept in memory per persona:scenario; resetDelegations() clears them.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const STALE = { code: 'stale_revision', message: 'The delegations changed. Reload to see the latest list.' };
const SERVER = { code: 'server_error', message: 'Something went wrong on our side.' };
const DENIED = new Set(['pm', 'none']);
const SCENARIOS = ['default', 'empty', 'readonly', 'forbidden', 'many', 'authority', 'single'];
const PAGE_SIZE = 20;
const TODAY = '2026-11-16';

const read = (path) => JSON.parse(readFileSync(join(here, path), 'utf8'));
const DATA = Object.fromEntries(SCENARIOS.filter((s) => s !== 'forbidden').map((name) => [name, read(`fixtures/delegations/${name}.json`)]));
const OVERLAY = read('proposals/setup.json');
const personName = (persona) => read(`fixtures/me.${persona}.json`).name;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validBody = ajv.compile(OVERLAY.delegation_body);

// persona:scenario -> { added: rows, revision }
const state = new Map();

export function resetDelegations() {
  state.clear();
}

// MOCK_DELEGATIONS_SCENARIO sets the default for a whole mock run: the design-fidelity tool scopes its cookies to the
// page's folder (/setup/delegation/), so they never reach /api/v1.
const DEFAULT_SCENARIO = SCENARIOS.includes(process.env.MOCK_DELEGATIONS_SCENARIO) ? process.env.MOCK_DELEGATIONS_SCENARIO : 'default';
const scenarioOf = (cookies) => (SCENARIOS.includes(cookies.psl_mock_delegations) ? cookies.psl_mock_delegations : DEFAULT_SCENARIO);
const dataOf = (scenario) => DATA[scenario === 'forbidden' ? 'default' : scenario];

function current(persona, scenario) {
  const key = `${persona}:${scenario}`;
  if (!state.has(key)) state.set(key, { added: [], revision: dataOf(scenario).revision });
  return state.get(key);
}

export function delegationsList({ url, persona, cookies }) {
  const scenario = scenarioOf(cookies);
  if (DENIED.has(persona) || scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  const data = dataOf(scenario);
  const now = current(persona, scenario);
  const rows = [...data.items, ...now.added];
  const match = /^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '');
  const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
  const body = { ...data, items: rows.slice(offset, offset + PAGE_SIZE) };
  if (now.revision !== undefined) body.revision = now.revision;
  if (offset + PAGE_SIZE < rows.length) body.next_cursor = `o:${offset + PAGE_SIZE}`;
  return { status: 200, body };
}

const invalid = (fields) => ({
  status: 422,
  body: { code: 'invalid', message: `Check these fields: ${fields.map((f) => f.name).join(', ')}.`, fields },
});

const FIELD_MESSAGES = {
  expected_revision: 'Send the revision you read.',
  delegate: 'Choose who to delegate to.',
  from_person_id: 'Choose who is delegating.',
  starts: 'Enter the start date.',
  ends: 'Enter the end date.',
  authority: 'Choose an authority.',
  reason: 'Write a reason or leave it out.',
};

/** The overlay schema's errors as one problem per field, in body order. */
function schemaProblems(body) {
  if (validBody(body)) return [];
  const names = [];
  for (const error of validBody.errors ?? []) {
    const name = error.params.additionalProperty ?? error.params.missingProperty ?? error.instancePath.split('/')[1] ?? 'body';
    if (!names.includes(name)) names.push(name);
  }
  return names.map((name) => ({ name, message: FIELD_MESSAGES[name] ?? 'Not part of a delegation.' }));
}

/** The delegate options open to this From: paired by for_person_id when the data pairs them, else all of them. */
function delegatesFor(data, fromId) {
  const options = data.delegate_options ?? [];
  if (!options.some((o) => o.for_person_id !== undefined)) return options;
  return options.filter((o) => o.for_person_id === undefined || o.for_person_id === fromId);
}

const statusOn = (starts, ends) => (starts > TODAY ? 'scheduled' : ends !== undefined && ends < TODAY ? 'ended' : 'active');
const person = ({ person_id, name, role }) => (role ? { person_id, name, role } : { person_id, name });

export function saveDelegation({ raw, persona, cookies }) {
  const scenario = scenarioOf(cookies);
  if (DENIED.has(persona) || scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid([{ name: 'body', message: 'Send a JSON object.' }]);
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return invalid([{ name: 'body', message: 'Send a JSON object.' }]);
  const problems = schemaProblems(body);
  if (problems.length > 0) return invalid(problems);
  if (body.ends < body.starts) return invalid([{ name: 'ends', message: "Ends can't be before Starts." }]);
  const save = cookies.psl_mock_delegations_save;
  if (save === 'invalid') {
    return invalid([
      { name: 'delegate', message: 'This person can’t take this delegation.' },
      { name: 'ends', message: 'Choose an end date within the next 90 days.' },
    ]);
  }

  const data = dataOf(scenario);
  const fromOptions = data.from_options ?? [];
  let from;
  if (body.from_person_id !== undefined) {
    from = fromOptions.find((o) => o.person_id === body.from_person_id);
    if (!from) return invalid([{ name: 'from_person_id', message: 'Choose who is delegating from the list.' }]);
  } else if (fromOptions.length === 1) {
    from = fromOptions[0];
  } else if (fromOptions.length > 1) {
    return invalid([{ name: 'from_person_id', message: 'Choose who is delegating.' }]);
  }
  const delegate = delegatesFor(data, from?.person_id).find((o) => o.person_id === body.delegate);
  if (!delegate) return invalid([{ name: 'delegate', message: 'Choose a delegate from the list.' }]);
  const authorities = data.authorities ?? [];
  if (body.authority !== undefined && !authorities.some((a) => a.value === body.authority)) {
    return invalid([{ name: 'authority', message: 'Choose an authority from the list.' }]);
  }

  const now = current(persona, scenario);
  if (save === 'stale') {
    now.revision += 1;
    return { status: 409, body: STALE };
  }
  if (body.expected_revision !== now.revision) return { status: 409, body: STALE };
  if (data.can_add !== true) return { status: 403, body: FORBIDDEN };
  if (save === 'uncertain') return { status: 500, body: SERVER };

  const id = `DL-${String(9001 + now.added.length).padStart(4, '0')}`;
  const row = {
    delegation_id: id,
    from: from ? person(from) : { name: personName(persona), is_you: true },
    delegate: person(delegate),
    starts: body.starts,
    ends: body.ends,
    status: statusOn(body.starts, body.ends),
    can_change: true,
    revision: 1,
  };
  if (body.authority !== undefined) row.authority = body.authority;
  if (body.reason !== undefined) row.reason = body.reason;
  now.added.push(row);
  now.revision += 1;
  if (save === 'uncertain_written') return { status: 500, body: SERVER };
  return { status: 200, body: { revision: now.revision, delegation_id: id } };
}

/** The v7 E-DELEGATIONS 200 body: the overlay fields removed (mock-contract.test.ts checks the rest). */
export function contractDelegations(body) {
  const core = ({ name, role, is_you }) => Object.fromEntries(Object.entries({ name, role, is_you }).filter(([, v]) => v !== undefined));
  const rest = { ...body };
  delete rest.can_add;
  delete rest.from_options;
  if (rest.delegate_options) rest.delegate_options = rest.delegate_options.map(({ person_id, name, role }) => (role ? { person_id, name, role } : { person_id, name }));
  return { ...rest, items: body.items.map((row) => ({ ...row, from: core(row.from), delegate: core(row.delegate) })) };
}

/** The v7 E-DELEGATION 200 body: delegation_id (G-SCR13A-4) removed. */
export function contractDelegation(body) {
  const rest = { ...body };
  delete rest.delegation_id;
  return rest;
}
