// F-113B: the release gates page (SCR-44) on the live work item. Turns GET /work/{id}/release-register, GET /work/{id}/planning-exit,
// the client-testing read and decision-appointments into the Section objects the workspace renderer draws, derives the board state,
// and describes the three writes. Presentation only: who may decide and which step is open come from the reads (`verdicts`,
// `can_approve_directly`, `actions`), never from a rule here. A value the reads do not give reads Unknown, never 0.
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { EvidenceId, UploadId } from '@/features/workspace/evidence';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Register = Get<'/api/v1/work/{work_id}/release-register'>;
export type PlanningExit = Get<'/api/v1/work/{work_id}/planning-exit'>;
export type ClientTesting = Get<'/api/v1/projects/{case_id}/delivery/{dossier_id}/client-testing'>;
export type Appointments = Get<'/api/v1/setup/{case_id}/decision-appointments'>;
export type Readback = { register: Register; exit: PlanningExit; uat: ClientTesting | null; appointments: Appointments | null };
export type Decision = NonNullable<PlanningExit['latest_decision']>;

export const NO_TOKEN = 'We don’t have this item’s current version yet. Reload and try again.';
export const NOT_YET = 'This can’t be decided yet.';
export const NOT_OPEN = 'This step isn’t open now.';
export const NO_DECISION = 'There is no decision for you to make here.';
export const NO_EVIDENCE = 'No evidence is on file for this decision yet.';
export const OUT_OF_SCOPE = 'This record is not for the current scope.';

export type BoardState = 'default' | 'decision' | 'returned' | 'owner_needed' | 'readiness' | 'ready';

/** The board state, from the reads only. When a case matches two, the later in this list wins:
 *  ready, readiness, owner-needed, returned, decision, default. */
export function boardState(rb: Pick<Readback, 'register' | 'exit'>, ctx: Pick<LineContext, 'state'>): BoardState {
  const { register: r, exit: e } = rb;
  if (r.readiness_ids.length > 0) return 'ready';
  if (e.latest_decision?.verdict === 'approve') return 'readiness';
  if (ctx.state === 'owner_needed') return 'owner_needed';
  if (e.latest_decision?.verdict === 'return') return 'returned';
  if (e.verdicts.length > 0 && e.packet !== null) return 'decision';
  return 'default';
}

type Tone = NonNullable<Item['tag']>['tone'];
const STATUS: Record<string, { text: string; tone: Tone }> = {
  current: { text: 'CURRENT', tone: 'verified' },
  stale_scope: { text: 'STALE SCOPE', tone: 'uncertain' },
  restricted_or_authority_changed: { text: 'AUTHORITY CHANGED', tone: 'person' },
  unknown_or_stale: { text: 'UNKNOWN OR STALE', tone: 'uncertain' },
  unknown: { text: 'UNKNOWN', tone: 'neutral' },
};

/** A check's status in the D-14 words; any other value is shown as given, in capitals, never as done. */
export function statusWords(status: string): { text: string; tone: Tone } {
  if (Object.hasOwn(STATUS, status)) return STATUS[status];
  const text = status.trim() === '' ? 'UNKNOWN' : status.replaceAll('_', ' ').toUpperCase();
  return { text, tone: 'neutral' };
}

const humanise = (name: string) => {
  const spaced = name.replaceAll('_', ' ').trim();
  return spaced === '' ? 'Unknown' : spaced.charAt(0).toUpperCase() + spaced.slice(1);
};
const VERDICT_WORDS: Record<string, string> = { approve: 'Approved', return: 'Returned', reject: 'Rejected' };
const OUTCOME_WORDS: Record<string, string> = { approved: 'Approved', changes_requested: 'Changes requested', rejected: 'Rejected', approved_with_workaround: 'Approved with workaround' };
const isPmoLead = (role: string) => role.replaceAll('_', ' ').trim().toLowerCase() === 'pmo lead';

/** "Approved 26 Nov 09:00 by Kemi Adebayo · approved directly", taken from the read's latest decision. */
export function decisionLine(d: Decision): string {
  const word = VERDICT_WORDS[d.verdict] ?? humanise(d.verdict);
  return `${word} ${formatDayTime(d.at)} by ${d.by}${d.verdict === 'approve' && d.direct ? ' · approved directly' : ''}`;
}
/** "Approved by PMO Lead, Kemi Adebayo, 26 Nov 09:00"; "PMO Lead" only when the role says so. */
export const approvedLine = (d: Decision) => `Approved by ${isPmoLead(d.role) ? 'PMO Lead, ' : ''}${d.by}, ${formatDayTime(d.at)}${d.direct ? ' · approved directly' : ''}`;

const text = (id: string, value: string): Item => ({ id, text: value });

/** The line under the page title for the board state. */
function stateLines(state: BoardState, rb: Readback): Item[] {
  const { register: r, exit: e } = rb;
  const d = e.latest_decision;
  switch (state) {
    case 'ready': {
      const n = r.readiness_ids.length;
      const lines = [text('ready', `Release ready · ${n} ${n === 1 ? 'readiness record' : 'readiness records'}`)];
      if (d?.verdict === 'approve') lines.push(text('approved', approvedLine(d)));
      if (r.release) lines.push(text('released', `Release recorded ${formatDayTime(r.release.released_at)} · ${r.release.reference}${r.release.environment ? ` · ${r.release.environment}` : ''}`));
      return lines;
    }
    case 'readiness':
      return [text('readiness', 'Preparing release readiness'), ...(d ? [text('approved', approvedLine(d))] : [])];
    case 'owner_needed':
      return [text('held', 'This release is on hold until a PMO Lead is assigned.')];
    case 'returned':
      return d ? [text('returned', `${d.by} returned the release on ${formatDayTime(d.at)}`)] : [];
    case 'decision':
      return [];
    default:
      if (e.latest_decision !== null) return [];
      return [text('waiting', e.verdicts.length > 0 ? 'Waiting for the packet' : 'Waiting for the PMO Lead')];
  }
}

function gateSections(r: Register): Section[] {
  if (!r.current_scope) return [{ key: 'scope', kind: 'text', items: [text('scope', OUT_OF_SCOPE)] }];
  return r.phases.map((phase, i) => ({
    key: `phase-${i}`,
    kind: 'table',
    title: phase.name,
    columns: [
      { key: 'check', label: 'Check', kind: 'text' },
      { key: 'authority', label: 'Authority', kind: 'text' },
      { key: 'status', label: 'Status', kind: 'tag' },
      { key: 'records', label: 'Records', kind: 'text' },
    ],
    items: phase.checks.map((check): Item => {
      const status = statusWords(check.status);
      const n = check.records.length;
      return {
        id: check.key,
        cells: [
          { column: 'check', text: check.title },
          { column: 'authority', text: check.authority },
          { column: 'status', tag: { label: status.text, tone: status.tone } },
          // an empty list draws no count at all, never "0 records"
          ...(n > 0 ? [{ column: 'records', text: `${n} ${n === 1 ? 'record' : 'records'}` }] : []),
        ],
      };
    }),
  }));
}

function planningSection(e: PlanningExit): Section {
  const items: Item[] = e.checklist.map((row, i) => {
    const status = statusWords(row.status);
    return { id: `check-${i}`, label: humanise(row.name), tag: { label: status.text, tone: status.tone } };
  });
  items.push({ id: 'decision', label: 'Latest decision', value: e.latest_decision ? decisionLine(e.latest_decision) : 'No decision yet' });
  return { key: 'planning', kind: 'facts', title: 'Planning decision', items };
}

function uatSection(uat: ClientTesting): Section {
  const items: Item[] = [{ id: 'outcome', label: 'Client response', value: uat.outcome === null ? 'No response recorded' : (OUTCOME_WORDS[uat.outcome] ?? humanise(uat.outcome)) }];
  if (uat.proof_current === false) items.push({ id: 'proof', label: 'Proof', value: 'Proof is out of date' });
  if (uat.binding_current === false) items.push({ id: 'binding', label: 'This release', value: 'Not tied to this release' });
  return { key: 'uat', kind: 'facts', title: 'Client testing', items };
}

function ownerSections(a: Appointments | null): Section[] {
  const sections: Section[] = [{ key: 'owner', kind: 'facts', title: 'Who decides', items: [{ id: 'pmo', label: 'PMO Lead assigned', tag: { label: 'Owner needed', tone: 'person' } }] }];
  if (a) {
    const name = (id: number) => a.people.find((p) => p.id === id)?.label ?? 'Unknown person';
    sections.push({
      key: 'appointments',
      kind: 'table',
      title: 'Appointments',
      columns: [
        { key: 'person', label: 'Person', kind: 'text' },
        { key: 'roles', label: 'Roles', kind: 'text' },
        { key: 'eligibility', label: 'Eligibility', kind: 'text' },
      ],
      items: a.appointments.map((x): Item => ({
        id: String(x.user_id),
        cells: [
          { column: 'person', text: name(x.user_id) },
          { column: 'roles', text: x.roles.join(', ') },
          { column: 'eligibility', text: x.eligibility },
        ],
      })),
    });
  }
  return sections;
}

export function releaseSections(rb: Readback, ctx: Pick<LineContext, 'state'>): Section[] {
  const state = boardState(rb, ctx);
  const out: Section[] = [];
  const lines = stateLines(state, rb);
  if (lines.length > 0) out.push({ key: 'state', kind: 'text', items: lines });
  if (state === 'owner_needed') out.push(...ownerSections(rb.appointments));
  out.push(...gateSections(rb.register));
  out.push(planningSection(rb.exit));
  if (rb.uat) out.push(uatSection(rb.uat));
  if (rb.exit.blockers.length > 0) out.push({ key: 'blockers', kind: 'text', title: 'What is blocking the release', items: rb.exit.blockers.map((b) => text(String(b.id), b.reference)) });
  if (state === 'returned' && rb.exit.workaround) out.push({ key: 'workaround', kind: 'text', items: [text('workaround', 'Client workaround on file')] });
  return out;
}

// ---- the three writes ----

export type DecideChoice = { verdict: 'approve' | 'return'; note: string; evidenceId: EvidenceId | null; issueId: number | null };

/** Why a decision may not be sent yet, or null. The server stays the rule for who may decide: this only checks the person has
 *  said what the read asks for (a note to return, evidence unless the read says they may approve directly). */
export function decisionHeld(e: PlanningExit, choice: Pick<DecideChoice, 'verdict' | 'note' | 'evidenceId'>): string | null {
  if (!e.verdicts.includes(choice.verdict)) return NO_DECISION;
  if (e.packet === null || e.expected_revision == null || e.case_revision == null) return NOT_YET;
  if (choice.verdict === 'return' && choice.note.trim() === '') return 'Write a note to return this.';
  const direct = choice.verdict === 'approve' && e.can_approve_directly;
  if (!direct && choice.evidenceId === null) return e.proofs.length === 0 ? NO_EVIDENCE : 'Choose the evidence for this decision.';
  return null;
}

/** The inputs of POST /work/{id}/planning-exit beyond the tokens and packet. `evidence_id` only when the person chose a proof the read
 *  lists; `issue_id` only for a return, and only a blocker the read lists; `note` only when written. */
export function decideInputs(e: PlanningExit, choice: DecideChoice): Record<string, unknown> {
  const inputs: Record<string, unknown> = { verdict: choice.verdict };
  if (choice.note.trim() !== '') inputs.note = choice.note;
  if (choice.evidenceId !== null && e.proofs.some((p) => p.id === choice.evidenceId)) inputs.evidence_id = choice.evidenceId;
  if (choice.verdict === 'return' && choice.issueId !== null && e.blockers.some((b) => b.id === choice.issueId)) inputs.issue_id = choice.issueId;
  return inputs;
}

export type ObserveChoice = { releasedAt: string; reference: string; environment: string; note: string; readinessId: number | null; uploadId: UploadId };

/** The inputs of `observe_release`: the file's `upload_id` is its own field and never an evidence id; a blank environment is null;
 *  `readiness_id` is the one readiness record, a listed choice, or null. */
export function observeInputs(r: Register, choice: ObserveChoice): Record<string, unknown> {
  const only = r.readiness_ids.length === 1 ? r.readiness_ids[0] : null;
  const chosen = choice.readinessId !== null && r.readiness_ids.includes(choice.readinessId) ? choice.readinessId : null;
  return {
    readiness_id: only ?? chosen,
    released_at: choice.releasedAt,
    reference: choice.reference.trim(),
    upload_id: choice.uploadId,
    note: choice.note,
    environment: choice.environment.trim() === '' ? null : choice.environment.trim(),
  };
}

/** The three descriptors, from the reads. A disabled reason is the read's own (no verdicts, no such action, a token not known). */
export function releaseCommands({ register: r, exit: e }: Readback, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const known = (a: number | null | undefined, b: number | null | undefined) => a != null && b != null && ctx.revision !== null;
  const exitTokens = { expected_revision: e.expected_revision, case_revision: e.case_revision };
  const regTokens = { expected_revision: r.expected_revision, case_revision: r.case_revision };
  const action = (name: Register['actions'][number]) => (!r.actions.includes(name) ? NOT_OPEN : !known(r.expected_revision, r.case_revision) ? NO_TOKEN : undefined);
  const decideReason = e.verdicts.length === 0 ? NO_DECISION : !known(e.expected_revision, e.case_revision) ? NO_TOKEN : e.packet === null ? NOT_YET : undefined;
  const route = `/api/v1/work/${ctx.workId}`;
  const prepare = action('prepare_readiness');
  const observe = action('observe_release');
  return [
    // the body has no `action`; makeCommand drops one placed in `fixed` when `action` is null, so the packet goes in `fixed` and nothing else does
    makeCommand({ id: 'release.decide', label: 'Decide the planning exit', url: `${route}/planning-exit`, tokens: exitTokens, action: null, fixed: { packet: e.packet }, successStatuses: [200], ...(decideReason ? { disabledReason: decideReason } : {}) }),
    makeCommand({ id: 'release.prepare_readiness', label: 'Prepare release readiness', url: `${route}/release-register`, tokens: regTokens, successStatuses: [200], ...(prepare ? { disabledReason: prepare } : {}) }),
    makeCommand({ id: 'release.observe', label: 'Record the release', url: `${route}/release-register`, tokens: regTokens, action: 'observe_release', fixed: { checked: true, private_log_id: null }, successStatuses: [200], ...(observe ? { disabledReason: observe } : {}) }),
  ];
}
