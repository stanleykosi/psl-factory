// Setup rules mock (E-SETUP-RULES, E-SETUP-RULE-SAVE) for F-11. Sample data only; no value is PSL's policy.
// Rows and bodies follow the contract overlay in proposals/setup.json (v7 D-SETUP-RULES-VIEW r1 plus proof_case).
//
// Scenario: cookie psl_mock_setup = desktop (default) | mobile | readonly | empty | forbidden | many; data comes from
// fixtures/setup/<area>.<desktop|mobile>.json, where <area> is rules (no area), finance or delivery.
// Save: cookie psl_mock_setup_save = stale (another person saves first, then 409) | invalid (422 naming reason, starts).
// pm and none get 403 on every setup call. can_change comes from the data, never from the persona.
// A save is kept as an in-memory override per persona:scenario:component; resetSetup() clears it.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const OVERLAY = JSON.parse(readFileSync(join(here, 'proposals', 'setup.json'), 'utf8'));

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validateSave = ajv.compile(OVERLAY.save_body);

export const SETUP_DENIED = new Set(['pm', 'none']);
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const SCENARIOS = ['desktop', 'mobile', 'readonly', 'empty', 'forbidden', 'many'];
const AREAS = ['rules', 'finance', 'delivery'];
const PAGE_SIZE = 50;
const AS_OF = '2026-11-12T10:40:00+01:00';

const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', 'setup', `${name}.json`), 'utf8'));
const DATA = Object.fromEntries(AREAS.map((area) => [area, { desktop: read(`${area}.desktop`), mobile: read(`${area}.mobile`) }]));

// persona:scenario:component -> the saved fields; persona:case_id -> current case revision (shared with evidence.mjs).
const overrides = new Map();
export const caseRevisions = new Map();

export function resetSetup() {
  overrides.clear();
  caseRevisions.clear();
}

// MOCK_SETUP_SCENARIO sets the default for a whole mock run. The design-fidelity tool scopes its cookies to the
// page's folder (/setup/rules/), so they never reach /api/v1; its phone boards run against a mock started this way.
const DEFAULT_SCENARIO = SCENARIOS.includes(process.env.MOCK_SETUP_SCENARIO) ? process.env.MOCK_SETUP_SCENARIO : 'desktop';
export const setupScenario = (cookies) => (SCENARIOS.includes(cookies.psl_mock_setup) ? cookies.psl_mock_setup : DEFAULT_SCENARIO);

function manyRows() {
  return Array.from({ length: 55 }, (_, i) => ({
    component: `sample.rule_${String(i + 1).padStart(2, '0')}`,
    name: `Sample rule ${i + 1}`,
    set: false,
    revision: 0,
    area: 'pre_sale',
    area_label: 'Pre-sale',
    holds_work: true,
    can_change: false,
    editor: { kind: 'read_only' },
  }));
}

/** Every row of one area in a scenario, before overrides, with the page-level counts. */
function baseData(scenario, area) {
  if (scenario === 'empty') return { items: [], as_of: AS_OF, not_set_count: 0 };
  if (scenario === 'many') return { items: manyRows(), as_of: AS_OF, not_set_count: 55 };
  const data = DATA[area][scenario === 'mobile' ? 'mobile' : 'desktop'];
  if (scenario !== 'readonly') return data;
  return { ...data, items: data.items.map((row) => ({ ...row, can_change: false })) };
}

/** The rows as served now: saved overrides applied, proof cases at their current revision, count lowered per save. */
function currentData(persona, scenario, area) {
  const base = baseData(scenario, area);
  let saved = 0;
  const items = base.items.map((row) => {
    let next = row;
    const override = overrides.get(`${persona}:${scenario}:${row.component}`);
    if (override) {
      if (!row.set) saved += 1;
      next = { ...row, ...override.fields, editor: { ...row.editor, selected: override.roles } };
    }
    if (next.proof_case) {
      const revision = caseRevisions.get(`${persona}:${next.proof_case.case_id}`);
      if (revision !== undefined) next = { ...next, proof_case: { ...next.proof_case, case_revision: revision } };
    }
    return next;
  });
  const body = { ...base, items };
  if (base.not_set_count !== undefined) body.not_set_count = Math.max(0, base.not_set_count - saved);
  return body;
}

/** All rows a scenario serves in any area (one entry per component). */
function scenarioRows(persona, scenario) {
  const rows = new Map();
  for (const area of AREAS) for (const row of currentData(persona, scenario, area).items) if (!rows.has(row.component)) rows.set(row.component, row);
  return rows;
}

export function proofCaseRevision(persona, scenario, caseId) {
  for (const row of scenarioRows(persona, scenario).values()) {
    if (row.proof_case?.case_id === caseId) return row.proof_case.case_revision;
  }
  return undefined;
}

export function setupRules({ url, persona, cookies }) {
  const scenario = setupScenario(cookies);
  if (SETUP_DENIED.has(persona) || scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  const area = url.searchParams.get('area') ?? 'rules';
  if (!AREAS.includes(area) || url.searchParams.get('area') === 'rules') return { status: 200, body: { items: [], as_of: AS_OF } };
  const data = currentData(persona, scenario, area);
  const match = /^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '');
  const offset = match && Number(match[1]) < data.items.length ? Number(match[1]) : 0;
  const body = { ...data, items: data.items.slice(offset, offset + PAGE_SIZE) };
  if (offset + PAGE_SIZE < data.items.length) body.next_cursor = `o:${offset + PAGE_SIZE}`;
  return { status: 200, body };
}

const invalid = (fields) => ({ status: 422, body: { code: 'invalid', message: `Check these fields: ${[...new Set(fields)].join(', ')}.` } });

function errorFields(errors) {
  return errors.map((e) => {
    const path = e.instancePath.split('/').filter(Boolean);
    return e.params.missingProperty ?? e.params.additionalProperty ?? (path.join('.') || 'body');
  });
}

export function saveSetupRule({ url, raw, persona, cookies }) {
  if (SETUP_DENIED.has(persona)) return { status: 403, body: FORBIDDEN };
  const scenario = setupScenario(cookies);
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid(['body']);
  }
  if (!validateSave(body)) return invalid(errorFields(validateSave.errors));
  const component = decodeURIComponent(url.pathname.split('/')[5] ?? '');
  const row = scenarioRows(persona, scenario).get(component);
  if (!row) return { status: 404, body: NOT_FOUND };
  const options = row.editor?.options ?? [];
  if (row.can_change !== true || row.editor?.kind !== 'role_set') return { status: 403, body: FORBIDDEN };
  const key = `${persona}:${scenario}:${component}`;
  if (cookies.psl_mock_setup_save === 'invalid') return invalid(['reason', 'starts']);
  if (cookies.psl_mock_setup_save === 'stale') {
    const other = options.find((o) => o.role === 'pmo_lead') ?? options[0];
    store(key, row, [other.role], options, body.starts);
    return { status: 409, body: SCENARIO_BODIES[409] };
  }
  if (body.expected_revision !== row.revision) return { status: 409, body: SCENARIO_BODIES[409] };
  const roles = body.value.roles;
  const known = new Set(options.map((o) => o.role));
  if (!Array.isArray(roles) || !roles.every((role) => typeof role === 'string' && known.has(role))) return invalid(['value.roles']);
  const revision = store(key, row, roles, options, body.starts);
  return { status: 200, body: { component, revision } };
}

function store(key, row, roles, options, starts) {
  const revision = row.revision + 1;
  const labels = options.filter((o) => roles.includes(o.role)).map((o) => o.label);
  const day = starts ?? new Date().toISOString().slice(0, 10);
  const fields = { set: true, revision, value: { roles: [...roles] }, effective_from: `${day}T00:00:00+01:00`, holds_work: false };
  if (labels.length > 0) fields.display_value = labels.join(', ');
  overrides.set(key, { fields, roles: [...roles] });
  return revision;
}

const CORE_ROW = ['component', 'name', 'value', 'set', 'revision'];

/** The v4 core of a rules page: proposal row fields and counts removed. */
export function contractRules(body) {
  const rest = { ...body };
  delete rest.not_set_count;
  delete rest.roles_missing_count;
  return {
    ...rest,
    items: body.items.map((row) => Object.fromEntries(Object.entries(row).filter(([name]) => CORE_ROW.includes(name)))),
  };
}
