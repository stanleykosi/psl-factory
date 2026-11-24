// F-103: the cash forecast reads (GET /work/{id}/forecast) turned into the words and Section objects the
// workspace renderer draws. Presentation only: nothing here adds, subtracts or rounds an amount, decides access, or invents a
// value. A missing, null or malformed amount is Unknown, never 0. Group view (audience 'group') draws only what the disclosure
// lists, and an entry that is an object keeps only its label or key (E-26: no staff name or individual pay).
import type { ApiError } from '@/api/errors';
import type { LiveForecast } from '@/api/types';
import { formatDate } from '@/components';
import type { Cell, Item, Section } from '@/features/workspace/labels';

export const UNAVAILABLE = 'This record is unavailable.';
export const NO_FIGURES = 'No forecast figures yet.';
export const NO_MATCHES = 'No actuals matched yet.';
export const NOT_RESENT = 'Nothing has been resent from this page.';

type Obj = Record<string, unknown>;
type Result = NonNullable<LiveForecast['result']>;

const obj = (v: unknown): Obj | null => (typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Obj) : null);
const text = (v: unknown): string | null => (typeof v === 'string' && v.trim() !== '' ? v : typeof v === 'number' ? String(v) : null);
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const DECIMAL = /^-?\d+\.\d{2}$/;
const NUMERIC = /^-?\d+(\.\d+)?$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

/** "needs_review" as "Needs review". */
export const words = (raw: string) => {
  const spaced = raw.replace(/[_-]+/g, ' ').trim();
  return spaced ? spaced[0].toUpperCase() + spaced.slice(1) : '';
};

const AUDIENCE_WORDS: Record<string, string> = { internal: 'Internal', management: 'Management', group: 'Group' };
export const audienceWords = (audience: string) => (Object.hasOwn(AUDIENCE_WORDS, audience) ? AUDIENCE_WORDS[audience] : audience);

/** One amount cell: the backend's decimal string as given; null, missing or not a number reads Unknown. */
export function moneyCell(column: string, value: unknown, currency: string | null): Cell {
  const raw = text(value);
  if (raw === null || !currency) return { column, money: { currency: currency ?? '', unknown: true } };
  if (DECIMAL.test(raw)) return { column, money: { amount: raw, currency, unknown: false } };
  // a number the formatter does not take (other precision) is shown as sent, never as Unknown
  return NUMERIC.test(raw) ? { column, text: `${currency} ${raw}` } : { column, money: { currency, unknown: true } };
}

const dateCell = (column: string, value: unknown): Cell => (typeof value === 'string' && DAY.test(value) ? { column, date: { date: value, unknown: false } } : { column, date: { unknown: true } });
const textCell = (column: string, value: unknown): Cell => ({ column, text: text(value) ?? '' });
const itemMoney = (value: unknown, currency: string | null): Item['money'] => moneyCell('x', value, currency).money ?? { currency: currency ?? '', unknown: true };

const PERIOD_COLUMNS = [
  ['opening', 'Opening'],
  ['inflow', 'In'],
  ['outflow', 'Out'],
  ['closing', 'Closing'],
] as const;

/** The forecast months: one row per recognised period, a column only where a period carries the field.
 *  A period the mapper does not recognise is listed by its keys (in group view only the fact that one is not shown). */
export function periodSections(result: Result, group: boolean): Section[] {
  const known: Obj[] = [];
  const other: string[] = [];
  list(result.periods).forEach((p) => {
    const o = obj(p);
    if (o && text(o.month) !== null) known.push(o);
    else other.push(group ? 'A period is not shown here.' : `Period data: ${o ? Object.keys(o).join(', ') || 'no fields' : 'not recognised'}`);
  });
  const out: Section[] = [];
  const currency = result.currency || null;
  if (known.length > 0) {
    const shown = PERIOD_COLUMNS.filter(([key]) => known.some((o) => key in o));
    out.push({
      key: 'periods',
      kind: 'table',
      title: 'Forecast months',
      columns: [{ key: 'month', label: 'Month', kind: 'text' }, ...shown.map(([key, label]) => ({ key, label, kind: 'money' as const }))],
      items: known.map((o, i): Item => ({ id: `p${i}`, cells: [textCell('month', o.month), ...shown.map(([key]) => moneyCell(key, o[key], currency))] })),
    });
  }
  if (other.length > 0) out.push({ key: 'periods-other', kind: 'text', ...(known.length > 0 ? {} : { title: 'Forecast months' }), items: other.map((t, i) => ({ id: `o${i}`, text: t })) });
  return out;
}

function itemSection(result: Result): Section[] {
  const rows = list(result.items).map(obj).filter((o): o is Obj => o !== null);
  if (rows.length === 0) return [];
  const currency = result.currency || null;
  return [
    {
      key: 'expected-items',
      kind: 'table',
      title: 'Expected items',
      columns: [
        { key: 'key', label: 'Item', kind: 'text' },
        { key: 'kind', label: 'Kind', kind: 'text' },
        { key: 'expected_on', label: 'Expected on', kind: 'date' },
        { key: 'matched', label: 'Matched', kind: 'money' },
        { key: 'residual', label: 'Residual', kind: 'money' },
      ],
      items: rows.map((o, i): Item => ({
        id: `i${i}`,
        cells: [textCell('key', o.key ?? o.label), textCell('kind', o.kind), dateCell('expected_on', o.expected_on), moneyCell('matched', o.matched, currency), moneyCell('residual', o.residual, currency)],
      })),
    },
  ];
}

const findingText = (f: unknown): string => text(f) ?? text(obj(f)?.text) ?? text(obj(f)?.message) ?? (obj(f) ? Object.keys(obj(f)!).join(', ') : 'Not recognised');

function findingSection(result: Result): Section[] {
  const findings = list(result.findings);
  return findings.length === 0 ? [] : [{ key: 'findings', kind: 'text', title: 'Findings', items: findings.map((f, i) => ({ id: `f${i}`, text: findingText(f) })) }];
}

const directionWords = (d: unknown) => (d === 'outflow' ? 'Out' : d === 'inflow' ? 'In' : 'Direction not recorded');

/** Matches and the actuals the forecast carries; none at all reads "No actuals matched yet.". */
function actualSection(f: LiveForecast): Section {
  const currency = f.result?.currency || null;
  const matches: Item[] = list(f.matches)
    .map(obj)
    .filter((o): o is Obj => o !== null)
    .map((m, i) => ({ id: `m${i}`, label: `Item ${text(m.item_key) ?? ''} · Actual ${text(m.actual_id) ?? ''}`, money: itemMoney(m.amount, currency) }));
  const carried: Item[] = list(f.result?.actuals)
    .map(obj)
    .filter((o): o is Obj => o !== null)
    .map((a, i) => ({ id: `a${i}`, label: `Actual ${text(a.id) ?? ''} · ${directionWords(a.direction)}`, money: itemMoney(a.amount, currency), detail: a.verified === true ? 'Verified' : 'Not verified' }));
  const items = [...matches, ...carried];
  return items.length === 0
    ? { key: 'matches', kind: 'text', title: 'Actuals in the forecast', items: [{ id: 'none', text: NO_MATCHES }] }
    : { key: 'matches', kind: 'figures', title: 'Actuals in the forecast', items };
}

/** An entry of a disclosure list as words: a string or number as sent; an object only by its label or key; else the fallback. */
export function entryText(v: unknown, fallback: string): string {
  const o = obj(v);
  return text(v) ?? (o ? (text(o.label) ?? text(o.key)) : null) ?? fallback;
}

/** The group's version, as the API sent it: nothing is derived from another read. */
function disclosureSections(d: NonNullable<LiveForecast['disclosure']>): Section[] {
  const texts = (title: string, key: string, entries: unknown[], label: string): Section[] =>
    entries.length === 0 ? [] : [{ key, kind: 'text', title, items: entries.map((e, i) => ({ id: `${key}${i}`, text: entryText(e, `${label} ${i + 1}`) })) }];
  const recipients = list(d.recipient_ids);
  const choice = (c: unknown) => {
    const o = obj(c);
    return o ? `${text(o.kind) ?? 'Choice'}${text(o.version) ? ` version ${text(o.version)}` : ''}` : c;
  };
  return [
    ...texts('Rows shared with the group', 'disclosure-rows', list(d.selected_rows), 'Row'),
    ...texts('Fields shared', 'disclosure-fields', list(d.selected_fields), 'Field'),
    ...texts('Details shared', 'disclosure-metadata', list(d.selected_metadata), 'Detail'),
    ...(recipients.length > 0 ? [{ key: 'disclosure-recipients', kind: 'recipients' as const, title: 'Recipients', items: recipients.map((id, i): Item => ({ id: `r${i}`, text: `Recipient ${text(id) ?? i + 1}` })) }] : []),
    ...texts('Available', 'disclosure-available', list(d.row_keys), 'Row'),
    ...texts('Choices on file', 'disclosure-choices', [...list(d.oracle_choices), ...list(d.decision_choices)].map(choice), 'Choice'),
  ];
}

const UNCERTAIN_JOB = new Set(['sent', 'sending', 'unknown', 'uncertain']);
/** Uncertain: the recorded outcome is unknown; or no outcome is recorded and a job sits in a sent, not-confirmed state; or the stage says so. */
export function isUncertain(f: LiveForecast): boolean {
  if (f.observation?.outcome === 'unknown') return true;
  if (!f.observation && list(f.jobs).some((j) => UNCERTAIN_JOB.has(String(obj(j)?.status)))) return true;
  return /uncertain/i.test(f.stage ?? '');
}

const OUTCOME_WORDS: Record<string, string> = { delivered: 'Recorded as delivered', not_delivered: 'Recorded as not delivered', unknown: 'Outcome not known' };
export const outcomeWords = (outcome: string) => (Object.hasOwn(OUTCOME_WORDS, outcome) ? OUTCOME_WORDS[outcome] : outcome);

function deliverySections(f: LiveForecast): Section[] {
  const items: Item[] = list(f.jobs)
    .map(obj)
    .filter((j): j is Obj => j !== null)
    .map((j) => {
      const receipts = list(j.receipt_ids);
      return {
        id: `j${text(j.id)}`,
        text: `Job ${text(j.id) ?? ''} · ${text(j.status) ?? 'status not recorded'}`,
        detail: [receipts.length === 0 ? 'No receipt yet' : receipts.map((n) => `Receipt ${text(n)}`).join(', '), j.can_retry === true ? 'Can be retried' : null, j.can_operate === true ? 'Can be operated' : null].filter(Boolean).join(' · '),
      };
    });
  if (f.observation) items.push({ id: 'observation', text: outcomeWords(f.observation.outcome) });
  if (f.can_restart) items.push({ id: 'restart', text: f.restart_policy_id === null || f.restart_policy_id === undefined ? 'Restart allowed' : `Restart allowed under rule ${f.restart_policy_id}` });
  const out: Section[] = [];
  if (isUncertain(f)) out.push({ key: 'uncertain', kind: 'text', note: `We can’t confirm this was delivered. ${NOT_RESENT}`, items: [] });
  if (items.length > 0) out.push({ key: 'delivery', kind: 'text', title: 'Delivery', items });
  return out;
}

/** The whole page's sections from one forecast read. */
export function forecastSections(f: LiveForecast): Section[] {
  const group = f.audience === 'group';
  const r = f.result;
  const facts: Item[] = [
    ...(r
      ? [
          { id: 'entity', label: 'Entity', value: r.entity },
          { id: 'currency', label: 'Currency', value: r.currency },
          { id: 'basis', label: 'Basis', value: r.basis },
          { id: 'status', label: 'Status', value: words(r.status ?? '') },
        ]
      : []),
    { id: 'audience', label: 'Audience', value: audienceWords(f.audience) },
  ];
  const stage: Item[] = [{ id: 'stage', text: `Stage: ${words(f.stage ?? '') || 'Not recorded'}` }];
  if (text(f.finding)) stage.push({ id: 'finding', text: f.finding });
  if (list(f.review_roles).length > 0) stage.push({ id: 'roles', text: `Reviewed by ${f.review_roles.join(', ')}` });
  const out: Section[] = [
    { key: 'header', kind: 'facts', ...(r && DAY.test(r.as_of ?? '') ? { coverage: `As of ${formatDate(r.as_of)}` } : {}), items: facts },
    { key: 'stage', kind: 'text', title: 'Where it stands', items: stage },
  ];
  if (!r) {
    out.push({ key: 'no-figures', kind: 'text', items: [{ id: 'none', text: NO_FIGURES }] });
    if (!group) out.push(actualSection(f));
  } else {
    out.push(...periodSections(r, group));
    // group view: only the header, months, disclosure and delivery (no items, findings, matches or actuals)
    if (!group) out.push(...itemSection(r), ...findingSection(r), actualSection(f));
  }
  if (f.disclosure) out.push(...disclosureSections(f.disclosure));
  out.push(...deliverySections(f));
  return out;
}

/** The page's words for a failed read; null leaves it to the shared panel frame (its own Try again). */
export function errorWords(error: ApiError): string | null {
  switch (error.kind) {
    case 'unauthenticated':
      return 'Your session ended. Sign in again to continue.';
    case 'not_found':
      return UNAVAILABLE;
    case 'forbidden':
      return 'You don’t have access to this forecast.';
    case 'csrf':
      return 'Refresh your session and try again.';
    case 'stale':
      return 'This changed while you were reading it. Reload.';
    case 'invalid':
      return error.fields[0]?.message ?? error.message;
    default:
      return null;
  }
}
