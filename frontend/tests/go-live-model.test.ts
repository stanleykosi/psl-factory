// F-114: the go-live model's rules without a page: what may be sent, from which read, and what is refused before any request.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { refuseFile, type EvidenceId, type UploadId } from '@/features/workspace/evidence';
import {
  candidateHeld, candidateInputs, declineReplies, emptySigner, goLiveCommands, goLiveSections, issueHeld, issueInputs, latestReceipt, latestReply, NEW_ISSUE, showSignoff, showSuccessor, signoffHeld, signoffInputs, TEXT,
  type Decline, type Readback, type Replies, type Signoff, type SignerFields,
} from '@/features/go-live/goLiveModel';

// @ts-expect-error plain ESM module without type declarations
import { goLiveLive } from '../mock/go-live.mjs';

const read = (id: number, part: string) => {
  const [status, body] = goLiveLive({ method: 'get', url: new URL(`http://mock/api/v1/work/${id}${part}`), scenario: undefined, csrfOk: true, persona: 'finance_lead' }) as [number, unknown];
  return status === 200 ? body : null;
};
const fixture = (id: number): Readback => {
  const replies = read(id, '/go-live-replies') as Replies;
  return { signoff: read(id, '/go-live-signoff') as Signoff | null, access: read(id, '/go-live-signoff') ? 'ok' : 'not_pm', replies, decline: read(id, '/go-live-replies/decline') as Decline | null };
};
const ctx = { workId: 4411, revision: 6 };
const full = (): SignerFields => ({ source_system: ' DocuSign ', source_reference: 'ENV-1', decision_id: 'D-9', decision_version: '2', signer_reference: 'S-1', signed_at: '2026-11-25T11:00' });
const choice = (patch = {}) => ({ pm: '61', client: '62', signers: { PM: full(), Client: full() }, mode: 'fresh_signatures', note: 'n', ...patch });

describe('the descriptors', () => {
  it('a signature body has no action, both revisions, and the version and receipt from the read whatever the inputs say', () => {
    const rb = fixture(4411);
    const cmd = goLiveCommands(rb, ctx).find((c) => c.id === 'go-live.signoff')!;
    expect(cmd.disabledReason).toBeUndefined();
    const body = cmd.body({ ...signoffInputs(rb.signoff!, choice()), action: 'x', version_id: 999, receipt_id: 999, expected_revision: 1 });
    expect(body).not.toHaveProperty('action');
    expect(body).toMatchObject({ expected_revision: 6, case_revision: 41, version_id: 11, receipt_id: 51, pm_signature_id: 61, client_signature_id: 62 });
  });
  it('a proof body is the contract\'s five keys: role and checked are the descriptor\'s, never the inputs\'', () => {
    const rb = fixture(4411);
    const cmd = goLiveCommands(rb, ctx).find((c) => c.id === 'go-live.proof_client')!;
    expect(cmd.body({ upload_id: 8001, role: 'PM', checked: false })).toEqual({ upload_id: 8001, role: 'Client', checked: true, receipt_id: 51, case_revision: 41 });
    expect(goLiveCommands(rb, ctx).find((c) => c.id === 'go-live.proof_pm')!.body({ upload_id: 8002 })).toMatchObject({ role: 'PM' });
  });
  it('an unknown (null) revision disables every write with the words, and a read with no receipt disables the sign-off', () => {
    const rb = fixture(4411);
    for (const c of goLiveCommands(rb, { workId: 4411, revision: null })) expect(c.disabledReason).toBe(TEXT.noToken);
    const blank = { ...rb, signoff: { ...rb.signoff!, expected_revision: null as unknown as number } };
    expect(goLiveCommands(blank, ctx).find((c) => c.id === 'go-live.signoff')!.disabledReason).toBe(TEXT.noToken);
    const empty = fixture(4420);
    expect(goLiveCommands(empty, ctx).find((c) => c.id === 'go-live.signoff')!.disabledReason).toBe(TEXT.notSent);
    expect(goLiveCommands(empty, ctx).find((c) => c.id === 'go-live.proof_pm')!.disabledReason).toBe(TEXT.notSent);
  });
  it('the replies commands carry the replies read\'s revisions; v2 sends four null inputs', () => {
    const rb = fixture(4413);
    const v2 = goLiveCommands(rb, ctx).find((c) => c.id === 'go-live.successor')!;
    expect(v2.url).toBe('/api/v1/work/4411/go-live-replies/successor');
    expect(v2.body({ reason: 'r' })).toEqual({ reason: 'r', inputs: { template_id: null, checklist: null, incident_reporting: null, rollback: null }, expected_revision: 6, case_revision: 41 });
    expect(goLiveCommands(rb, ctx).find((c) => c.id === 'go-live.link_decline_issue')!.body({ reply_id: 1 })).toMatchObject({ action: 'link_decline_issue' });
  });
  it('no sign-off command is described for a person the sign-off read refused', () => {
    expect(goLiveCommands(fixture(4415), ctx).map((c) => c.id)).not.toContain('go-live.signoff');
  });
});

describe('what may be pressed', () => {
  const s = () => fixture(4411).signoff!;
  it('refuses the same record for both signers, however it is written', () => {
    for (const [pm, client] of [['61', '61'], ['61', '061'], ['62', '62.0']] as const) expect(signoffHeld(s(), choice({ pm, client }))).toBe(TEXT.sameProof);
  });
  it('refuses a record the read does not list, an unchosen record, and an empty or blank field of either signer', () => {
    expect(signoffHeld(s(), choice({ client: '999' }))).toMatch(/listed/);
    expect(signoffHeld(s(), choice({ pm: undefined }))).toMatch(/Choose a signed copy/);
    for (const role of ['PM', 'Client'] as const) {
      for (const key of Object.keys(emptySigner()) as (keyof SignerFields)[]) {
        for (const blank of ['', '   ', '\t\n']) {
          const signers = { PM: full(), Client: full() };
          signers[role] = { ...signers[role], [key]: blank };
          expect(signoffHeld(s(), choice({ signers }))).toBe(TEXT.reconcile);
        }
      }
    }
    expect(signoffHeld(s(), choice({ signers: { PM: full(), Client: { ...full(), signed_at: 'not a time' } } }))).toBe(TEXT.reconcile);
    expect(signoffHeld(s(), choice({ note: '   ' }))).toBe('Add a note.');
    expect(signoffHeld(s(), choice())).toBeNull();
  });
  it('nothing is held to sign for when nothing was delivered', () => {
    expect(signoffHeld(fixture(4420).signoff!, choice())).toBe(TEXT.notSent);
  });
  it('binds only when the read offers an earlier acceptance, and then with that id; otherwise fresh with null', () => {
    const plain = signoffInputs(s(), choice({ mode: 'metadata_binding' }));
    expect(plain).toMatchObject({ mode: 'fresh_signatures', prior_acceptance_id: null });
    const prior = fixture(4416).signoff!;
    expect(signoffInputs(prior, choice({ mode: 'metadata_binding' }))).toMatchObject({ mode: 'metadata_binding', prior_acceptance_id: 6990 });
    expect(signoffInputs(prior, choice({ mode: 'fresh_signatures' }))).toMatchObject({ mode: 'fresh_signatures', prior_acceptance_id: null });
  });
  it('trims every signer field and sends the signed time as an ISO time', () => {
    const body = signoffInputs(s(), choice()) as { signers: { PM: Record<string, string> } };
    expect(body.signers.PM.source_system).toBe('DocuSign');
    expect(body.signers.PM.signed_at).toBe(new Date('2026-11-25T11:00').toISOString());
  });
  it('the sign-off form is drawn only with a receipt, no acceptance and no client reply; never for a person the read refused', () => {
    expect(showSignoff(fixture(4411))).toBe(true);
    expect(showSignoff(fixture(4416))).toBe(true);
    for (const id of [4412, 4413, 4414, 4415, 4420]) expect(showSignoff(fixture(id)), String(id)).toBe(false);
  });
  it('the latest reply ignores withdrawn rows; Prepare v2 follows only a request for changes', () => {
    expect(latestReply(fixture(4419).replies!)?.number).toBe(1);
    expect(showSuccessor(fixture(4419).replies)).toBe(true);
    expect(showSuccessor(fixture(4414).replies)).toBe(false);
    expect(showSuccessor(fixture(4411).replies)).toBe(false);
    expect(showSuccessor(null)).toBe(false);
  });
  it('the latest receipt wins by time', () => {
    const s0 = s();
    expect(latestReceipt({ ...s0, receipts: [{ id: 1, recorded_at: '2026-11-25T10:00:00Z' }, { id: 2, recorded_at: '2026-11-26T10:00:00Z' }, { id: 3, recorded_at: '2026-11-24T10:00:00Z' }] })?.id).toBe(2);
    expect(latestReceipt({ ...s0, receipts: [] })).toBeNull();
  });
});

describe('the decline panel', () => {
  const rb = () => fixture(4414);
  it('draws controls only for a declined reply the read gives options for', () => {
    expect(declineReplies(rb()).map((r) => r.id)).toEqual([21]);
    expect(declineReplies(fixture(4422))).toEqual([]);
    expect(declineReplies(fixture(4413))).toEqual([]);
  });
  it('an issue is a listed one or a new one with a listed owner; a reply with no entry is refused', () => {
    const d = rb().decline!;
    const base = { replyId: 21, issue: '301', title: '', owner: undefined, nextAction: '', note: 'n' };
    expect(issueHeld(d, base)).toBeNull();
    expect(issueHeld(d, { ...base, issue: '999' })).toMatch(/listed/);
    expect(issueHeld(d, { ...base, replyId: 22 })).toMatch(/nothing to link/);
    expect(issueHeld(d, { ...base, issue: NEW_ISSUE })).toMatch(/title/);
    expect(issueHeld(d, { ...base, issue: NEW_ISSUE, title: 't', owner: '999' })).toMatch(/owner/);
    expect(issueHeld(d, { ...base, issue: NEW_ISSUE, title: 't', owner: '31' })).toBeNull();
    expect(issueInputs({ ...base, issue: NEW_ISSUE, title: ' t ', owner: '31', nextAction: '   ' })).toMatchObject({ existing_issue_id: null, title: 't', owner_id: 31, next_action: null });
  });
  it('a candidate takes its requirements id from the read, never from the form', () => {
    const d = rb().decline!;
    expect(candidateHeld(d, { replyId: 21, reference: 'R', note: 'n' })).toBeNull();
    expect(candidateHeld(d, { replyId: 22, reference: 'R', note: 'n' })).toMatch(/no new release candidate/);
    expect(candidateInputs(d, { replyId: 21, reference: ' R ', note: 'n' })).toEqual({ reply_id: 21, reference: 'R', requirements_id: 81, note: 'n' });
  });
});

describe('what is drawn', () => {
  const texts = (rb: Readback) => goLiveSections(rb).flatMap((s) => [s.title ?? '', ...s.items.flatMap((i) => [i.text ?? '', i.label ?? '', typeof i.value === 'string' ? i.value : ''])]);
  it('never says 0, null or blank for an unknown value, and a hidden reply says so', () => {
    const all = texts(fixture(4418)).join('|');
    expect(all).toContain(TEXT.hidden);
    expect(all).not.toMatch(/\bnull\b|undefined|NaN/);
  });
  it('nothing about hypercare, archive or marking a milestone is drawn on an accepted item', () => {
    const all = texts(fixture(4412)).join('|');
    expect(all).not.toMatch(/Hypercare|Archive|Mark milestone/i);
    expect(all).toContain('Go-live accepted');
  });
  it('a failed read of one part names it; the other still draws', () => {
    const rb = { ...fixture(4411), replies: null };
    expect(texts(rb)).toContain(TEXT.repliesFailed);
    expect(texts({ ...fixture(4411), signoff: null, access: 'failed' as const })).toContain(TEXT.signoffFailed);
  });
});

describe('the evidence types and the routes (AC21, AC22)', () => {
  it('a PDF is accepted; an executable and an over-size file are refused before any request', () => {
    expect(refuseFile({ name: 'signed.PDF', size: 1000 })).toBeNull();
    expect(refuseFile({ name: 'run.exe', size: 10 })).not.toBeNull();
    expect(refuseFile({ name: 'big.pdf', size: 1024 * 1024 * 1024 })).not.toBeNull();
  });
  it('an upload id cannot stand where an evidence id is expected', () => {
    const needsEvidence = (id: EvidenceId) => id;
    const upload = 5 as UploadId;
    // @ts-expect-error an UploadId is not an EvidenceId
    needsEvidence(upload);
    expect(true).toBe(true);
  });
  it('the feature calls only the go-live routes in the contract, and never a message or email route', () => {
    const dir = join(__dirname, '../src/features/go-live');
    const source = readdirSync(dir).filter((n) => /\.(ts|tsx)$/.test(n)).map((n) => readFileSync(join(dir, n), 'utf8')).join('\n');
    const routes = [...source.matchAll(/liveApi\.(GET|POST)\(\s*'([^']+)'/g)].map((m) => `${m[1]} ${m[2]}`).sort();
    expect(routes).toEqual(['GET /api/v1/work/{work_id}/go-live-replies', 'GET /api/v1/work/{work_id}/go-live-replies/decline', 'GET /api/v1/work/{work_id}/go-live-signoff']);
    // the writes go through the descriptors, to these urls only
    const urls = [...source.matchAll(/url: `\$\{route\}([^`]*)`/g)].map((m) => m[1]).sort();
    expect(urls).toEqual(['/go-live-replies', '/go-live-replies/successor', '/go-live-signoff', '/go-live-signoff/proofs']);
    expect(source).not.toMatch(/\/(emails?|messages?|notifications?)\b|sendMail|notify/i);
  });
});
