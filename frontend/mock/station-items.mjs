// PROPOSAL overlay G-OVERVIEW-STATION (D-162): GET /api/v1/overview/stations/items?line=&station=&limit=&cursor= reads the work
// at one station of the factory floor, for the 3D floor's readout strip. Not in v7 (proposals/overview-station-items.json holds
// the shape). Visible to whoever may read E-OVERVIEW; the mock shows the same rows to every persona. The rows are consistent
// with the station counts of the overview the cookie psl_mock_overview names: a station counting n has n rows, taken from the
// work fixtures (so every link opens); needs-a-person stations lead with one row that needs a person. In the live demo, the
// line runs that are still going stand at a station of their floor line too, and the overview counts them (withDemoRuns).
// Order: needs a person first, then the longest waiting. Cursor "o<n>", limit 1 to 50 (default 10). Sample data only.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { overview } from './overview.mjs';

export const STATION_ITEMS_PATH = '/api/v1/overview/stations/items';

const here = dirname(fileURLToPath(import.meta.url));
const workDir = join(here, 'fixtures', 'work');
const pool = readdirSync(workDir)
  .filter((name) => /^W-\d+\.json$/.test(name) && name !== 'W-1099.json')
  .map((name) => JSON.parse(readFileSync(join(workDir, name), 'utf8')))
  .filter((item) => typeof item.title === 'string' && typeof item.reference === 'string');

// Which work fixtures read as belonging to each floor line, by the fixture's own line name (all of them where none match).
const FIT = {
  'Pre-sale': /RFP|Prepare a costing|Engagement|SOW|statement of work/i,
  Planning: /Plan a project|Prepare a costing|Engagement/i,
  Release: /Release|Hypercare|Weekly|Minutes|Handover|Escalat|Issue|Emergency|Controlled change|Leadership/i,
  Closing: /Closure|Go-live|Handover|Closing/i,
  Invoices: /invoice|receipt|Payment reminder/i,
  'Month-end': /Ledger|Fixed asset|Income|Finance question/i,
  'Cash and BU': /Cash forecast|Confirm business unit|receipt/i,
  Payroll: /payroll|staff|joiner|Leaver/i,
};
const poolFor = (line) => {
  const fit = pool.filter((item) => FIT[line]?.test(item.line ?? ''));
  return fit.length > 0 ? fit : pool;
};

// The floor line each demo line key stands on (the overview's eight lines).
const FLOOR_LINE = {
  rfp_intake: 'Pre-sale',
  invoice: 'Invoices',
  income_schedules: 'Invoices',
  ledger_sources: 'Month-end',
  fixed_assets: 'Month-end',
  cash_forecast: 'Cash and BU',
  hr_staff_list: 'Payroll',
};
const FINANCE_LINES = ['Invoices', 'Month-end', 'Cash and BU'];
const ROLE = { 'Pre-sale': 'PMO Lead', Planning: 'PMO Lead', Release: 'PMO Lead', Closing: 'PMO Lead', Invoices: 'Finance Lead', 'Month-end': 'Finance Lead', 'Cash and BU': 'Finance Lead', Payroll: 'HR Lead' };
const AGENT = (line) => (line === 'Payroll' ? 'Zainab' : FINANCE_LINES.includes(line) ? 'Chidi' : 'Tola');

const HOUR = 3_600_000;
const LIMITS = { min: 1, max: 50, fallback: 10 };
const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

const floorLineOf = (run) => FLOOR_LINE[run.lineKey] ?? 'Release';
const stationAt = (line, progress) => Math.min(line.stations.length - 1, Math.floor(progress * line.stations.length));

/** The runs still going, each with the floor line and station index it stands at in this overview. */
function standing(body, floorRuns) {
  return floorRuns.flatMap((run) => {
    const line = body.lines.find((l) => l.line === floorLineOf(run));
    return line ? [{ run, line: line.line, index: stationAt(line, run.progress) }] : [];
  });
}

/** The overview with the demo's running line runs counted at their stations (totals and the needs-a-person mark too). */
export function withDemoRuns(body, floorRuns) {
  const here = standing(body, floorRuns);
  if (here.length === 0) return body;
  const next = structuredClone(body);
  for (const { run, line, index } of here) {
    const station = next.lines.find((l) => l.line === line).stations[index];
    station.count += 1;
    next.totals.in_progress += 1;
    if (run.waiting) {
      station.needs_person = true;
      next.totals.need_a_person += 1;
    }
  }
  return next;
}

const iso = (ms) => new Date(ms).toISOString();

/** Every row of one station (`body` is the overview without the demo runs), in order: needs a person first, then the longest waiting. */
function rowsOf(body, floorRuns, lineName, stationName) {
  const line = body.lines.find((l) => l.line === lineName);
  const index = line?.stations.findIndex((s) => s.name === stationName) ?? -1;
  if (index < 0) return undefined;
  const base = body.lines.slice(0, body.lines.indexOf(line)).reduce((n, l) => n + l.stations.length, 0) + index;
  const asOf = Date.parse(body.as_of);
  const rows = [];
  for (let i = 0; i < line.stations[index].count; i += 1) {
    const own = poolFor(lineName);
    const work = own[(base * 7 + i * 3) % own.length];
    const needs = line.stations[index].needs_person && i === 0;
    rows.push({
      work_id: work.id,
      title: work.title,
      reference: work.reference,
      state: needs ? 'waiting' : 'processing',
      waiting_since: iso(asOf - (needs ? 26 : 2 + ((base + i) % 5) * 5) * HOUR),
      needs_person: needs,
      held_by: needs ? { kind: 'role', name: ROLE[lineName] } : { kind: 'agent', name: AGENT(lineName) },
    });
  }
  for (const { run, line: where, index: at } of standing(body, floorRuns)) {
    if (where !== lineName || at !== index) continue;
    rows.push({
      work_id: run.id,
      title: run.title,
      reference: run.reference,
      state: run.waiting ? 'waiting' : 'processing',
      waiting_since: iso(run.since),
      needs_person: run.waiting,
      held_by: run.waiting ? { kind: 'role', name: run.role } : { kind: 'agent', name: run.agent },
    });
  }
  return rows.sort((a, b) => Number(b.needs_person) - Number(a.needs_person) || Date.parse(a.waiting_since) - Date.parse(b.waiting_since));
}

/** [status, body]. `floorRuns` is runs.floor() in the live demo, else []. */
export function stationItems({ url, cookies, floorRuns = [] }) {
  const params = url.searchParams;
  const line = params.get('line');
  const station = params.get('station');
  const limit = params.has('limit') ? Number(params.get('limit')) : LIMITS.fallback;
  const cursor = params.get('cursor');
  const match = cursor === null ? null : /^o(\d+)$/.exec(cursor);
  const offset = match ? Number(match[1]) : 0;
  if (!line || !station || !Number.isInteger(limit) || limit < LIMITS.min || limit > LIMITS.max || (cursor !== null && !match)) return [404, INVALID_QUERY];
  const body = overview({ cookies }).body;
  const rows = rowsOf(body, floorRuns, line, station);
  if (!rows || offset > rows.length) return [404, rows ? INVALID_QUERY : NOT_FOUND];
  const page = {
    items: rows.slice(offset, offset + limit),
    total: rows.length,
    needs_person_count: rows.filter((r) => r.needs_person).length,
    as_of: body.as_of,
  };
  if (offset + limit < rows.length) page.next_cursor = `o${offset + limit}`;
  return [200, page];
}
