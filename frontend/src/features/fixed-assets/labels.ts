// F-102: the fixed asset schedule reads (GET /work/{id}/assets) turned into the words and Section objects the workspace renderer
// draws. Presentation only: nothing here adds, subtracts, rounds or derives an amount, a date or a rate, decides access or invents
// a value. A null or missing amount is Unknown, never 0. Reviews are not built here (F-102B): who may review what is text only.
import type { ApiError } from '@/api/errors';
import type { LiveAssets } from '@/api/types';
import { formatDate, formatDayTime } from '@/components';
import { moneyCell, words } from '@/features/forecast/labels';
import type { Cell, Item, Section } from '@/features/workspace/labels';

export const UNAVAILABLE = 'This record is unavailable.';
export const NO_REGISTER = 'No register has been captured yet.';
export const NO_ASSETS = 'No assets in this register.';
export const NO_CHANGES = 'No changes in this period.';
export const NO_REVIEW = 'No review is open for you.';
export const DATE_UNCLEAR = 'Date unclear';

type Register = NonNullable<LiveAssets['register']>;
type Asset = Register['assets'][number];
type Schedule = NonNullable<LiveAssets['schedule']>;

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const present = (v: string | null | undefined): v is string => typeof v === 'string' && v.trim() !== '';
const textCell = (column: string, value: string | null | undefined): Cell => ({ column, text: present(value) ? value : '' });
const dateCell = (column: string, value: string | null | undefined): Cell => (present(value) && DAY.test(value) ? { column, date: { date: value, unknown: false } } : { column, date: { unknown: true } });
const dateWords = (value: string | null | undefined) => (present(value) ? formatDate(value) : 'Unknown');

const CAPITALISATION: Record<string, string> = { capitalise: 'Capitalise', undecided: 'Undecided' };
const COMPLETENESS: Record<string, string> = { complete: 'Complete', partial: 'Partial', unknown: 'Unknown' };
const KIND: Record<string, string> = { addition: 'Addition', disposal: 'Disposal', reclassification: 'Reclassification' };
const BASIS: Record<string, string> = { explicit_supplied_fraction: 'Supplied fraction', reviewed_in_service_date: 'Reviewed in-service date' };
const PURPOSE: Record<string, string> = { register: 'Register', basis: 'Basis', schedule: 'Schedule' };
const VERDICT: Record<string, string> = { approve: 'Approve', return: 'Return', reject: 'Reject', revoke: 'Revoke' };
const yesNo = (v: boolean | null | undefined) => (v === true ? 'Yes' : v === false ? 'No' : 'Unknown');
const pick = (table: Record<string, string>, key: string) => (Object.hasOwn(table, key) ? table[key] : words(key));

/** An asset whose dates are absent, or whose two dates are both empty, is unclear. */
export const isUnclear = (asset: Asset): boolean => !asset.dates || (!present(asset.dates.delivery_date) && !present(asset.dates.in_service_date));

/** The fact ids with a proof link: only those the read lists, each against the asset whose dates cite it. An id no asset cites is "other". */
export function proofLinks(a: Pick<LiveAssets, 'date_attachment_ids' | 'register'>): { factId: number; assetId: string | null }[] {
  const assets = a.register?.assets ?? [];
  return (a.date_attachment_ids ?? []).map((factId) => ({ factId, assetId: assets.find((x) => x.dates?.evidence_id === factId)?.asset_id ?? null }));
}

const stageSection = (a: LiveAssets): Section => ({
  key: 'stage',
  kind: 'text',
  title: 'Where it stands',
  items: [{ id: 'stage', text: `Stage: ${words(a.stage ?? '') || 'Not recorded'}` }, ...(present(a.finding) ? [{ id: 'finding', text: a.finding }] : [])],
});

function headerSection(r: Register, s: Schedule | null): Section {
  return {
    key: 'register',
    kind: 'facts',
    title: 'Register',
    coverage: `As of ${dateWords(r.label_as_of)}`,
    items: [
      { id: 'entity', label: 'Entity', value: r.entity },
      { id: 'provider', label: 'Provider', value: r.provider },
      { id: 'currency', label: 'Currency', value: r.currency },
      { id: 'period', label: 'Period', value: `${dateWords(r.period_start)} to ${dateWords(r.period_end)}` },
      { id: 'extracted', label: 'Extracted', value: present(r.extracted_at) ? formatDayTime(r.extracted_at) : 'Unknown' },
      { id: 'completeness', label: 'Completeness', value: pick(COMPLETENESS, r.completeness) },
      { id: 'native', label: 'Native source verified', value: yesNo(s?.native_source_verified) },
    ],
  };
}

function assetTable(r: Register): Section {
  if (r.assets.length === 0) return { key: 'assets', kind: 'text', title: 'Assets', items: [{ id: 'none', text: NO_ASSETS }] };
  return {
    key: 'assets',
    kind: 'table',
    title: 'Assets',
    columns: [
      { key: 'asset', label: 'Asset', kind: 'text' },
      { key: 'category', label: 'Category', kind: 'text' },
      { key: 'capitalisation', label: 'Capitalisation', kind: 'text' },
      { key: 'opening_cost', label: 'Opening cost', kind: 'money' },
      { key: 'opening_accumulated', label: 'Opening accumulated', kind: 'money' },
      { key: 'residual', label: 'Residual', kind: 'money' },
      { key: 'life', label: 'Life', kind: 'text' },
      { key: 'fraction', label: 'Fraction', kind: 'text' },
    ],
    items: r.assets.map((x): Item => ({
      id: x.asset_id,
      cells: [
        textCell('asset', x.asset_id),
        textCell('category', x.category),
        textCell('capitalisation', pick(CAPITALISATION, x.capitalisation)),
        moneyCell('opening_cost', x.opening_cost, r.currency),
        moneyCell('opening_accumulated', x.opening_accumulated, r.currency),
        moneyCell('residual', x.residual, r.currency),
        textCell('life', x.life),
        textCell('fraction', x.fraction),
      ],
    })),
  };
}

function eventTable(r: Register): Section {
  if (r.events.length === 0) return { key: 'events', kind: 'text', title: 'Changes in the period', items: [{ id: 'none', text: NO_CHANGES }] };
  return {
    key: 'events',
    kind: 'table',
    title: 'Changes in the period',
    columns: [
      { key: 'date', label: 'Date', kind: 'date' },
      { key: 'kind', label: 'Change', kind: 'text' },
      { key: 'asset', label: 'Asset', kind: 'text' },
      { key: 'cost', label: 'Cost change', kind: 'money' },
      { key: 'accumulated', label: 'Accumulated change', kind: 'money' },
    ],
    items: r.events.map((e): Item => ({
      id: e.event_id,
      cells: [dateCell('date', e.date), textCell('kind', pick(KIND, e.kind)), textCell('asset', e.asset_id), moneyCell('cost', e.cost_delta, r.currency), moneyCell('accumulated', e.accumulated_delta, r.currency)],
    })),
  };
}

const moneyItem = (id: string, label: string, value: string | null | undefined, currency: string): Item => ({ id, label, money: moneyCell('x', value, currency).money ?? { currency, unknown: true } });

const closingSection = (r: Register): Section => ({
  key: 'closing',
  kind: 'figures',
  title: 'Closing controls',
  items: [moneyItem('cost', 'Cost', r.closing_controls?.cost, r.currency), moneyItem('accumulated', 'Accumulated', r.closing_controls?.accumulated, r.currency), moneyItem('book', 'Book value', r.closing_controls?.book_value, r.currency)],
});

function dateSections(a: LiveAssets, r: Register): Section[] {
  const unclear = r.assets.filter(isUnclear);
  const dated = r.assets.filter((x) => !isUnclear(x));
  const out: Section[] = [];
  if (unclear.length > 0) out.push({ key: 'unclear', kind: 'text', title: 'Unclear dates', items: unclear.map((x) => ({ id: x.asset_id, text: `${x.asset_id} · ${DATE_UNCLEAR}` })) });
  if (dated.length > 0) {
    out.push({
      key: 'dates',
      kind: 'table',
      title: 'Dates on file',
      columns: [
        { key: 'asset', label: 'Asset', kind: 'text' },
        { key: 'delivery', label: 'Delivery date', kind: 'date' },
        { key: 'service', label: 'In service', kind: 'date' },
        { key: 'basis', label: 'Basis', kind: 'text' },
      ],
      items: dated.map((x): Item => ({ id: x.asset_id, cells: [textCell('asset', x.asset_id), dateCell('delivery', x.dates?.delivery_date), dateCell('service', x.dates?.in_service_date), textCell('basis', x.dates ? pick(BASIS, x.dates.fraction_basis) : '')] })),
    });
  }
  const proof: Item[] = [{ id: 'opening', text: a.has_opening_attachment ? 'Opening proof attached' : 'No opening proof attached' }];
  if (a.opening_return) proof.push({ id: 'returned', text: 'Returned for opening proof' });
  out.push({ key: 'proof', kind: 'text', title: 'Opening proof', items: proof });
  return out;
}

function scheduleSections(s: Schedule): Section[] {
  const currency = s.scope?.currency ?? '';
  const findings: Section[] = s.findings.length > 0 ? [{ key: 'schedule-findings', kind: 'text', title: s.status === 'held' ? 'Why the schedule is held' : 'Schedule findings', items: s.findings.map((f, i) => ({ id: `f${i}`, text: f })) }] : [];
  if (s.status === 'held') return [{ key: 'schedule-held', kind: 'text', title: 'Depreciation schedule', note: 'Held. No figures are shown until the reasons below are cleared.', items: [] }, ...findings];
  const noted = s.rows.filter((x) => x.findings.length > 0);
  return [
    {
      key: 'schedule',
      kind: 'table',
      title: 'Depreciation schedule',
      columns: [
        { key: 'asset', label: 'Asset', kind: 'text' },
        { key: 'category', label: 'Category', kind: 'text' },
        { key: 'cost', label: 'Closing cost', kind: 'money' },
        { key: 'charge', label: 'Charge', kind: 'money' },
        { key: 'accumulated', label: 'Closing accumulated', kind: 'money' },
        { key: 'book', label: 'Book value', kind: 'money' },
      ],
      items: s.rows.map((x): Item => ({
        id: x.asset_id,
        cells: [textCell('asset', x.asset_id), textCell('category', x.category), moneyCell('cost', x.closing_cost, currency), moneyCell('charge', x.charge, currency), moneyCell('accumulated', x.closing_accumulated, currency), moneyCell('book', x.book_value, currency)],
      })),
    },
    ...(noted.length > 0 ? [{ key: 'row-findings', kind: 'text' as const, title: 'Notes on rows', items: noted.flatMap((x) => x.findings.map((f, i): Item => ({ id: `${x.asset_id}-${i}`, text: `${x.asset_id}: ${f}` }))) }] : []),
    {
      key: 'totals',
      kind: 'figures',
      title: 'Schedule totals',
      items: [moneyItem('cost', 'Cost', s.totals?.cost, currency), moneyItem('charge', 'Charge', s.totals?.charge, currency), moneyItem('accumulated', 'Accumulated', s.totals?.accumulated, currency), moneyItem('book', 'Book value', s.totals?.book_value, currency)],
    },
    ...findings,
    {
      key: 'scope',
      kind: 'facts',
      title: 'Schedule scope',
      coverage: `As of ${dateWords(s.scope?.label_as_of)}`,
      items: [
        { id: 'entity', label: 'Entity', value: s.scope?.entity },
        { id: 'currency', label: 'Currency', value: s.scope?.currency },
        { id: 'period', label: 'Period', value: `${dateWords(s.scope?.period_start)} to ${dateWords(s.scope?.period_end)}` },
        { id: 'posted', label: 'Posted to the ledger', value: yesNo(s.ledger_posted) },
      ],
    },
  ];
}

function reviewSection(a: LiveAssets): Section {
  const lines: Item[] = (a.review_options ?? []).map((o, i) => ({ id: `r${i}`, text: `${pick(PURPOSE, o.purpose)} review: ${(o.verdicts ?? []).map((v) => pick(VERDICT, v)).join(', ') || 'no verdicts'}` }));
  return { key: 'reviews', kind: 'text', title: 'Who may review what', items: lines.length > 0 ? lines : [{ id: 'none', text: NO_REVIEW }] };
}

/** The whole page's sections from one assets read. The links (proof, accounting note) are drawn by the adapter's Actions. */
export function assetsSections(a: LiveAssets): Section[] {
  const out: Section[] = [stageSection(a)];
  const r = a.register;
  if (!r) {
    out.push({ key: 'no-register', kind: 'text', items: [{ id: 'none', text: NO_REGISTER }] });
  } else {
    out.push(headerSection(r, a.schedule), assetTable(r), eventTable(r), closingSection(r), ...dateSections(a, r));
  }
  if (a.schedule) out.push(...scheduleSections(a.schedule));
  out.push(reviewSection(a));
  return out;
}

/** The page's words for a failed read; null leaves it to the shared panel frame (its own Try again). */
export function errorWords(error: ApiError): string | null {
  switch (error.kind) {
    case 'unauthenticated':
      return 'Your session ended. Sign in again to continue.';
    case 'not_found':
    case 'forbidden':
      return UNAVAILABLE;
    case 'csrf':
      return 'Refresh your session and try again.';
    case 'stale':
    case 'invalid':
      return error.message;
    default:
      return null;
  }
}
