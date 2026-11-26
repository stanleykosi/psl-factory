// F-117: Handover to Support (SCR-48) on the live work item. Turns GET /work/{id}/support-publication, .../support-replies and
// .../support-receipt into the Section objects the workspace renderer draws, and describes the writes. Presentation only: who may
// publish, record or acknowledge is each read answering (can_publish, can_record, can_acknowledge; a 403 or 404 on a read means no
// view of it), what may be chosen comes from the served lists, and nothing here decides a business rule. A value a read does not
// give reads Unknown or "not recorded", never 0 and never blank. "Received", "queued" and "acknowledged" are said only from a read.
import type { paths } from '@/api/live-schema';
import { formatDayMonth, formatDayTime } from '@/components';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Publication = Get<'/api/v1/work/{work_id}/support-publication'>;
export type Replies = Get<'/api/v1/work/{work_id}/support-replies'>;
export type Receipts = Get<'/api/v1/work/{work_id}/support-receipt'>;
export type ReplyRow = Replies['receipts'][number];
export type AckRow = Receipts['receipts'][number];
/** Each part is null when the person has no view of it (403 or 404) or its read failed; `failed` names the reads that failed otherwise. */
export type Readback = { publication: Publication | null; replies: Replies | null; receipt: Receipts | null; failed: ('publication' | 'replies' | 'receipt')[] };

export const TEXT = {
  noToken: 'We don’t have this item’s current version yet. Reload and try again.',
  locked: 'Check the page before trying again.',
  consequence: 'Publishing sends it to Support. Then you record whether they received it or found gaps.',
  uncertain: 'We couldn’t confirm whether Support got it. Use Check what happened above. Don’t publish again until the page says it can be.',
  noReply: 'No reply recorded yet',
  noProof: 'No proof records available to attach yet',
  failedParts: { publication: 'We couldn’t load whether this can be published.', replies: 'We couldn’t load Support’s replies.', receipt: 'We couldn’t load Support’s receipt.' },
} as const;

export const NOTE_LIMIT = 4000;
export const GAP_LIMIT = 400;
export const MAX_GAPS = 10;

const CHANNEL_WORDS: Record<string, string> = { email: 'Email', whatsapp: 'WhatsApp', client_portal: 'Client portal', signed_document: 'Signed document', meeting: 'Meeting' };
const STATUS_WORDS: Record<string, string> = { received: 'Received', gaps: 'Gaps found' };
export const channelWord = (channel: string) => (Object.hasOwn(CHANNEL_WORDS, channel) ? CHANNEL_WORDS[channel] : channel.replaceAll('_', ' '));
const statusWord = (status: string) => (Object.hasOwn(STATUS_WORDS, status) ? STATUS_WORDS[status] : status);
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`;

/** A date-time-local value as the ISO time the server reads, or null when it is not a time. */
export const isoOf = (value: string): string | null => {
  const at = new Date(value);
  return value && !Number.isNaN(at.getTime()) ? at.toISOString() : null;
};

/** The row's own time: when the person replied, else when the delivery was recorded. */
const timeOf = (r: ReplyRow) => Date.parse(r.reply?.responded_at ?? r.recorded_at);

/** The newest row that has a status (the latest reply on file), or null. Ties go to the later row. */
export function latestReply(replies: Replies | null): ReplyRow | null {
  let best: ReplyRow | null = null;
  for (const r of replies?.receipts ?? []) if (r.status !== null && (best === null || timeOf(r) >= timeOf(best))) best = r;
  return best;
}

const gapsOf = (r: ReplyRow | null) => (r && r.status === 'gaps' ? (r.reply?.gaps ?? []) : []);

/** One sentence for the page's state, from the reads only. */
export function statusSentence(rb: Readback, state: LineContext['state']): string {
  if (rb.publication?.can_publish) return 'Waiting to be published';
  if (state === 'processing') return 'Queued for Support';
  const latest = latestReply(rb.replies);
  if (latest?.status === 'gaps') return `Support found ${plural(gapsOf(latest).length, 'gap')}`;
  if (latest?.status === 'received') return 'Support received it';
  return 'Not recorded';
}

const text = (id: string, value: string, extra: Partial<Item> = {}): Item => ({ id, text: value, ...extra });

function replyItem(r: ReplyRow): Item {
  if (r.status === null || r.reply === null) return text(`reply-${r.id}`, `${r.recipient} · ${TEXT.noReply}`);
  const { party, channel, responded_at: at, note } = r.reply;
  return text(`reply-${r.id}`, `${r.recipient} · ${statusWord(r.status)} · ${party} · ${channelWord(channel)} · ${formatDayTime(at)}`, {
    detail: `Recorded ${formatDayTime(r.recorded_at)}. “${note}”`,
  });
}

/** What the page draws, in order: the state, Support's reply, the gaps, the receipt Support gave itself. */
export function handoverSections(rb: Readback, ctx: Pick<LineContext, 'state'>): Section[] {
  const out: Section[] = [];
  const lines: Item[] = [text('sentence', statusSentence(rb, ctx.state))];
  if (ctx.state === 'effect_uncertain' || ctx.state === 'awaiting_reconciliation') lines.push(text('uncertain', TEXT.uncertain));
  for (const part of rb.failed) lines.push(text(`failed-${part}`, TEXT.failedParts[part]));
  out.push({ key: 'state', kind: 'text', items: lines });

  const { replies, receipt } = rb;
  if (replies && replies.receipts.length > 0) {
    out.push({ key: 'replies', kind: 'text', title: 'Support’s reply', items: replies.receipts.map(replyItem) });
  }
  const latest = latestReply(replies);
  const gaps = gapsOf(latest);
  if (latest && gaps.length > 0 && latest.reply) {
    // OPEN is drawn only while the newest reply still says gaps; no per-gap status is served, so no row says closed
    out.push({
      key: 'gaps',
      kind: 'text',
      title: `Support listed ${plural(gaps.length, 'gap')} on ${formatDayMonth(latest.reply.responded_at)}`,
      items: gaps.map((g, i) => text(`gap-${i}`, `${i + 1}. ${g}`, { tag: { label: 'Open', tone: 'stopped' } })),
    });
  }
  if (receipt) {
    const own = receipt.receipts.filter((r) => r.status !== null);
    if (own.length > 0) {
      out.push({ key: 'receipt', kind: 'text', title: 'Support receipt', items: own.map((r) => text(`ack-${r.id}`, `Acknowledged by Support: ${statusWord(r.status as string)}`)) });
    }
    if (receipt.document) {
      out.push({
        key: 'document',
        kind: 'text',
        title: `${receipt.document.title} · version ${receipt.document.version}`,
        items: receipt.document.sections.map((s, i) => text(`doc-${i}`, s.text, { label: s.heading })),
      });
    }
  }
  return out;
}

// ---- the gaps box ----

/** One gap per non-blank line, trimmed, in order; the problem is plain words, or null. Blank lines are dropped. */
export function parseGaps(raw: string): { gaps: string[]; problem: string | null } {
  const gaps = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l !== '');
  if (gaps.length === 0) return { gaps, problem: 'Add at least one gap, one per line.' };
  if (gaps.length > MAX_GAPS) return { gaps, problem: `Add at most ${MAX_GAPS} gaps.` };
  if (gaps.some((g) => g.length > GAP_LIMIT)) return { gaps, problem: `Keep each gap to ${GAP_LIMIT} characters.` };
  return { gaps, problem: null };
}

// ---- Record Support's reply ----

export type ReplyForm = {
  /** The chosen row's id, as text; undefined: not chosen. */
  receipt: string | undefined;
  party: string;
  role: string | undefined;
  channel: string | undefined;
  when: string;
  status: 'received' | 'gaps' | undefined;
  gaps: string;
  note: string;
  proof: string | undefined;
};
export const emptyReply = (): ReplyForm => ({ receipt: undefined, party: '', role: undefined, channel: undefined, when: '', status: undefined, gaps: '', note: '', proof: undefined });

const rowOf = (r: Replies, id: string | undefined) => (id === undefined ? undefined : r.receipts.find((x) => String(x.id) === id));

/** Why "Record" may not be pressed yet, or null. Nothing is prefilled or guessed. */
export function replyHeld(r: Replies, f: ReplyForm, now: number = Date.now()): string | null {
  if (rowOf(r, f.receipt) === undefined) return 'Choose which Support recipient replied.';
  if (f.party.trim() === '') return 'Add who replied.';
  if (f.role === undefined || !r.roles.includes(f.role)) return 'Choose the role you are recording as.';
  if (f.channel === undefined || !r.channels.includes(f.channel as never)) return 'Choose how they replied.';
  const at = isoOf(f.when);
  if (at === null) return 'Add when they replied.';
  if (Date.parse(at) > now) return 'The time they replied can’t be in the future.';
  if (f.status === undefined) return 'Choose what Support said.';
  if (f.status === 'gaps') {
    const { problem } = parseGaps(f.gaps);
    if (problem) return problem;
  }
  if (f.note.trim() === '') return 'Add a note.';
  if (f.note.length > NOTE_LIMIT) return `Keep the note to ${NOTE_LIMIT} characters.`;
  if (f.proof === undefined || !r.proofs.some((p) => String(p.id) === f.proof)) return r.proofs.length === 0 ? TEXT.noProof : 'Choose a proof record.';
  return null;
}

/** The inputs of POST support-replies beyond the two revisions. `previous_id` is the row's own `previous_id` as served (null while the
 *  row has no reply): a replacement names the record it replaces and never edits it. `gaps` is sent only for Gaps found. */
export function replyInputs(r: Replies, f: ReplyForm): Record<string, unknown> {
  const row = rowOf(r, f.receipt);
  return {
    receipt_id: row ? row.id : null,
    previous_id: row ? row.previous_id : null,
    status: f.status,
    evidence_id: Number(f.proof),
    note: f.note.trim(),
    party: f.party.trim(),
    channel: f.channel,
    responded_at: isoOf(f.when),
    role: f.role,
    ...(f.status === 'gaps' ? { gaps: parseGaps(f.gaps).gaps } : {}),
  };
}

// ---- Support's own acknowledgement ----

export type AckForm = { receipt: string | undefined; status: 'received' | 'gaps' | undefined; note: string; proof: string | undefined };
export const emptyAck = (): AckForm => ({ receipt: undefined, status: undefined, note: '', proof: undefined });

export function ackRows(r: Receipts | null): AckRow[] {
  return r ? r.receipts.filter((x) => x.can_acknowledge) : [];
}

export function ackHeld(r: Receipts, f: AckForm): string | null {
  if (!ackRows(r).some((x) => String(x.id) === f.receipt)) return 'Choose which receipt you are acknowledging.';
  if (f.status === undefined) return 'Choose received or gaps found.';
  if (f.note.trim() === '') return 'Add a note.';
  if (f.note.length > NOTE_LIMIT) return `Keep the note to ${NOTE_LIMIT} characters.`;
  if (f.proof === undefined || !r.proofs.some((p) => String(p.id) === f.proof)) return r.proofs.length === 0 ? TEXT.noProof : 'Choose a proof record.';
  return null;
}

export const ackInputs = (f: AckForm): Record<string, unknown> => ({ receipt_id: Number(f.receipt), evidence_id: Number(f.proof), status: f.status, note: f.note.trim() });

// ---- the descriptors ----

export const IDS = ['handover.publish', 'handover.record_reply', 'handover.acknowledge'];

/** The write descriptors, from the reads, each with the revisions of the read it was built from (never the other reads'). A null
 *  revision is unknown: the write is disabled. No body has an `action` or a key field: `action: null` and nothing in `fixed` that
 *  rule would drop. Publish is described only when the read says it can be and names the version; the version is never typed. */
export function handoverCommands(rb: Readback, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const route = `/api/v1/work/${ctx.workId}`;
  const reason = (a: number | null | undefined, b: number | null | undefined) => (a != null && b != null && ctx.revision !== null ? {} : { disabledReason: TEXT.noToken });
  const out: CommandDescriptor[] = [];
  const { publication: p, replies: r, receipt: c } = rb;
  if (p && p.can_publish && p.version_id !== null) {
    out.push(
      makeCommand({ id: 'handover.publish', label: 'Publish to Support', url: `${route}/support-publication`, tokens: { expected_revision: p.expected_revision, case_revision: p.case_revision }, action: null, fixed: { version_id: p.version_id }, successStatuses: [202], ...reason(p.expected_revision, p.case_revision) }),
    );
  }
  if (r && r.can_record) {
    out.push(makeCommand({ id: 'handover.record_reply', label: 'Record reply', url: `${route}/support-replies`, tokens: { expected_revision: r.expected_revision, case_revision: r.case_revision }, action: null, successStatuses: [201], ...reason(r.expected_revision, r.case_revision) }));
  }
  if (c && ackRows(c).length > 0) {
    out.push(makeCommand({ id: 'handover.acknowledge', label: 'Acknowledge', url: `${route}/support-receipt`, tokens: { expected_revision: c.expected_revision, case_revision: c.case_revision }, action: null, successStatuses: [200], ...reason(c.expected_revision, c.case_revision) }));
  }
  return out;
}
