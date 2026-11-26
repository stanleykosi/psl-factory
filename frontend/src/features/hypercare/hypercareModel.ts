// F-115: the hypercare page (SCR-46) on the live work item. Turns GET /work/{id}/stability, GET /work/{id}/stability/events and the project's
// issues register into the Section objects the workspace renderer draws, and derives the page state. Presentation only: whether the work
// is qualified, which criterion is met and who may act are the reads' answers. A value the reads do not give reads Unknown, never 0.
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import type { Item, Section } from '@/features/workspace/labels';

import { criterionLabel, RESULT_TAGS, type Criteria } from './hypercareLabels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Stability = Get<'/api/v1/work/{work_id}/stability'>;
export type StabilityEvents = Get<'/api/v1/work/{work_id}/stability/events'>;
export type IssuesPage = Get<'/api/v1/projects/{case_id}/issues'>;
export type RegisterIssue = IssuesPage['issues'][number];
export type OpenIssues = { issues: RegisterIssue[]; owners: IssuesPage['owners'] };

export type HypercareState = 'setup' | 'evaluating' | 'qualified' | 'not_met';
export const STATE_WORDS: Record<HypercareState, string> = { setup: 'Setup needed', evaluating: 'Evaluating', qualified: 'Qualified', not_met: 'Not met' };
const STATE_TONES: Record<HypercareState, 'person' | 'agent' | 'verified' | 'stopped'> = { setup: 'person', evaluating: 'agent', qualified: 'verified', not_met: 'stopped' };
export const MAX_ISSUES = 100;
export const NO_ISSUES = 'No open issues.';

/** The criteria as the read gives them (the contract's two shapes differ only by the optional issue clearance). */
export const criteriaOf = (s: Pick<Stability, 'criteria'>): Criteria | null => s.criteria as Criteria | null;

/** Page state, in this order: no criteria is Setup needed; else no answer yet is Evaluating; else qualified or not met. */
export function hypercareState(s: Pick<Stability, 'criteria' | 'qualified'>): HypercareState {
  if (s.criteria === null) return 'setup';
  if (s.qualified === null) return 'evaluating';
  return s.qualified ? 'qualified' : 'not_met';
}

const text = (id: string, value: string): Item => ({ id, text: value });
const hours = (n: number) => `${n} ${n === 1 ? 'hour' : 'hours'}`;

/** Open issues only (Open or In Progress), whatever else the register holds. */
export const isOpenIssue = (i: Pick<RegisterIssue, 'status'>) => i.status === 'Open' || i.status === 'In Progress';

/** A blocking issue matches the criteria's clearance rule on both its status and its severity. */
export function blocksHypercare(issue: Pick<RegisterIssue, 'status' | 'severity'>, criteria: Criteria | null): boolean {
  const c = criteria?.issue_clearance;
  return !!c && issue.severity !== null && c.blocking_statuses.includes(issue.status) && c.blocking_severities.includes(issue.severity);
}

function windowLine(s: Stability, criteria: Criteria | null): string | null {
  if (s.due_at) return `Window ends ${formatDayTime(s.due_at)}`;
  return criteria ? `${hours(criteria.minimum_hours)} from the release` : null;
}

function stateSections(s: Stability, state: HypercareState, criteria: Criteria | null): Section[] {
  const out: Section[] = [];
  const line = windowLine(s, criteria);
  out.push({ key: 'state', kind: 'facts', items: [{ id: 'state', label: 'Hypercare', tag: { label: STATE_WORDS[state], tone: STATE_TONES[state] }, ...(line ? { value: line } : {}) }] });
  const note: Item[] = [];
  if (state === 'setup') note.push(text('setup', 'Hypercare criteria are not set.'), text('who', s.can_draft_criteria ? 'An admin can draft them in Setup' : 'An admin sets the criteria in Setup.'));
  if (state === 'evaluating') note.push(text('evaluating', 'Tola is evaluating hypercare.'));
  if (state === 'qualified') note.push(text('qualified', 'Hypercare qualified.'), text('verified', s.verified ? 'Verified' : 'Qualified, not yet verified'));
  if (state === 'not_met') s.findings.forEach((f, i) => note.push(text(`finding-${i}`, f)));
  if (note.length > 0) out.push({ key: 'result', kind: 'text', items: note });
  return out;
}

function criteriaSection(s: Stability, criteria: Criteria | null): Section | null {
  const rows: { key: string; owner: string | null; status: string | null }[] =
    s.criterion_results.length > 0
      ? s.criterion_results.map((r) => ({ key: r.key, owner: r.owner, status: r.status }))
      : criteria
        ? [
            ...criteria.confirmation_owners.flatMap((owner) => [
              { key: 'confirmation', owner, status: null },
              { key: 'elapsed_hours', owner, status: null },
            ]),
            ...criteria.metrics.map((m) => ({ key: `metric:${m.key}`, owner: m.owner, status: null })),
            ...(criteria.issue_clearance ? [{ key: 'issue_clearance', owner: null, status: null }] : []),
          ]
        : [];
  if (rows.length === 0) return null;
  return {
    key: 'criteria',
    kind: 'checklist',
    title: 'Criteria',
    items: rows.map((r, i): Item => {
      const { label, detail } = criterionLabel(r.key, r.owner, criteria);
      // a result this page does not know is shown as given and never as Met
      const tag = r.status === null ? undefined : (RESULT_TAGS[r.status] ?? { label: r.status, tone: 'uncertain' as const });
      return { id: `${i}-${r.key}-${r.owner ?? ''}`, label, ...(detail ? { detail } : {}), ...(tag ? { tag } : {}) };
    }),
  };
}

const CHECK_NAMES: Record<string, string> = { release: 'Release', acceptance: 'Acceptance', stability: 'Stability' };

function checksSection(s: Stability): Section | null {
  if (s.checks.length === 0) return null;
  return {
    key: 'checks',
    kind: 'checklist',
    title: 'Checks',
    items: s.checks.map((c): Item => ({
      id: c.name,
      label: CHECK_NAMES[c.name] ?? c.name,
      tag: c.status === 'ready' ? { label: 'Ready', tone: 'verified' } : c.status === 'held' ? { label: 'Held', tone: 'uncertain' } : { label: c.status, tone: 'uncertain' },
      ...(c.finding ? { detail: c.finding } : {}),
    })),
  };
}

/** One row per owner who has a reading, plus a confirmation owner with none. The reading's own number is not in the read, so none is drawn. */
function readingsSection(s: Stability, criteria: Criteria | null): Section | null {
  const owners = [...new Set([...s.observations.map((o) => o.owner as string), ...(criteria?.confirmation_owners ?? [])])];
  if (owners.length === 0) return null;
  const recorded = new Set(s.observations.map((o) => o.owner as string));
  return {
    key: 'readings',
    kind: 'table',
    title: 'Metric readings',
    columns: [
      { key: 'owner', label: 'Owner', kind: 'text' },
      { key: 'recorded', label: 'Reading', kind: 'text' },
      { key: 'results', label: 'Metrics met', kind: 'text' },
    ],
    items: owners.map((owner): Item => {
      const metrics = s.criterion_results.filter((r) => r.owner === owner && r.key.startsWith('metric:'));
      const met = metrics.filter((r) => r.status === 'met').length;
      return {
        id: owner,
        cells: [
          { column: 'owner', text: owner },
          { column: 'recorded', text: recorded.has(owner) ? 'Recorded' : 'No reading yet' },
          { column: 'results', text: metrics.length > 0 ? `${met} of ${metrics.length} met` : 'No results yet' },
        ],
      };
    }),
  };
}

/** The stability panel's own sections (the open issues and the next step are drawn after them, by HypercareActions). */
export function stabilitySections(s: Stability): Section[] {
  const criteria = criteriaOf(s);
  const state = hypercareState(s);
  return [...stateSections(s, state, criteria), criteriaSection(s, criteria), checksSection(s), readingsSection(s, criteria)].filter((x): x is Section => x !== null);
}

/** "Open issues": a table apart from the readings. Nothing open reads "No open issues."; an owner the register does not list reads "No owner". */
export function issuesSection(open: OpenIssues, criteria: Criteria | null): Section {
  if (open.issues.length === 0) return { key: 'issues', kind: 'text', title: 'Open issues', items: [text('none', NO_ISSUES)] };
  return {
    key: 'issues',
    kind: 'table',
    title: 'Open issues',
    columns: [
      { key: 'reference', label: 'Issue', kind: 'text' },
      { key: 'title', label: 'Title', kind: 'text' },
      { key: 'severity', label: 'Severity', kind: 'text' },
      { key: 'status', label: 'Status', kind: 'text' },
      { key: 'owner', label: 'Owner', kind: 'text' },
      { key: 'age', label: 'Open for', kind: 'text' },
      { key: 'blocks', label: 'Effect', kind: 'tag' },
    ],
    items: open.issues.map((i): Item => ({
      id: String(i.id),
      cells: [
        { column: 'reference', text: i.reference },
        { column: 'title', text: i.title },
        ...(i.severity ? [{ column: 'severity', text: i.severity }] : []),
        { column: 'status', text: i.status },
        { column: 'owner', text: open.owners.find((o) => o.id === i.owner_id)?.name ?? 'No owner' },
        ...(i.age_days !== null ? [{ column: 'age', text: `${i.age_days} days open` }] : []),
        ...(blocksHypercare(i, criteria) ? [{ column: 'blocks', tag: { label: 'Blocks hypercare', tone: 'stopped' as const } }] : []),
      ],
    })),
  };
}

/** What closes the page: only the Not met state has a next step. The closure line is drawn only while a stability or acceptance check is held. */
export function nextSection(s: Stability): Section | null {
  if (hypercareState(s) !== 'not_met') return null;
  const items = [text('fix', 'Fix the findings above. Tola evaluates again when they are resolved.')];
  if (s.checks.some((c) => (c.name === 'stability' || c.name === 'acceptance') && c.status === 'held')) items.push(text('closure', 'Closure stays blocked until then.'));
  return { key: 'next', kind: 'text', title: 'Next', items };
}

/** The packet is a 64-character digest, too long for a phone line: its first twelve characters and an ellipsis. */
export const shortId = (id: string) => (id.length > 12 ? `${id.slice(0, 12)}…` : id);

/** Release evidence and acceptance, counted from the events read. Display only: no write is offered here. */
export function eventsSections(e: StabilityEvents): Section[] {
  const count = (n: number) => (n === 0 ? 'None recorded' : `${n} recorded`);
  const receiptTimes = e.receipts.map((r) => (r as { at?: unknown }).at).filter((at): at is string => typeof at === 'string');
  const latest = receiptTimes.length > 0 ? [...receiptTimes].sort().at(-1) : undefined;
  const n = e.receipts.length;
  const items: Item[] = [
    { id: 'evidence', label: 'Release evidence', value: count(e.release_evidence.length) },
    { id: 'signatures', label: 'Go-live signatures', value: count(e.signatures.length) },
    { id: 'packet', label: 'Acceptance packet', value: e.acceptance_packet === null ? 'Not recorded' : shortId(e.acceptance_packet) },
    { id: 'receipts', label: 'Receipts', value: n === 0 ? 'None recorded' : `${n} ${n === 1 ? 'receipt' : 'receipts'}${latest ? `, latest ${formatDayTime(latest)}` : ''}` },
  ];
  const out: Section[] = [{ key: 'events', kind: 'facts', title: 'Release and acceptance', items }];
  if (e.can_record_release && e.release_evidence.length === 0) out.push({ key: 'events-note', kind: 'text', items: [text('unrecorded', 'The release has not been recorded.')] });
  return out;
}

/** Follows the register's pages until it ends or MAX_ISSUES rows are read, and keeps the open ones. A failed page fails the whole read. */
export async function readOpenIssues(page: (before: number | null) => Promise<IssuesPage>): Promise<OpenIssues> {
  const issues: RegisterIssue[] = [];
  let owners: IssuesPage['owners'] = [];
  let seen = 0;
  let before: number | null = null;
  for (;;) {
    const p = await page(before);
    owners = [...owners, ...p.owners.filter((o) => !owners.some((x) => x.id === o.id))];
    seen += p.issues.length;
    issues.push(...p.issues.filter(isOpenIssue));
    if (p.next_before === null || seen >= MAX_ISSUES || p.issues.length === 0 || p.next_before === before) break;
    before = p.next_before;
  }
  return { issues, owners };
}
