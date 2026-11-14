// E-MONTH-END in the contract mock: the month-end checklist for 2026-10 (fixtures/E-MONTH-END.json, the SCR-36
// desktop board's data). Finance only: pm and none are refused with 403; any other period answers 404.
// Cookie psl_mock_month_end picks a variant from fixtures/finance/: board-phone (the phone board's six cards, for
// the design-fidelity check), known (cash fully known), unknown (cash all Unknown), empty (no tasks), or contract
// (the default with the proposal fields removed: a pure v4 body). Sample data only.
//
// Engineering proposal D-MONTH-END-VIEW r1 (v7 proposal, not in v4): the body carries as_of, coverage, summary,
// cash_received_detail, agent_note and next_action, and each task title, detail, status_label, tone, restricted and
// restricted_label. `contractBody` strips them so tests can check the rest against the v4 schema.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', name), 'utf8'));
const fixture = read('E-MONTH-END.json');
const VARIANTS = Object.fromEntries(
  ['board-phone', 'known', 'unknown', 'empty'].map((name) => [name, read(`finance/month-end.${name}.json`)]),
);

const PERIOD = '2026-10';
const NOT_FINANCE = { code: 'forbidden', message: 'Month-end is for Finance.' };
const PROPOSAL_KEYS = ['as_of', 'coverage', 'summary', 'cash_received_detail', 'agent_note', 'next_action'];
const TASK_PROPOSAL_KEYS = ['title', 'detail', 'status_label', 'tone', 'restricted', 'restricted_label'];

const without = (object, keys) => Object.fromEntries(Object.entries(object).filter(([name]) => !keys.includes(name)));

/** The body without the D-MONTH-END-VIEW proposal fields, top level and per task. */
export function contractBody(body) {
  if (!Array.isArray(body?.tasks)) return body;
  return { ...without(body, PROPOSAL_KEYS), tasks: body.tasks.map((task) => without(task, TASK_PROPOSAL_KEYS)) };
}

export function monthEnd({ url, persona, cookies }) {
  if (persona === 'pm' || persona === 'none') return { status: 403, body: NOT_FINANCE };
  if (url.searchParams.getAll('period').join(',') !== PERIOD) return { status: 404, body: SCENARIO_BODIES[404] };
  const variant = cookies.psl_mock_month_end;
  if (variant === 'contract') return { status: 200, body: contractBody(fixture) };
  return { status: 200, body: Object.hasOwn(VARIANTS, variant ?? '') ? VARIANTS[variant] : fixture };
}
