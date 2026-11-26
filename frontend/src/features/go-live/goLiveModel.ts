// F-114: go-live acceptance (SCR-45) on the live work item. Turns GET /work/{id}/go-live-signoff, GET .../go-live-replies and (only
// when a reply was declined) GET .../go-live-replies/decline into the Section objects the workspace renderer draws, and describes the
// writes. Presentation only: who may sign comes from the sign-off read answering (403 or 404 means not the appointed PM), what may be
// chosen comes from the served lists, and nothing here decides a business rule. A value a read does not give reads Unknown or "not
// available", never 0 and never blank.
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Signoff = Get<'/api/v1/work/{work_id}/go-live-signoff'>;
export type Replies = Get<'/api/v1/work/{work_id}/go-live-replies'>;
export type Decline = Get<'/api/v1/work/{work_id}/go-live-replies/decline'>;
export type Reply = Replies['replies'][number];
/** ok: the person read the sign-off; not_pm: the read answered 403 or 404; failed: any other failure of that read. */
export type Access = 'ok' | 'not_pm' | 'failed';
export type Readback = { signoff: Signoff | null; access: Access; replies: Replies | null; decline: Decline | null };

export const TEXT = {
  notSent: 'The go-live document hasn’t been sent to the client yet.',
  onlyPm: 'Only the appointed PM records the signatures.',
  hidden: 'Details not available to you',
  signoffFailed: 'We couldn’t load the signature record. Reload the page to try again.',
  repliesFailed: 'We couldn’t load the client’s replies. Reload the page to try again.',
  noToken: 'We don’t have this item’s current version yet. Reload and try again.',
  sameProof: 'Choose a different signature record for each signer',
  reconcile: 'Needs reconciliation: add the source system, reference, decision id and version from the signed record.',
  replyHeld: 'Recording the client’s reply isn’t available here yet: it needs a proof file this page can’t take yet.',
  remediationHeld: 'Reviewing the remediation isn’t available here yet: it needs a proof file this page can’t take yet.',
} as const;

export const NOTE_LIMIT = 4000;
export const FIELD_LIMIT = 160;
export const TITLE_LIMIT = 240;
export const NEXT_ACTION_LIMIT = 1000;
export const REASON_LIMIT = 2000;

const OUTCOME_WORDS: Record<string, string> = { changes_requested: 'Changes requested', declined: 'Declined', withdrawn: 'Withdrawn' };
const CHANNEL_WORDS: Record<string, string> = { email: 'Email', customer_portal: 'Customer portal', meeting: 'Meeting', phone: 'Phone', other: 'Other' };
const CHANGES_WORDS: Record<string, string> = { reviewed_document_successor: 'A reviewed new document', owner_review: 'The owner reviews it' };
const DECLINE_WORDS: Record<string, string> = { new_release_candidate: 'A new release candidate', owner_review: 'The owner reviews it' };

const humanise = (name: string) => {
  const spaced = name.replaceAll('_', ' ').trim();
  return spaced === '' ? 'Unknown' : spaced.charAt(0).toUpperCase() + spaced.slice(1);
};
const word = (words: Record<string, string>, key: string) => (Object.hasOwn(words, key) ? words[key] : humanise(key));

/** A date-time-local value as the ISO time the server reads, or null when it is not a time. */
export const isoOf = (value: string): string | null => {
  const at = new Date(value);
  return value && !Number.isNaN(at.getTime()) ? at.toISOString() : null;
};

/** The receipt of the latest delivery (the latest `recorded_at`; the later row when two tie), or null when nothing was sent. */
export function latestReceipt(s: Signoff): Signoff['receipts'][number] | null {
  let best: Signoff['receipts'][number] | null = null;
  for (const r of s.receipts) if (best === null || Date.parse(r.recorded_at) >= Date.parse(best.recorded_at)) best = r;
  return best;
}

/** The newest reply that is not withdrawn (highest `number`), or null. */
export function latestReply(r: Replies): Reply | null {
  let best: Reply | null = null;
  for (const x of r.replies) if (x.outcome !== 'withdrawn' && (best === null || x.number > best.number)) best = x;
  return best;
}

export const isAccepted = (r: Replies | null) => r !== null && r.milestone.acceptance_id !== null;

/** Whether the sign-off form is drawn: the person read the sign-off, something was delivered, and no acceptance or client reply has
 *  closed the version. The server stays the rule: it answers 409 or 422 to anything it will not take. */
export function showSignoff(rb: Readback): boolean {
  if (rb.access !== 'ok' || !rb.signoff || latestReceipt(rb.signoff) === null) return false;
  if (rb.replies === null) return true;
  return !isAccepted(rb.replies) && latestReply(rb.replies) === null;
}

const text = (id: string, value: string): Item => ({ id, text: value });
const fact = (id: string, label: string, value: string): Item => ({ id, label, value });

const hiddenReply = (x: Reply) => x.party === null && x.channel === null && x.responded_at === null && x.note === null && x.evidence_id === null;

/** "Reply 2 · Changes requested · Ngozi Bello · Email · 12 Nov 09:00"; a reply the person may not read says so once. */
function replyLine(x: Reply): string {
  const head = `Reply ${x.number} · ${word(OUTCOME_WORDS, x.outcome)}`;
  if (hiddenReply(x)) return `${head} · ${TEXT.hidden}`;
  const party = x.party ?? 'Unknown party';
  const channel = x.channel === null ? 'Unknown channel' : word(CHANNEL_WORDS, x.channel);
  const when = x.responded_at === null ? 'Unknown date' : formatDayTime(x.responded_at);
  return `${head} · ${party} · ${channel} · ${when}`;
}

function replyFacts(x: Reply): Section {
  const hidden = hiddenReply(x);
  const items: Item[] = hidden
    ? [text('hidden', TEXT.hidden)]
    : [
        fact('party', 'Client', x.party ?? 'Unknown'),
        fact('when', 'Replied', x.responded_at === null ? 'Unknown' : formatDayTime(x.responded_at)),
        fact('channel', 'Channel', x.channel === null ? 'Unknown' : word(CHANNEL_WORDS, x.channel)),
        ...(x.note !== null ? [text('note', `“${x.note}”`)] : [fact('note', 'Note', 'Unknown')]),
      ];
  return { key: 'latest-reply', kind: 'facts', title: x.outcome === 'declined' ? 'The client declined' : 'The client asked for changes', items };
}

function rulesSection(d: Decline): Section {
  const current = d.rules?.current ?? null;
  if (!current) return { key: 'rules', kind: 'text', title: 'Response rules', items: [text('none', 'No response rules set')] };
  const list = (values: string[], words?: Record<string, string>) => (values.length === 0 ? 'None set' : values.map((v) => (words ? word(words, v) : v)).join(', '));
  return {
    key: 'rules',
    kind: 'facts',
    title: 'Response rules',
    items: [
      fact('roles', 'Who records the reply', list(current.recording_roles)),
      fact('channels', 'Channels', list(current.channels, CHANNEL_WORDS)),
      fact('changes', 'When changes are asked for', word(CHANGES_WORDS, current.changes_handling)),
      fact('decline', 'When declined', word(DECLINE_WORDS, current.decline_handling)),
    ],
  };
}

function unlockSection(r: Replies): Section {
  const declined = r.replies.some((x) => x.outcome === 'declined');
  const count = (n: number, ids: string) => (n === 0 ? 'None yet' : `${n} · ${ids}`);
  const items: Item[] = [fact('acceptance', 'Acceptance', r.milestone.acceptance_id === null ? 'Not accepted yet' : `Accepted (#${r.milestone.acceptance_id})`)];
  if (declined) {
    items.push(fact('issues', 'Issues linked to this decline', count(r.linked_issues.length, r.linked_issues.map((l) => `#${l.issue_id}`).join(', '))));
    items.push(fact('handoffs', 'Reviewed handoffs', count(r.reviewed_handoffs.length, r.reviewed_handoffs.map((h) => `#${h.review_id}`).join(', '))));
  }
  if (r.milestone.name !== null) items.push(fact('milestone', 'Milestone', `${r.milestone.name} · ${r.milestone.recorded_id === null ? 'Not recorded yet' : 'Recorded'}`));
  return { key: 'unlocks', kind: 'facts', title: 'What this unlocks', items };
}

export function goLiveSections(rb: Readback): Section[] {
  const { signoff, replies, access } = rb;
  const out: Section[] = [];
  const lines: Item[] = [];
  if (replies && isAccepted(replies)) lines.push({ id: 'accepted', text: `Go-live accepted · acceptance #${replies.milestone.acceptance_id}`, tag: { label: 'Accepted', tone: 'verified' } });
  else if (signoff && signoff.prior_acceptance_id !== null) lines.push(text('earlier', `An earlier acceptance is on file (#${signoff.prior_acceptance_id})`));
  if (access === 'not_pm') lines.push(text('only-pm', TEXT.onlyPm));
  if (access === 'failed') lines.push(text('signoff-failed', TEXT.signoffFailed));
  if (replies === null) lines.push(text('replies-failed', TEXT.repliesFailed));
  if (signoff && latestReceipt(signoff) === null) lines.push(text('not-sent', TEXT.notSent));
  if (lines.length > 0) out.push({ key: 'state', kind: 'text', items: lines });

  const receipt = signoff ? latestReceipt(signoff) : null;
  if (receipt) out.push({ key: 'sent', kind: 'facts', title: 'Sent to the client', items: [fact('delivery', 'Delivery', `Delivery recorded ${formatDayTime(receipt.recorded_at)}`)] });

  if (replies) {
    const latest = latestReply(replies);
    if (latest) out.push(replyFacts(latest));
    if (replies.capture.length === 0) {
      if (replies.finding.trim() !== '') out.push({ key: 'capture', kind: 'text', title: 'Record the client’s reply', items: [text('finding', replies.finding)] });
    } else {
      out.push({ key: 'capture', kind: 'text', title: 'Record the client’s reply', items: [text('held', TEXT.replyHeld)] });
    }
    if (replies.replies.length > 0) {
      const sorted = [...replies.replies].sort((a, b) => a.number - b.number);
      const items: Item[] = [];
      for (const x of sorted) {
        items.push(text(`reply-${x.id}`, replyLine(x)));
        if (!hiddenReply(x) && x.note !== null && x.outcome !== 'withdrawn') items.push(text(`note-${x.id}`, `“${x.note}”`));
      }
      out.push({ key: 'history', kind: 'text', title: 'Replies so far', items });
    }
    out.push(unlockSection(replies));
  }
  if (rb.decline) out.push(rulesSection(rb.decline));
  return out;
}

// ---- the sign-off ----

export const SIGNER_FIELDS = [
  ['source_system', 'Source system'],
  ['source_reference', 'Source reference'],
  ['decision_id', 'Decision id'],
  ['decision_version', 'Decision version'],
  ['signer_reference', 'Signer reference'],
] as const;
export type SignerFields = Record<(typeof SIGNER_FIELDS)[number][0], string> & { signed_at: string };
export const emptySigner = (): SignerFields => ({ source_system: '', source_reference: '', decision_id: '', decision_version: '', signer_reference: '', signed_at: '' });

/** True when any of the signer's six source fields is empty or `signed_at` is not a time. Nothing is prefilled or guessed. */
export const signerNeedsReconciliation = (f: SignerFields) => SIGNER_FIELDS.some(([k]) => f[k].trim() === '') || isoOf(f.signed_at) === null;

export type SignoffChoice = { pm: string | undefined; client: string | undefined; signers: { PM: SignerFields; Client: SignerFields }; mode: string | undefined; note: string };
const listed = (s: Signoff, id: string | undefined) => id !== undefined && s.proofs.some((p) => String(p.id) === id);

/** Why "Record signatures" may not be pressed yet, or null. */
export function signoffHeld(s: Signoff, c: SignoffChoice): string | null {
  if (latestReceipt(s) === null) return TEXT.notSent;
  if (c.pm === undefined || c.client === undefined) return 'Choose a signed copy for each signer.';
  if (Number(c.pm) === Number(c.client)) return TEXT.sameProof;
  if (!listed(s, c.pm) || !listed(s, c.client)) return 'Choose a listed signature record for each signer.';
  if (signerNeedsReconciliation(c.signers.PM) || signerNeedsReconciliation(c.signers.Client)) return TEXT.reconcile;
  if (c.note.trim() === '') return 'Add a note.';
  return null;
}

const trimmed = (f: SignerFields) => ({
  source_system: f.source_system.trim(),
  source_reference: f.source_reference.trim(),
  decision_id: f.decision_id.trim(),
  decision_version: f.decision_version.trim(),
  signer_reference: f.signer_reference.trim(),
  signed_at: isoOf(f.signed_at) ?? '',
});

/** The inputs of POST /work/{id}/go-live-signoff beyond the tokens, `version_id` and `receipt_id` (the command fixes those from the
 *  read). `metadata_binding` is sent only when the read offers an earlier acceptance, with that id; otherwise `fresh_signatures`. */
export function signoffInputs(s: Signoff, c: SignoffChoice): Record<string, unknown> {
  const binding = c.mode === 'metadata_binding' && s.prior_acceptance_id !== null;
  return {
    pm_signature_id: Number(c.pm),
    client_signature_id: Number(c.client),
    signers: { PM: trimmed(c.signers.PM), Client: trimmed(c.signers.Client) },
    mode: binding ? 'metadata_binding' : 'fresh_signatures',
    prior_acceptance_id: binding ? s.prior_acceptance_id : null,
    note: c.note.trim(),
  };
}

// ---- the decline panel and the next version ----

export type IssueChoice = { replyId: number; issue: string | undefined; title: string; owner: string | undefined; nextAction: string; note: string };
export const NEW_ISSUE = 'new';

export function issueHeld(d: Decline, c: IssueChoice): string | null {
  const entry = d.issues.find((i) => i.reply_id === c.replyId);
  if (!entry) return 'There is nothing to link for this reply.';
  if (c.issue === undefined) return 'Choose an issue or create a new one.';
  if (c.issue === NEW_ISSUE) {
    if (c.title.trim() === '') return 'Add a title for the new issue.';
    if (c.owner === undefined || !entry.owners.some((o) => String(o.id) === c.owner)) return 'Choose an owner.';
  } else if (!entry.existing_issues.some((i) => String(i.id) === c.issue)) return 'Choose a listed issue.';
  if (c.note.trim() === '') return 'Add a note.';
  return null;
}

export function issueInputs(c: IssueChoice): Record<string, unknown> {
  const existing = c.issue !== undefined && c.issue !== NEW_ISSUE;
  return existing
    ? { reply_id: c.replyId, existing_issue_id: Number(c.issue), title: null, owner_id: null, next_action: null, note: c.note.trim() }
    : { reply_id: c.replyId, existing_issue_id: null, title: c.title.trim(), owner_id: Number(c.owner), next_action: c.nextAction.trim() === '' ? null : c.nextAction.trim(), note: c.note.trim() };
}

export type CandidateChoice = { replyId: number; reference: string; note: string };
export function candidateHeld(d: Decline, c: CandidateChoice): string | null {
  if (!d.new_candidates.some((n) => n.reply_id === c.replyId)) return 'There is no new release candidate to prepare for this reply.';
  if (c.reference.trim() === '') return 'Add a reference for the new candidate.';
  if (c.note.trim() === '') return 'Add a note.';
  return null;
}
/** `requirements_id` is the read's own entry for this reply, never typed. */
export function candidateInputs(d: Decline, c: CandidateChoice): Record<string, unknown> {
  const entry = d.new_candidates.find((n) => n.reply_id === c.replyId);
  return { reply_id: c.replyId, reference: c.reference.trim(), requirements_id: entry ? entry.requirements_id : null, note: c.note.trim() };
}

/** The declined replies that have at least one decline control the read supplies options for. */
export function declineReplies(rb: Readback): Reply[] {
  const { replies, decline } = rb;
  if (!replies || !decline) return [];
  return replies.replies.filter((x) => x.outcome === 'declined' && (decline.issues.some((i) => i.reply_id === x.id) || decline.new_candidates.some((n) => n.reply_id === x.id)));
}

/** Prepare v2 is offered only when the newest reply that is not withdrawn asks for changes. */
export const showSuccessor = (r: Replies | null) => r !== null && latestReply(r)?.outcome === 'changes_requested';

// ---- the descriptors ----

export const IDS = ['go-live.signoff', 'go-live.proof_pm', 'go-live.proof_client', 'go-live.successor', 'go-live.link_decline_issue', 'go-live.prepare_new_candidate'];

/** The write descriptors, from the reads. A null revision is unknown: the write is disabled. `action: null` bodies carry no `action`;
 *  nothing is put in `fixed` that the `action: null` rule would drop (makeCommand removes an `action` placed there). */
export function goLiveCommands(rb: Readback, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const route = `/api/v1/work/${ctx.workId}`;
  const known = (a: number | null | undefined, b: number | null | undefined) => (a != null && b != null && ctx.revision !== null ? undefined : TEXT.noToken);
  const out: CommandDescriptor[] = [];
  const { signoff: s, replies: r } = rb;
  if (s && rb.access === 'ok') {
    const receipt = latestReceipt(s);
    const tokens = { expected_revision: s.expected_revision, case_revision: s.case_revision };
    const reason = receipt === null ? TEXT.notSent : known(s.expected_revision, s.case_revision);
    out.push(
      makeCommand({ id: 'go-live.signoff', label: 'Record signatures', url: `${route}/go-live-signoff`, tokens, action: null, fixed: { version_id: s.version_id, receipt_id: receipt ? receipt.id : null }, successStatuses: [200], ...(reason ? { disabledReason: reason } : {}) }),
    );
    for (const role of ['PM', 'Client'] as const) {
      out.push(
        makeCommand({
          id: `go-live.proof_${role.toLowerCase()}`,
          label: 'Add signed copy',
          url: `${route}/go-live-signoff/proofs`,
          tokens: { case_revision: s.case_revision },
          action: null,
          fixed: { receipt_id: receipt ? receipt.id : null, role, checked: true },
          successStatuses: [201],
          ...(receipt === null ? { disabledReason: TEXT.notSent } : known(s.case_revision, s.case_revision) ? { disabledReason: TEXT.noToken } : {}),
        }),
      );
    }
  }
  if (r) {
    const tokens = { expected_revision: r.expected_revision, case_revision: r.case_revision };
    const reason = known(r.expected_revision, r.case_revision);
    const base = { url: `${route}/go-live-replies`, tokens, ...(reason ? { disabledReason: reason } : {}) };
    out.push(
      makeCommand({ id: 'go-live.successor', label: 'Prepare v2', ...base, url: `${route}/go-live-replies/successor`, action: null, fixed: { inputs: { template_id: null, checklist: null, incident_reporting: null, rollback: null } }, successStatuses: [200] }),
      makeCommand({ id: 'go-live.link_decline_issue', label: 'Link the issue', ...base, successStatuses: [201] }),
      makeCommand({ id: 'go-live.prepare_new_candidate', label: 'Prepare a new release candidate', ...base, successStatuses: [201] }),
    );
  }
  return out;
}
