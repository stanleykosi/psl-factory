// F-117: the handover model's rules without a page: what may be sent, from which read, and what is refused before any request.
import { describe, expect, it } from 'vitest';

import {
  ackHeld, ackInputs, emptyAck, emptyReply, handoverCommands, handoverSections, latestReply, parseGaps, replyHeld, replyInputs, statusSentence, TEXT,
  type Readback, type Receipts, type Replies, type Publication, type ReplyForm,
} from '@/features/delivery-handover/handoverModel';

// @ts-expect-error plain ESM module without type declarations
import { handoverLive } from '../mock/handover-live.mjs';

const read = (id: number, part: string) => {
  const [status, body] = handoverLive({ method: 'get', url: new URL(`http://mock/api/v1/work/${id}${part}`), scenario: undefined, csrfOk: true, persona: 'finance_lead' }) as [number, unknown];
  return status === 200 ? structuredClone(body) : null;
};
const fixture = (id: number): Readback => ({
  publication: read(id, '/support-publication') as Publication | null,
  replies: read(id, '/support-replies') as Replies | null,
  receipt: read(id, '/support-receipt') as Receipts | null,
  failed: [],
});
const ctx = { workId: 6101, revision: 8 };
const NOW = Date.parse('2026-11-26T12:00:00Z');
const form = (patch: Partial<ReplyForm> = {}): ReplyForm => ({ receipt: '8101', party: ' Femi Ojo ', role: 'Support lead', channel: 'email', when: '2026-11-25T11:00', status: 'received', gaps: '', note: ' Read it ', proof: '7301', ...patch });
const texts = (rb: Readback, state: Parameters<typeof handoverSections>[1]['state'] = 'waiting') => handoverSections(rb, { state }).flatMap((s) => s.items.map((i) => i.text ?? ''));

describe('the status sentence', () => {
  it('says Waiting to be published only from can_publish, Queued only from the processing state', () => {
    expect(statusSentence(fixture(6101), 'ready')).toBe('Waiting to be published');
    expect(statusSentence(fixture(6102), 'processing')).toBe('Queued for Support');
    expect(statusSentence(fixture(6103), 'waiting')).toBe('Not recorded');
  });
  it('counts the latest reply\'s gaps and says received only for a received reply', () => {
    expect(statusSentence(fixture(6104), 'action_needed')).toBe('Support found 2 gaps');
    expect(statusSentence(fixture(6105), 'verified')).toBe('Support received it');
    const one = fixture(6104);
    one.replies!.receipts[0].reply!.gaps = ['Only one'];
    expect(statusSentence(one, 'action_needed')).toBe('Support found 1 gap');
  });
  it('never says received, published or delivered from a read that has no reply', () => {
    for (const id of [6101, 6102, 6103, 6106, 6107]) expect(statusSentence(fixture(id), 'waiting')).not.toMatch(/received|delivered|acknowledged|^Published/i);
  });
});

describe('the sections', () => {
  it('draws gaps as numbered rows tagged Open only while the latest reply is gaps', () => {
    const gaps = handoverSections(fixture(6104), { state: 'action_needed' }).find((s) => s.key === 'gaps')!;
    expect(gaps.title).toBe('Support listed 2 gaps on 25 Nov');
    expect(gaps.items.map((i) => i.text)).toEqual(['1. No contact for the credit bureau outage', '2. Runbook misses the nightly export restart']);
    expect(gaps.items.every((i) => i.tag?.label === 'Open')).toBe(true);
    expect(handoverSections(fixture(6105), { state: 'verified' }).some((s) => s.key === 'gaps')).toBe(false);
    expect(JSON.stringify(handoverSections(fixture(6105), { state: 'verified' }))).not.toMatch(/Open|Replaced|closed|resolved/);
  });
  it('a reply with no status reads "No reply recorded yet"', () => {
    expect(texts(fixture(6103)).join('|')).toMatch(/Femi Ojo · No reply recorded yet/);
  });
  it('Acknowledged by Support is drawn only from a receipt row with a status; the PM\'s own record never says it', () => {
    expect(texts(fixture(6105)).join('|')).not.toMatch(/Acknowledged by Support/);
    expect(texts(fixture(6104)).join('|')).not.toMatch(/Acknowledged by Support/);
    const rb = fixture(6107);
    expect(texts(rb).join('|')).not.toMatch(/Acknowledged by Support/);
    rb.receipt!.receipts[0].status = 'gaps';
    expect(texts(rb)).toContain('Acknowledged by Support: Gaps found');
  });
  it('the document is drawn only for the real recipient (document non-null)', () => {
    expect(handoverSections(fixture(6107), { state: 'waiting' }).find((s) => s.key === 'document')!.title).toBe('Support handover · version 1');
    for (const id of [6101, 6104]) expect(handoverSections(fixture(id), { state: 'waiting' }).some((s) => s.key === 'document')).toBe(false);
  });
  it('a read with no view (403) is not an error: the other reads still draw, and nothing says failed', () => {
    const rb = fixture(6107);
    expect(rb.publication).toBeNull();
    expect(rb.replies).toBeNull();
    expect(texts(rb).join('|')).not.toMatch(/couldn’t load/);
    expect(handoverSections({ ...rb, failed: ['replies'] }, { state: 'waiting' })[0].items.map((i) => i.text)).toContain(TEXT.failedParts.replies);
  });
  it('an item with nothing to show draws only the status sentence', () => {
    const sections = handoverSections({ publication: { expected_revision: 1, case_revision: 1, can_publish: false, version_id: null }, replies: { ...fixture(6103).replies!, receipts: [], can_record: false }, receipt: null, failed: [] }, { state: 'waiting' });
    expect(sections.map((s) => s.key)).toEqual(['state']);
    expect(sections[0].items.map((i) => i.text)).toEqual(['Not recorded']);
  });
  it('the uncertain states say so and offer no publish', () => {
    expect(texts(fixture(6106), 'effect_uncertain')).toContain(TEXT.uncertain);
    expect(texts(fixture(6106), 'awaiting_reconciliation')).toContain(TEXT.uncertain);
    expect(handoverCommands(fixture(6106), ctx).map((c) => c.id)).toEqual([]);
  });
});

describe('the descriptors', () => {
  it('publish is described only when the read says can_publish and names the version; its body is the three keys, version from the read', () => {
    const cmd = handoverCommands(fixture(6101), ctx).find((c) => c.id === 'handover.publish')!;
    expect(cmd.disabledReason).toBeUndefined();
    expect(cmd.body({ version_id: 1, action: 'x', expected_revision: 1 })).toEqual({ version_id: 9101, expected_revision: 8, case_revision: 41 });
    expect(cmd.idempotency).toEqual({ field: null, value: null });
    for (const id of [6102, 6103, 6104, 6105]) expect(handoverCommands(fixture(id), ctx).map((c) => c.id)).not.toContain('handover.publish');
    const noVersion = fixture(6101);
    noVersion.publication!.version_id = null;
    expect(handoverCommands(noVersion, ctx)).toEqual([]);
    expect(handoverCommands({ ...fixture(6101), publication: { ...fixture(6101).publication!, can_publish: false } }, ctx)).toEqual([]);
  });
  it('a null revision stays null and disables the write with the words, never 0', () => {
    const rb = fixture(6101);
    rb.publication!.expected_revision = null as unknown as number;
    const cmd = handoverCommands(rb, ctx).find((c) => c.id === 'handover.publish')!;
    expect(cmd.disabledReason).toBe(TEXT.noToken);
    expect(cmd.body({}).expected_revision).toBeNull();
    expect(handoverCommands(fixture(6101), { workId: 6101, revision: null })[0].disabledReason).toBe(TEXT.noToken);
  });
  it('the reply and acknowledge commands take the revisions of their own read and carry no action or key', () => {
    const rb = fixture(6103);
    const cmd = handoverCommands(rb, ctx).find((c) => c.id === 'handover.record_reply')!;
    const body = cmd.body(replyInputs(rb.replies!, form()));
    expect(body).not.toHaveProperty('action');
    expect(body).toMatchObject({ expected_revision: 8, case_revision: 41 });
    const ack = handoverCommands(fixture(6107), ctx).find((c) => c.id === 'handover.acknowledge')!;
    expect(ack.body(ackInputs({ receipt: '8101', status: 'received', note: ' ok ', proof: '7401' }))).toEqual({ receipt_id: 8101, evidence_id: 7401, status: 'received', note: 'ok', expected_revision: 8, case_revision: 41 });
    expect(handoverCommands(fixture(6107), ctx).map((c) => c.id)).toEqual(['handover.acknowledge']);
  });
  it('no reply command is described when can_record is false', () => {
    expect(handoverCommands(fixture(6101), ctx).map((c) => c.id)).toEqual(['handover.publish']);
  });
});

describe('the reply body', () => {
  const r = () => fixture(6103).replies!;
  it('is the contract\'s eleven keys, trimmed, with previous_id null for a row with no reply and no gaps key for Received', () => {
    const body = replyInputs(r(), form());
    expect(body).toEqual({ receipt_id: 8101, previous_id: null, status: 'received', evidence_id: 7301, note: 'Read it', party: 'Femi Ojo', channel: 'email', responded_at: new Date('2026-11-25T11:00').toISOString(), role: 'Support lead' });
    expect(body).not.toHaveProperty('gaps');
  });
  it('a replacement names the record it replaces, as the row serves it', () => {
    const rb = fixture(6105).replies!;
    expect(replyInputs(rb, form({ role: 'PMO Lead' })).previous_id).toBe(9002);
  });
  it('Gaps found sends the gaps in order, trimmed, blank lines dropped', () => {
    expect(replyInputs(r(), form({ status: 'gaps', gaps: '  one  \n\n   \r\ntwo\n' })).gaps).toEqual(['one', 'two']);
  });
  it('the gaps parser refuses none, more than ten, and a line over 400 characters', () => {
    expect(parseGaps('').problem).toMatch(/at least one/);
    expect(parseGaps(' \n \n').problem).toMatch(/at least one/);
    expect(parseGaps(Array.from({ length: 11 }, (_, i) => `g${i}`).join('\n')).problem).toMatch(/at most 10/);
    expect(parseGaps(Array.from({ length: 10 }, (_, i) => `g${i}`).join('\n')).problem).toBeNull();
    expect(parseGaps('x'.repeat(401)).problem).toMatch(/400/);
    expect(parseGaps('x'.repeat(400)).problem).toBeNull();
  });
  it('Record stays off until every field is filled, from the read\'s lists, and not for a future time', () => {
    expect(replyHeld(r(), form(), NOW)).toBeNull();
    expect(replyHeld(r(), form({ receipt: undefined }), NOW)).toMatch(/recipient/);
    expect(replyHeld(r(), form({ party: '   ' }), NOW)).toMatch(/Who replied/i);
    expect(replyHeld(r(), form({ role: undefined }), NOW)).toMatch(/role/);
    expect(replyHeld(r(), form({ role: 'Admin' }), NOW)).toMatch(/role/);
    expect(replyHeld(r(), form({ channel: 'telegram' }), NOW)).toMatch(/how they replied/i);
    expect(replyHeld(r(), form({ when: '' }), NOW)).toMatch(/when/i);
    expect(replyHeld(r(), form({ when: 'soon' }), NOW)).toMatch(/when/i);
    expect(replyHeld(r(), form({ when: '2026-11-27T11:00' }), NOW)).toMatch(/future/);
    expect(replyHeld(r(), form({ status: undefined }), NOW)).toMatch(/what Support said/i);
    expect(replyHeld(r(), form({ status: 'gaps', gaps: '' }), NOW)).toMatch(/gap/);
    expect(replyHeld(r(), form({ note: '  ' }), NOW)).toMatch(/note/i);
    expect(replyHeld(r(), form({ note: 'n'.repeat(4001) }), NOW)).toMatch(/4000/);
    expect(replyHeld(r(), form({ proof: undefined }), NOW)).toMatch(/proof/i);
    expect(replyHeld(r(), form({ proof: '9999' }), NOW)).toMatch(/proof/i);
    expect(replyHeld({ ...r(), proofs: [] }, form(), NOW)).toBe(TEXT.noProof);
    expect(emptyReply().receipt).toBeUndefined();
  });
  it('the acknowledgement needs a listed receipt it may acknowledge, a status, a note and a listed proof', () => {
    const rc = fixture(6107).receipt!;
    expect(ackHeld(rc, { receipt: '8101', status: 'gaps', note: 'n', proof: '7401' })).toBeNull();
    expect(ackHeld(rc, { ...emptyAck(), status: 'gaps', note: 'n', proof: '7401' })).toMatch(/receipt/);
    expect(ackHeld(rc, { receipt: '8101', status: undefined, note: 'n', proof: '7401' })).toMatch(/received or gaps/);
    expect(ackHeld(rc, { receipt: '8101', status: 'gaps', note: ' ', proof: '7401' })).toMatch(/note/);
    expect(ackHeld(rc, { receipt: '8101', status: 'gaps', note: 'n', proof: '1' })).toMatch(/proof/);
  });
  it('latestReply takes the newest row with a status', () => {
    const rb = fixture(6104).replies!;
    rb.receipts.push({ ...rb.receipts[0], id: 8102, status: 'received', reply: { ...rb.receipts[0].reply!, responded_at: '2026-11-26T00:00:00Z', gaps: [] } });
    expect(latestReply(rb)!.id).toBe(8102);
    expect(latestReply(null)).toBeNull();
  });
});
