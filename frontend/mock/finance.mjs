// GET /api/v1/month-end in the contract mock (F-79, SCR-36), in the live 1.24.0 shape (contracts/psl-factory.openapi.json,
// operation finance_operations_company_close). The company close for 2026-10 from fixtures/finance/month-end.live.json
// (page 1) and month-end.page2.json (page 2). Finance only: pm and none are refused with 403; any other month answers 404.
// Cookie psl_mock_month_end picks a variant: empty (no work, counts 0), one-page (no next page), cash-unavailable (a
// workspace whose cash cannot be read), two-currency, more-cash (more_cash_groups), unnamed (a cash row with no workspace
// name), zero (one confirmed 0.00 row) or error (500). Every reply is validated against the live 200 schema. Sample data only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', 'finance', name), 'utf8'));
const page1 = read('month-end.live.json');
const page2 = read('month-end.page2.json');

const MONTH = '2026-10';
const NOT_FINANCE = { code: 'forbidden', message: 'Month-end is for Finance.' };
const SERVER = { code: 'server_error', message: 'The mock answered with a scripted server error.' };
const U = (n) => `00000000-0000-4000-8000-000000000${n}`;

const contract = JSON.parse(readFileSync(join(here, '..', '..', 'contracts', 'psl-factory.openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
export const validate = ajv.compile(contract.paths['/api/v1/month-end'].get.responses['200'].content['application/json'].schema);

const cashRow = (workspaceId, workspace, currency, amount) => ({ workspace_id: workspaceId, workspace, currency, basis: 'gross', amount, sample: true });
const workspace = (caseId, title, cashUnavailable) => ({
  month: MONTH, as_of: page1.as_of, workspace: { case_id: caseId, title, revision: 1, sample: true }, stations: [], cash: [],
  cash_unavailable: cashUnavailable, periods: [], receivables: { status: 'not_captured', cutoff: null, captured_date: null, snapshot_id: null }, can_capture: false,
});

const VARIANTS = {
  empty: (body) => ({ ...body, work: [], next_page: null, counts: { done: 0, waiting: 0, in_progress: 0, stopped: 0 } }),
  'one-page': (body) => ({ ...body, next_page: null }),
  'cash-unavailable': (body) => ({
    ...body,
    workspaces: [workspace(U(102), 'Harmattan Bank mobile onboarding', true)],
    cash: [body.cash[0], cashRow(U(102), 'Harmattan Bank mobile onboarding', 'NGN', '900000.00')],
  }),
  'two-currency': (body) => ({ ...body, cash: [body.cash[0], cashRow(U(102), 'Harmattan Bank mobile onboarding', 'USD', '12000.00')] }),
  'more-cash': (body) => ({ ...body, more_cash_groups: true }),
  unnamed: (body) => ({ ...body, cash: [body.cash[0], cashRow(null, null, 'NGN', '250000.00')] }),
  zero: (body) => ({ ...body, cash: [{ ...body.cash[0], amount: '0.00' }] }),
};

export function monthEnd({ url, persona, cookies = {} }) {
  if (persona === 'pm' || persona === 'none') return { status: 403, body: NOT_FINANCE };
  if ((url.searchParams.get('month') ?? MONTH) !== MONTH) return { status: 404, body: SCENARIO_BODIES[404] };
  const variant = cookies.psl_mock_month_end;
  if (variant === 'error') return { status: 500, body: SERVER };
  const page = Number(url.searchParams.get('page') ?? 1);
  const edit = Object.hasOwn(VARIANTS, variant ?? '') ? VARIANTS[variant] : (body) => body;
  const base = page === 2 && variant !== 'empty' && variant !== 'one-page' ? page2 : page1;
  const body = edit(base);
  if (!validate(body)) throw new Error(`month-end mock: reply is not valid: ${ajv.errorsText(validate.errors)}`);
  return { status: 200, body };
}
