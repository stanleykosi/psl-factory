// F-112: a change request (SCR-31, part 1) on the live work item. Turns GET /work/{id}/change (and, for the reference and module, the
// project's ordinary-changes read) into the Section objects the workspace renderer draws, and describes the writes (assess, decide,
// authorize). Presentation only: which controls exist comes from the read (`assessors`, each decider's `verdicts`, `can_authorize`),
// what may be chosen comes from the served lists, and nothing here decides who may act. A value the read does not give reads
// "Not recorded" or "Not given yet", never 0. Notice, execution, go-live note, closure, retry and restart are F-112B: no command for
// them is described here.
import type { operations } from '@/api/live-schema';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

export type Change = operations['changes_detail']['responses'][200]['content']['application/json'];
export type Register = operations['changes_register']['responses'][200]['content']['application/json'];
export type Team = Change['assessors'][number];
export type Decider = Change['decisions'][number];
export type Verdict = Decider['verdicts'][number];
/** `register` is the project's ordinary-changes read; null when it could not be read (the reference and module are then left out). */
export type Readback = { change: Change; register: Register | null };

export const TEXT = {
  noToken: 'We don’t have this change’s current version yet. Reload and try again.',
  noProof: 'No proof file is recorded for this case yet',
  locked: 'Check the page before trying again.',
  reading: 'Reading the change again before the next entry.',
  notRecorded: 'Not recorded',
  notGiven: 'Not given yet',
  newChange: 'You can log a new change later.',
  authoriseCommits: 'This commits the change. It cannot be undone here.',
} as const;

export const NOTE_LIMIT = 4000;
export const EFFORT_LIMIT = 32;
export const SCOPE_ITEM_LIMIT = 240;
export const SCOPE_ITEMS_MAX = 100;

export const TEAMS: readonly Team[] = ['Engineering', 'QA', 'Infra', 'Security'];

// ---- the stage track (D-6) ----

export const STEPS = ['Authorization', 'Notice', 'Execution', 'Go-live', 'Signatures'] as const;
const STAGE_STEP: Record<string, number> = { source: 0, impact: 0, authorization: 0, notice: 1, execution: 2, go_live: 3, signatures: 4, complete: 4 };

/** The step (0 to 4) a stage code lights, or null for a value outside the eight codes: no step is lit and the raw text is shown. */
export const stepOf = (stage: string): number | null => (Object.hasOwn(STAGE_STEP, stage) ? STAGE_STEP[stage] : null);

export type StepState = 'done' | 'now' | 'next';
/** Each step's state for a stage: before the current one done, the current one now, after it next. `complete` finishes the last step. */
export function stepStates(stage: string): StepState[] | null {
  const at = stepOf(stage);
  if (at === null) return null;
  return STEPS.map((_, i): StepState => (i < at || (stage === 'complete' && i === at) ? 'done' : i === at ? 'now' : 'next'));
}

// ---- the people and the status ----

/** A decider's status read as an approval or a rejection from its words (assumption 3): "Approved" yes, "Not approved" no. */
export const isApproved = (d: Pick<Decider, 'status'>) => /^approve/i.test(d.status.trim());
export const isRejected = (d: Pick<Decider, 'status'>) => /^reject/i.test(d.status.trim());

/** The row for each of the four teams in order; a team the read leaves out is a missing row (no assessment). */
export function impactRows(c: Change): Change['impact'] {
  return TEAMS.map((team) => c.impact.find((r) => r.team === team) ?? { team, status: 'Missing', assessment_id: null, summary: null, effort: null });
}
export const recordedCount = (c: Change) => impactRows(c).filter((r) => r.assessment_id !== null).length;

export type StatusTag = { label: string; tone: 'neutral' | 'person' | 'agent' | 'stopped' | 'uncertain' | 'verified' };

/** The status tag, derived (the read carries none): rejected, authorised, approved to authorise, deciding, being assessed, else the raw
 *  status of the first row not recorded, else none. */
export function statusTag(c: Change): StatusTag | null {
  const done = recordedCount(c);
  const approved = c.decisions.filter(isApproved).length;
  if (c.decisions.some(isRejected)) return { label: 'Rejected', tone: 'stopped' };
  if (c.authorization_id !== null) return { label: 'Authorised', tone: 'verified' };
  if (c.can_authorize && c.decisions.length > 0 && approved === c.decisions.length) return { label: 'Approved · to authorise', tone: 'person' };
  if ((c.stage === 'source' || c.stage === 'impact') && done < TEAMS.length) return { label: `Being assessed · ${done} of ${TEAMS.length}`, tone: 'uncertain' };
  if ((c.stage === 'impact' || c.stage === 'authorization') && done === TEAMS.length && approved < c.decisions.length) return { label: `Deciding · ${approved} of ${c.decisions.length}`, tone: 'uncertain' };
  const open = impactRows(c).find((r) => r.assessment_id === null);
  return open ? { label: open.status, tone: 'neutral' } : null;
}

export const isRejectedChange = (c: Change) => c.decisions.some(isRejected);

// ---- the sections ----

const text = (id: string, value: string): Item => ({ id, text: value });
const fact = (id: string, label: string, value: string): Item => ({ id, label, value });

/** The ordinary-changes row for this version, or null: nothing is guessed from a title. */
export const registerRow = (rb: Readback) => rb.register?.records.find((r) => r.version_id === rb.change.change_version_id) ?? null;

export function changeSections(rb: Readback): Section[] {
  const c = rb.change;
  const row = registerRow(rb);
  const tag = statusTag(c);
  const out: Section[] = [];

  const facts: Item[] = [];
  if (row) facts.push(fact('reference', 'Reference', row.reference));
  facts.push({ id: 'category', label: 'Category', value: c.category, tag: { label: c.category, tone: 'neutral' } });
  if (row) facts.push(fact('module', 'Module', row.module));
  if (tag) facts.push({ id: 'status', label: 'Status', tag: { label: tag.label, tone: tag.tone } });
  if (stepOf(c.stage) === null) facts.push(fact('stage', 'Stage', c.stage));
  if (c.authorization_id !== null) facts.push(fact('authorisation', 'Authorisation', `Recorded (#${c.authorization_id})`));
  out.push({ key: 'summary', kind: 'facts', items: facts });

  const states = stepStates(c.stage);
  out.push({
    key: 'track',
    kind: 'checklist',
    title: 'Where this change is',
    items: STEPS.map((name, i): Item => ({ id: `step-${i + 1}`, text: `${i + 1} · ${name}`, ...(states ? { status: states[i] } : {}) })),
  });

  out.push({
    key: 'impact',
    kind: 'table',
    title: 'Impact assessments',
    columns: [
      { key: 'team', label: 'Team', kind: 'text' },
      { key: 'assessment', label: 'Assessment', kind: 'text' },
      { key: 'effort', label: 'Effort', kind: 'text' },
      { key: 'recorded', label: 'Recorded', kind: 'tag' },
    ],
    items: impactRows(c).map((r): Item => ({
      id: r.team,
      cells: [
        { column: 'team', text: r.team },
        { column: 'assessment', text: r.summary ?? TEXT.notGiven },
        { column: 'effort', text: r.effort === null || r.effort.trim() === '' ? TEXT.notRecorded : r.effort },
        { column: 'recorded', tag: { label: r.status, tone: r.assessment_id === null ? 'uncertain' : 'verified' } },
      ],
    })),
  });

  if (c.decisions.length > 0) {
    out.push({
      key: 'deciders',
      kind: 'table',
      title: 'Deciders',
      columns: [
        { key: 'role', label: 'Decider', kind: 'text' },
        { key: 'status', label: 'Decision', kind: 'tag' },
      ],
      items: c.decisions.map((d): Item => ({
        id: d.role,
        cells: [
          { column: 'role', text: d.role },
          { column: 'status', tag: { label: d.status, tone: isRejected(d) ? 'stopped' : isApproved(d) ? 'verified' : 'uncertain' } },
        ],
      })),
    });
  }

  const next: Item[] = [text('next', c.next_action)];
  if (c.finding.trim() !== '') next.push(text('finding', c.finding));
  if (isRejectedChange(c)) next.push(text('later', TEXT.newChange));
  out.push({ key: 'next', kind: 'text', title: 'Next', items: next });
  return out;
}

// ---- the writes ----

export type ProofChoice = { id: number; version: number; kind: string };
export const proofLabel = (p: ProofChoice) => `${p.kind.replaceAll('_', ' ')} · version ${p.version} · no. ${p.id}`;
const listed = (c: Change, id: string | undefined) => id !== undefined && c.evidence.some((e) => String(e.id) === id);

export const CHOICES = ['yes', 'no', 'unknown'] as const;
export type Choice = (typeof CHOICES)[number] | undefined;
/** Yes and No are true and false; "Not known" is null: unknown is never false. */
export const choiceValue = (c: Choice): boolean | null => (c === 'yes' ? true : c === 'no' ? false : null);

export const OUTPUT_KEYS = ['discipline', 'timeline', 'cost_resource', 'risk', 'dependency'] as const;
export type Outputs = Record<(typeof OUTPUT_KEYS)[number], string>;
export const emptyOutputs = (): Outputs => ({ discipline: '', timeline: '', cost_resource: '', risk: '', dependency: '' });

export type AssessChoice = {
  team: Team;
  note: string;
  effort: string;
  cost: Choice;
  timeline: Choice;
  clientFacing: Choice;
  production: Choice;
  scope: string;
  outputs: Outputs;
  evidence: string | undefined;
};

/** The scope items: one per line, blank lines dropped; null when none. */
export const scopeItems = (scope: string): string[] | null => {
  const items = scope.split('\n').map((s) => s.trim()).filter((s) => s !== '');
  return items.length === 0 ? null : items;
};

/** Why an assessment may not be sent yet, or null. The server stays the rule for who may assess: this only checks the person has said
 *  what the read asks for and that the team is one the read lists. */
export function assessHeld(c: Change, a: AssessChoice): string | null {
  if (!c.assessors.includes(a.team)) return 'This team’s assessment isn’t open to you.';
  if (c.evidence.length === 0) return TEXT.noProof;
  if (a.note.trim() === '') return 'Add the assessment note.';
  if (a.note.length > NOTE_LIMIT) return `Use ${NOTE_LIMIT} characters or fewer in the note.`;
  if (a.effort.trim().length > EFFORT_LIMIT) return `Use ${EFFORT_LIMIT} characters or fewer for the effort.`;
  if (a.cost === undefined || a.timeline === undefined || a.clientFacing === undefined || a.production === undefined) return 'Answer each question about cost, timeline, the client and production, or choose “Not known”.';
  const items = scopeItems(a.scope);
  if (items && (items.length > SCOPE_ITEMS_MAX || items.some((s) => s.length > SCOPE_ITEM_LIMIT))) return `Keep each scope item to ${SCOPE_ITEM_LIMIT} characters and at most ${SCOPE_ITEMS_MAX} items.`;
  if (OUTPUT_KEYS.some((k) => a.outputs[k].trim().length > NOTE_LIMIT)) return `Use ${NOTE_LIMIT} characters or fewer in each output note.`;
  if (!listed(c, a.evidence)) return 'Choose the proof for this assessment.';
  return null;
}

/** The inputs of `assess` beyond the tokens, `action` and `change_version_id` (the command fixes those). Every contract key is present;
 *  unknown is null: a blank effort, no scope items, no output notes and a “Not known” choice are all null. `proof_upload` is null (a
 *  file upload is not part of this page: the proof is a recorded one chosen from the read). */
export function assessInputs(a: AssessChoice): Record<string, unknown> {
  const notes = Object.fromEntries(OUTPUT_KEYS.map((k) => [k, a.outputs[k].trim() === '' ? null : a.outputs[k].trim()]));
  return {
    contributor: a.team,
    cost_impact: choiceValue(a.cost),
    timeline_impact: choiceValue(a.timeline),
    client_facing: choiceValue(a.clientFacing),
    production_impact: choiceValue(a.production),
    scope_items: scopeItems(a.scope),
    outputs: OUTPUT_KEYS.every((k) => notes[k] === null) ? null : notes,
    effort_person_days: a.effort.trim() === '' ? null : a.effort.trim(),
    evidence: Number(a.evidence),
    note: a.note.trim(),
    proof_upload: null,
  };
}

export type DecideChoice = { role: Decider['role']; verdict: Verdict; note: string; evidence: string | undefined };

/** Why a decision may not be sent yet, or null: the verdict must be one the row lists, with a note and a listed proof. */
export function decideHeld(c: Change, d: DecideChoice): string | null {
  const row = c.decisions.find((x) => x.role === d.role);
  if (!row || !row.verdicts.includes(d.verdict)) return 'This decision isn’t open to you.';
  if (c.evidence.length === 0) return TEXT.noProof;
  if (d.note.trim() === '') return 'Add a note for this decision.';
  if (d.note.length > NOTE_LIMIT) return `Use ${NOTE_LIMIT} characters or fewer in the note.`;
  if (!listed(c, d.evidence)) return 'Choose the proof for this decision.';
  return null;
}

export const decideInputs = (d: DecideChoice): Record<string, unknown> => ({ role: d.role, verdict: d.verdict, evidence: Number(d.evidence), note: d.note.trim() });

export const authorizeOffered = (c: Change) => c.can_authorize && c.authorization_id === null;

/** `commercial` is one of the read's choices or null; a value the read does not list is never sent. */
export const authorizeInputs = (c: Change, commercial: string | undefined): Record<string, unknown> => ({
  commercial: commercial !== undefined && c.authorization_choices.some((id) => String(id) === commercial) ? Number(commercial) : null,
});

export const IDS = ['change.assess', 'change.decide', 'change.authorize'];

/** The three descriptors, from the read. The body carries `action`, both revisions from the read and `change_version_id` whatever the
 *  inputs say. A null revision is unknown: the write is disabled. No command for notice, execution, closure, retry or restart exists. */
export function changeCommands(rb: Readback, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const c = rb.change;
  const url = `/api/v1/work/${ctx.workId}/change`;
  const tokens = { expected_revision: c.expected_revision, case_revision: c.case_revision };
  const unknown = c.expected_revision == null || c.case_revision == null || ctx.revision === null ? TEXT.noToken : undefined;
  const base = { url, tokens, fixed: { change_version_id: c.change_version_id }, successStatuses: [201 as const] };
  const reason = (r: string | undefined) => (r ? { disabledReason: r } : {});
  return [
    makeCommand({ id: 'change.assess', label: 'Record assessment', ...base, ...reason(unknown ?? (c.assessors.length === 0 ? 'No assessment is open to you.' : undefined)) }),
    makeCommand({ id: 'change.decide', label: 'Record a decision', ...base, ...reason(unknown ?? (c.decisions.every((d) => d.verdicts.length === 0) ? 'No decision is open to you.' : undefined)) }),
    makeCommand({ id: 'change.authorize', label: 'Record the authorisation', ...base, ...reason(unknown ?? (authorizeOffered(c) ? undefined : 'The authorisation isn’t open to you.')) }),
  ];
}
