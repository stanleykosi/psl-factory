// F-118: Closure (SCR-49) on the live work item. Turns the closure checklist, the work read, the decision history and the Finance
// confirmation read into the Section objects the workspace renderer draws, and describes the three writes (decide, replace the report,
// confirm milestone notifications). Presentation only: who may decide is the work read's `tasks[]`, who may confirm is the Finance read
// answering, whether debt is visible is `debt` not null; nothing here is a rule about who may act. A value a read does not give reads
// Unknown or "Amount not recorded", never 0. "Closed", "verified" and "returned" are said only from a read, never from a press.
import type { paths } from '@/api/live-schema';
import { formatAmount } from '@/features/decide/format';
import { formatDate, formatDayMonth } from '@/components';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Checklist = Get<'/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist'>;
export type FinanceRead = Get<'/api/v1/projects/{case_id}/delivery/{dossier_id}/finance-confirmation'>;
export type WorkRead = Get<'/api/v1/work/{work_id}'>;
export type HistoryRow = Get<'/api/v1/work/{work_id}/history'>['items'][number];
export type Check = Checklist['checks'][number];
export type Debt = NonNullable<Checklist['debt']>;
export type Task = WorkRead['tasks'][number];

/** What the page needs from the work read; null when that read failed. */
export type WorkPart = { revision: number | null; case_revision: number | null; state: WorkRead['state']; tasks: Task[] };
/** The two ids a closure decision carries. No 1.26 read serves them (the report check's `references` is the report evidence, not the
 *  closure document version or the decision proof; D-26, LD-2), so `read()` leaves this null and Close and Return stay held. */
export type DecisionIds = { version_id: number; evidence_id: number };
export type Readback = {
  caseId: string;
  dossierId: number;
  checklist: Checklist;
  work: WorkPart | null;
  /** Decision rows, newest first as served; empty when none or the read failed. */
  history: HistoryRow[];
  /** Null: the person has no view of it (403 or 404) or it was not asked (the finance check is already confirmed). */
  finance: FinanceRead | null;
  /** The Finance proofs the person may attach. No read lists them yet, so `read()` leaves this empty. */
  financeEvidence: { id: number; label: string }[];
  decision: DecisionIds | null;
  failed: ('work' | 'history' | 'finance')[];
};

export const TEXT = {
  noToken: 'Reload to continue',
  noDecision: 'The closure report isn’t ready to decide yet',
  noFinanceProof: 'No Finance evidence available to attach',
  locked: 'Check the page before trying again.',
  stale: 'This changed. Review the latest report.',
  financeStale: 'Finance confirmation changed. Review it again.',
  cantDecide: 'You can’t decide this closure.',
  tooLong: 'The report is too long.',
  failedParts: { work: 'We couldn’t load who can decide on closure.', history: 'We couldn’t load the decision history.', finance: 'We couldn’t load the Finance confirmation.' },
} as const;

export const NOTE_LIMIT = 4000;
export const REPORT_LIMIT = 16000;
export const SOURCE_LIMIT = 160;
export const REASON_LIMIT = 2000;
export const FINANCE_NOTE_LIMIT = 4000;

/** The board's name for a check; the API's own title is the one drawn and the board's is a sub-line where it differs (Q2). */
const BOARD: Record<string, string> = {
  context: 'Current project scope',
  go_live: 'Go-live accepted',
  hypercare: 'Hypercare qualified',
  archive: 'Archive verified',
  handover: 'Handover acknowledged',
  retrospective: 'Retrospective saved',
  finance: 'Finance confirmation',
  report: 'PM closure report',
};

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`;
const text = (id: string, value: string, extra: Partial<Item> = {}): Item => ({ id, text: value, ...extra });

// ---- the checks ----

/** Presentation only, nothing here decides access: unknown and unavailable are never Done. */
export function checkFields(check: Check): Pick<Item, 'status' | 'tag'> {
  switch (check.status) {
    case 'current':
    case 'recorded':
      // the board words the Finance row Confirmed (and Unknown), the others Done
      return check.key === 'finance' ? { tag: { label: 'Confirmed', tone: 'verified' } } : { status: 'done' };
    case 'held':
      return { status: 'not_yet' };
    case 'unknown':
      return { status: 'unknown' };
    case 'closed':
      return { tag: { label: 'Closed', tone: 'verified' } };
    default:
      return { tag: { label: 'Not available', tone: 'neutral' } };
  }
}

const recordsOf = (check: Check) => check.references.filter((r): r is number => Number.isInteger(r)).length;

function checkItem(check: Check): Item {
  const board = BOARD[check.key];
  const lines = [
    check.key === 'finance' ? 'Milestone notifications confirmed by Finance' : board !== undefined && board.toLowerCase() !== check.title.toLowerCase() ? board : null,
    check.summary,
    check.finding,
  ].filter((l): l is string => typeof l === 'string' && l.trim() !== '');
  const n = recordsOf(check);
  return { id: `check-${check.key}`, text: check.title, detail: lines.join(' · '), ...checkFields(check), ...(n > 0 ? { cite_label: plural(n, 'record') } : {}) };
}

// ---- the state ----

export type ClosureState = 'closed' | 'returned' | 'decision' | 'awaiting' | 'ready' | 'blocked';

/** The task this person may decide, or null. Which verdicts are offered is the task's own list; `reject` is not drawn. */
export function decisionTask(work: WorkPart | null): { task: Task; verdicts: ('approve' | 'return')[] } | null {
  const task = work?.tasks.find((t) => t.can_decide && t.verdicts.some((v) => v === 'approve' || v === 'return'));
  return task ? { task, verdicts: (['approve', 'return'] as const).filter((v) => task.verdicts.includes(v)) } : null;
}

/** The newest decision row (by time, then entry), or null. */
export function latestDecision(history: HistoryRow[]): HistoryRow | null {
  let best: HistoryRow | null = null;
  for (const r of history) if (best === null || Date.parse(r.at) > Date.parse(best.at) || (r.at === best.at && r.entry_id > best.entry_id)) best = r;
  return best;
}

export function stateOf(rb: Readback): ClosureState {
  if (rb.checklist.recorded_closure_id !== null) return 'closed';
  const latest = latestDecision(rb.history);
  const state = rb.work?.state;
  if (latest?.status === 'return' && (state === 'action_needed' || state === 'ready')) return 'returned';
  if (decisionTask(rb.work)) return 'decision';
  if (rb.work && rb.work.tasks.length > 0) return 'awaiting';
  return rb.checklist.ready_to_prepare ? 'ready' : 'blocked';
}

const firstHold = (checks: Check[]) => checks.find((c) => c.status === 'held') ?? checks.find((c) => c.status === 'unknown' || c.status === 'unavailable');

/** The headline tag and the "Next" line (null when the read gives none). */
export function headline(rb: Readback, ctxState: string | undefined): { label: string; tone: 'neutral' | 'person' | 'stopped' | 'verified'; next: string | null; detail: string | null } {
  const state = stateOf(rb);
  const latest = latestDecision(rb.history);
  switch (state) {
    case 'closed':
      return { label: latest?.status === 'approve' ? `Closed ${formatDate(latest.at)}` : 'Closed', tone: 'verified', next: null, detail: closedDetail(latest, ctxState) };
    case 'returned':
      return { label: 'Closure · Returned', tone: 'stopped', next: 'Replace the report.', detail: returnedNote(latest) };
    case 'decision':
      return { label: 'Closure · Waiting for your decision', tone: 'person', next: 'Close the project, or return it with a note.', detail: null };
    case 'awaiting':
      return { label: 'Closure · Awaiting Head of PMO', tone: 'person', next: 'The Head of PMO decides on closure.', detail: null };
    case 'ready':
      return { label: 'Closure · Ready to prepare', tone: 'neutral', next: null, detail: null };
    default: {
      const hold = firstHold(rb.checklist.checks);
      return { label: 'Closure · Not yet', tone: 'neutral', next: hold ? (hold.finding ?? hold.summary) : null, detail: null };
    }
  }
}

/** Who closed, and "Verified" only when the item's own state says so. */
function closedDetail(latest: HistoryRow | null, ctxState: string | undefined): string | null {
  const parts = [latest?.status === 'approve' && latest.actor ? `Closed by ${latest.actor}` : null, ctxState === 'verified' ? 'Verified' : null].filter((p): p is string => p !== null);
  return parts.length > 0 ? parts.join(' · ') : null;
}

/** "<actor> returned closure on <date>: “<reason>”", each part only when the row gives it; null when there is no such row (never invented). */
function returnedNote(latest: HistoryRow | null): string | null {
  if (!latest || latest.status !== 'return') return null;
  const who = latest.actor ? `${latest.actor} returned closure` : 'Closure was returned';
  return `${who} on ${formatDayMonth(latest.at)}${latest.reason ? `: “${latest.reason}”` : ''}`;
}

// ---- still open after closure ----

/** One debt row: the reference, its basis and the amount; an amount the read does not give is "Amount not recorded", never 0. */
export function debtItem(row: Debt['items'][number], index: number): Item {
  const known = row.owed === null ? null : formatAmount({ amount: row.owed, currency: row.currency, unknown: false });
  const value = row.owed === null ? 'Amount not recorded' : (known ?? `${row.currency} ${row.owed}`);
  return { id: `debt-${index}`, label: row.reference, detail: row.basis, value };
}

/** The "Still open after closure" section, or null when `debt` is null (the viewer cannot read it: no heading, no placeholder). */
export function debtSection(debt: Checklist['debt']): Section | null {
  if (debt === null) return null;
  const asOf = `As of ${formatDate(debt.as_of)}`;
  return {
    key: 'debt',
    kind: 'figures',
    title: 'Still open after closure',
    coverage: debt.limited ? `${asOf} · List is limited; more may exist.` : asOf,
    items: debt.items.length === 0 ? [text('none', `No open invoices recorded as of ${formatDate(debt.as_of)}.`)] : debt.items.map(debtItem),
  };
}

// ---- the Finance block ----

const FINANCE_HEAD = 'Finance confirmation: milestone notifications';

/** Milestones listed, and why it cannot be confirmed or that it is confirmed. Drawn only when the Finance read answered. */
export function financeSection(f: FinanceRead | null): Section | null {
  if (f === null) return null;
  const items: Item[] = [];
  if (f.confirmation_id !== null) items.push(text('confirmed', 'Confirmed', { tag: { label: 'Confirmed', tone: 'verified' } }));
  else if (f.finding) items.push(text('finding', f.finding));
  for (const m of f.milestones) items.push(text(`ms-${m.milestone_id}`, `Milestone ${m.milestone_id}`, { detail: `Receipt ${m.receipt_id}` }));
  if (items.length === 0) items.push(text('none', 'No milestone notifications are listed.'));
  return { key: 'finance', kind: 'text', title: FINANCE_HEAD, items };
}

/** What the page draws, in order: the state, the checks, the Finance block, and (once closed) what is still open. */
export function closureSections(rb: Readback, ctx: Pick<LineContext, 'state'>): Section[] {
  const head = headline(rb, ctx.state);
  // the tag alone carries the headline; the same words as the row's text would draw twice
  const lines: Item[] = [{ id: 'state', tag: { label: head.label, tone: head.tone } }];
  if (head.detail) lines.push(text('detail', head.detail));
  if (head.next) lines.push(text('next', `Next: ${head.next}`));
  for (const part of rb.failed) lines.push(text(`failed-${part}`, TEXT.failedParts[part]));
  const out: Section[] = [
    { key: 'state', kind: 'text', items: lines },
    { key: 'checks', kind: 'checklist', title: 'Before closure', items: rb.checklist.checks.map(checkItem) },
  ];
  const finance = financeSection(rb.finance);
  if (finance) out.push(finance);
  if (stateOf(rb) === 'closed') {
    const debt = debtSection(rb.checklist.debt);
    if (debt) out.push(debt);
  }
  return out;
}

// ---- the writes ----

/** `null` when the report check names no single evidence id: the previous report stays null, never a guess (the server answers 409). */
export const previousReport = (checklist: Checklist): number | null => {
  const ids = checklist.checks.find((c) => c.key === 'report')?.references.filter((r): r is number => Number.isInteger(r)) ?? [];
  return ids.length === 1 ? ids[0] : null;
};

export type DecideForm = { note: string };
/** Why a verdict may not be pressed yet, or null. The note is sent as typed; a return needs one. */
export const decideHeld = (verdict: 'approve' | 'return', note: string): string | null => (verdict === 'return' && note.trim() === '' ? 'Add a note to return the closure.' : note.length > NOTE_LIMIT ? `Keep the note to ${NOTE_LIMIT} characters.` : null);

export type ReplaceForm = { report: string; source: string; reason: string };
export const emptyReplace = (): ReplaceForm => ({ report: '', source: '', reason: '' });
export function replaceHeld(f: ReplaceForm): string | null {
  if (f.report.trim() === '') return 'Add the report text.';
  if (f.report.length > REPORT_LIMIT) return `Keep the report to ${REPORT_LIMIT.toLocaleString('en-GB')} characters.`;
  if (f.source.trim() === '') return 'Add where the report comes from.';
  if (f.source.length > SOURCE_LIMIT) return `Keep the source to ${SOURCE_LIMIT} characters.`;
  if (f.reason.trim() === '') return 'Add why it is replaced.';
  if (f.reason.length > REASON_LIMIT) return `Keep the reason to ${REASON_LIMIT} characters.`;
  return null;
}
export const replaceInputs = (f: ReplaceForm): Record<string, unknown> => ({ report_text: f.report, source_reference: f.source.trim(), reason: f.reason.trim() });

export type FinanceForm = { complete: boolean; proof: string | undefined; note: string };
export const emptyFinance = (): FinanceForm => ({ complete: false, proof: undefined, note: '' });
export function financeHeld(rb: Readback, f: FinanceForm): string | null {
  if (!f.complete) return 'Tick that these are all the milestone notifications.';
  if (rb.financeEvidence.length === 0) return TEXT.noFinanceProof;
  if (f.proof === undefined || !rb.financeEvidence.some((p) => String(p.id) === f.proof)) return 'Choose a Finance proof.';
  if (f.note.trim() === '') return 'Add a note.';
  if (f.note.length > FINANCE_NOTE_LIMIT) return `Keep the note to ${FINANCE_NOTE_LIMIT} characters.`;
  return null;
}
export const financeInputs = (f: FinanceForm): Record<string, unknown> => ({ evidence_id: Number(f.proof), note: f.note.trim() });

export const IDS = { decide: 'closure.decide', replace: 'closure.replace-report', finance: 'closure.finance-confirm' } as const;
export const ALL_IDS: string[] = Object.values(IDS);

/** The write descriptors, from the reads, each with the revisions of the read it was built from. A null token is unknown: the write is
 *  disabled ("Reload to continue"), never sent as 0. No body has an `action` or a key field (live closure writes have none), so
 *  `action: null`, and nothing placed in `fixed` that rule would drop. Decide is described only for a task the work read says this
 *  person may decide, and held until both ids are served. Replace is described in the returned state. Finance is described only
 *  while the Finance read answered, shows no confirmation yet and names no finding. */
export function closureCommands(rb: Readback, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const route = `/api/v1/work/${ctx.workId}`;
  const w = rb.work;
  const tokens = { expected_revision: w?.revision ?? null, case_revision: w?.case_revision ?? null };
  const noToken = w?.revision == null || w?.case_revision == null || ctx.revision === null ? { disabledReason: TEXT.noToken } : {};
  const out: CommandDescriptor[] = [];
  if (decisionTask(w) && rb.checklist.recorded_closure_id === null) {
    const hold = rb.decision === null ? { disabledReason: TEXT.noDecision } : {};
    out.push(makeCommand({ id: IDS.decide, label: 'Close or return', url: `${route}/reviews`, tokens, action: null, fixed: { kind: 'closure', ...rb.decision }, successStatuses: [200], ...hold, ...noToken }));
  }
  if (stateOf(rb) === 'returned') {
    out.push(makeCommand({ id: IDS.replace, label: 'Replace the report', url: `${route}/closure-report`, tokens, action: null, fixed: { previous_evidence_id: previousReport(rb.checklist) }, successStatuses: [201], ...noToken }));
  }
  const f = rb.finance;
  if (f && f.confirmation_id === null) {
    const reason = f.finding ?? (f.milestones.length === 0 ? 'No milestone notifications are listed.' : null);
    const finance = reason ? { disabledReason: reason } : {};
    out.push(
      makeCommand({
        id: IDS.finance,
        label: 'Confirm milestone notifications',
        url: `/api/v1/projects/${rb.caseId}/delivery/${rb.dossierId}/finance-confirmation`,
        tokens: { revision: f.revision },
        action: null,
        fixed: { milestone_ids: f.milestones.map((m) => m.milestone_id), inventory_complete: true },
        successStatuses: [201],
        ...finance,
        ...(ctx.revision === null ? { disabledReason: TEXT.noToken } : {}),
      }),
    );
  }
  return out;
}

/** The words under a write, from the shared sender's notice. A refusal to decide gives no reason; the shared words for a changed
 *  record and a too-large body are the page's own. Anything else is the sender's text as it came. */
export function closureNotice(notice: { kind: 'success' | 'error'; text: string; detail?: string }, lastId: string | null): { text: string; detail?: string } {
  if (notice.text.startsWith('This changed while you were working')) return { text: lastId === IDS.finance ? TEXT.financeStale : TEXT.stale };
  if (notice.text === 'You can’t do this.' && lastId === IDS.decide) return { text: TEXT.cantDecide };
  if (notice.text === 'That is too large to send.' && lastId === IDS.replace) return { text: TEXT.tooLong };
  return notice.detail ? { text: notice.text, detail: notice.detail } : { text: notice.text };
}
