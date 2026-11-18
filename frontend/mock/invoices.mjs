// E-INVOICES in the contract mock (F-41, SCR-20): the invoices list from fixtures/finance/invoices.<variant>.json, cookie
// psl_mock_invoices = board (default) | known | unknown | contract | empty | paged | error. Finance only: personas pm and
// none are refused with 403 (finance.read is the backend's grant; the mock only stands in for it). Sample data only.
//
// q matches the reference or the client (case-insensitive); status keeps the rows of that filter value (every row for
// "issued"); a status the filters do not name returns no rows. total is the number of matched rows, worked out here as
// the backend would; the page never counts. paged serves the board rows two per page with an "o<offset>" cursor.
//
// PROPOSAL (G-SCR20-1 to -6, not in v7): totals_detail, period, bank_data_as_of, coverage, agent_note and each row's
// overdue and milestone_label. `contractBody` strips them; every reply's stripped body is checked against the v7 schema.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', 'finance', `invoices.${name}.json`), 'utf8'));
const VARIANTS = Object.fromEntries(['board', 'known', 'unknown', 'empty'].map((name) => [name, read(name)]));

const PROPOSAL_KEYS = ['totals_detail', 'period', 'bank_data_as_of', 'coverage', 'agent_note'];
const ROW_PROPOSAL_KEYS = ['overdue', 'milestone_label'];
// Which rows each filter value keeps (the mock's own rule, standing in for the backend's).
const STATUS_ROWS = { issued: null, overdue: ['INV-0391'], part_paid: ['INV-0398'], paid: ['INV-0388'] };
const LIMITS = [10, 20, 50];
const PAGED_SIZE = 2;

const NOT_FINANCE = { code: 'forbidden', message: 'Payments are for Finance.' };
const SERVER = { code: 'server_error', message: 'The mock answered with a scripted server error.' };

const openapi = JSON.parse(readFileSync(join(here, '..', '..', 'architecture', 'packages', 'v7', 'openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(openapi.paths['/api/v1/finance/invoices'].get.responses['200'].content['application/json'].schema);

const without = (object, keys) => Object.fromEntries(Object.entries(object).filter(([name]) => !keys.includes(name)));

/** The body without the G-SCR20 proposal fields, top level and per row. */
export function contractBody(body) {
  if (!Array.isArray(body?.items)) return body;
  return { ...without(body, PROPOSAL_KEYS), items: body.items.map((row) => without(row, ROW_PROPOSAL_KEYS)) };
}

function variantBody(variant) {
  if (variant === 'contract') return { ...contractBody(VARIANTS.board), totals: { owed: { currency: 'NGN', unknown: true } } };
  if (variant === 'paged') return VARIANTS.board;
  return Object.hasOwn(VARIANTS, variant ?? '') ? VARIANTS[variant] : VARIANTS.board;
}

function matches(row, q, status) {
  if (q) {
    const needle = q.toLowerCase();
    if (!row.reference.toLowerCase().includes(needle) && !(row.client ?? '').toLowerCase().includes(needle)) return false;
  }
  if (status !== null) {
    if (!Object.hasOwn(STATUS_ROWS, status)) return false;
    if (STATUS_ROWS[status] !== null && !STATUS_ROWS[status].includes(row.invoice_id)) return false;
  }
  return true;
}

export function invoices({ url, persona, cookies = {} }) {
  if (persona === 'pm' || persona === 'none') return { status: 403, body: NOT_FINANCE };
  const variant = cookies.psl_mock_invoices;
  if (variant === 'error') return { status: 500, body: SERVER };
  const params = url.searchParams;
  const base = variantBody(variant);
  const rows = base.items.filter((row) => matches(row, params.get('q')?.trim() ?? '', params.has('status') ? params.get('status') : null));
  const limit = variant === 'paged' ? PAGED_SIZE : LIMITS.includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 20;
  const cursor = /^o(\d+)$/.exec(params.get('cursor') ?? '');
  const offset = cursor ? Number(cursor[1]) : 0;
  const body = { ...base, items: rows.slice(offset, offset + limit), total: base.total === undefined ? undefined : rows.length };
  if (body.total === undefined) delete body.total;
  delete body.next_cursor;
  if (offset + limit < rows.length) body.next_cursor = `o${offset + limit}`;
  if (!validate(contractBody(body))) throw new Error(`invoices mock: reply is not valid: ${ajv.errorsText(validate.errors)}`);
  return { status: 200, body };
}
