// GET /api/v1/payments in the contract mock (F-79, SCR-20), in the live 1.24.0 shape (contracts/psl-factory.openapi.json,
// operation finance_operations_payments). The invoices list from fixtures/finance/invoices.<variant>.json, cookie
// psl_mock_invoices = board (default) | known | unknown | empty | paged | limited | currencies | links | error. Finance only:
// personas pm and none are refused with 403 (the mock only stands in for the backend's grant). Sample data only.
//
// q matches the reference or the customer (case-insensitive); state keeps the rows of that status. paged serves the board
// rows two per page with an opaque "c<page>" cursor. Every reply is validated against the live 200 schema.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', 'finance', `invoices.${name}.json`), 'utf8'));
const VARIANTS = Object.fromEntries(['board', 'known', 'unknown', 'empty'].map((name) => [name, read(name)]));
const PAGED_SIZE = 2;
const STATES = ['issued', 'part-paid', 'overdue', 'paid', 'unknown'];

const NOT_FINANCE = { code: 'forbidden', message: 'Payments are for Finance.' };
const SERVER = { code: 'server_error', message: 'The mock answered with a scripted server error.' };

const contract = JSON.parse(readFileSync(join(here, '..', '..', 'contracts', 'psl-factory.openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
export const validate = ajv.compile(contract.paths['/api/v1/payments'].get.responses['200'].content['application/json'].schema);

const EXTRA = {
  limited: (body) => ({ ...body, limited: true }),
  // two currencies: the totals and the received figures carry one entry each, never added together
  currencies: (body) => ({
    ...body,
    totals: [...body.totals, { currency: 'USD', basis: 'gross', owed: '12000.00', overdue: '0.00', known_owed: '12000.00', unknown_owed_count: 0 }],
    received_this_month: { ...body.received_this_month, totals: [...body.received_this_month.totals, { currency: 'USD', basis: 'net', amount: '3000.00' }] },
  }),
  links: (body) => ({ ...body, items: body.items.map((row) => ({ ...row, record_payment_url: null, review_payment_url: null, reminder_url: null })) }),
};

function variantBody(variant) {
  if (Object.hasOwn(EXTRA, variant ?? '')) return EXTRA[variant](VARIANTS.board);
  return Object.hasOwn(VARIANTS, variant ?? '') ? VARIANTS[variant] : VARIANTS.board;
}

function matches(row, q, state) {
  if (q) {
    const needle = q.toLowerCase();
    if (!row.reference.toLowerCase().includes(needle) && !row.customer.toLowerCase().includes(needle)) return false;
  }
  return state === null || row.status === state;
}

export function invoices({ url, persona, cookies = {} }) {
  if (persona === 'pm' || persona === 'none') return { status: 403, body: NOT_FINANCE };
  const variant = cookies.psl_mock_invoices;
  if (variant === 'error') return { status: 500, body: SERVER };
  const params = url.searchParams;
  const state = params.get('state');
  const base = variantBody(variant);
  const rows = base.items.filter((row) => matches(row, params.get('q')?.trim() ?? '', STATES.includes(state) ? state : null));
  const size = variant === 'paged' ? PAGED_SIZE : rows.length;
  const page = /^c(\d+)$/.exec(params.get('cursor') ?? '');
  const offset = page ? (Number(page[1]) - 1) * size : 0;
  const body = { ...base, items: rows.slice(offset, offset + size), cursor: offset + size < rows.length ? `c${Math.floor(offset / size) + 2}` : null };
  if (!validate(body)) throw new Error(`invoices mock: reply is not valid: ${ajv.errorsText(validate.errors)}`);
  return { status: 200, body };
}
