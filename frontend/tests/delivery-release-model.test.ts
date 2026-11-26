// F-113B: the release gates model: board states, D-14 words, sections, and the three write bodies. Pure functions over the mock's reads.
import { describe, expect, it } from 'vitest';

import type { EvidenceId, UploadId } from '@/features/workspace/evidence';
import { boardState, decideInputs, decisionHeld, NO_EVIDENCE, NOT_YET, observeInputs, releaseCommands, releaseSections, statusWords, type PlanningExit, type Readback, type Register } from '@/features/delivery-release/releaseModel';

// @ts-expect-error plain ESM module without type declarations
import { releaseLive } from '../mock/delivery-release.mjs';

const get = (path: string) => releaseLive({ method: 'get', url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead' })[1];
const readback = (id: number): Readback => ({ register: get(`/api/v1/work/${id}/release-register`) as Register, exit: get(`/api/v1/work/${id}/planning-exit`) as PlanningExit, uat: null, appointments: null });
const ctx = (id: number, state = 'action_needed') => ({ workId: id, caseId: `00000000-0000-4000-8000-00000000${id}`, revision: 6 as number | null, caseRevision: 41, state }) as Parameters<typeof releaseSections>[1] & { workId: number; revision: number | null };
const ev = (n: number) => n as EvidenceId;

describe('the board state (AC4)', () => {
  const state = (id: number, s = 'action_needed') => boardState(readback(id), ctx(id, s));
  it('picks each state from the reads', () => {
    expect(state(4804)).toBe('default');
    expect(state(4801)).toBe('decision');
    expect(state(4805)).toBe('returned');
    expect(state(4807, 'owner_needed')).toBe('owner_needed');
    expect(state(4808)).toBe('readiness');
    expect(state(4809)).toBe('readiness');
    expect(state(4810)).toBe('ready');
    expect(state(4811)).toBe('ready');
  });
  it('a null packet with verdicts is not a decision', () => expect(state(4803)).toBe('default'));
  it('the later state wins: ready over readiness over owner-needed over returned over decision', () => {
    const rb = readback(4801);
    expect(boardState({ ...rb, exit: { ...rb.exit, latest_decision: { ...rb.exit.latest_decision!, verdict: 'return' } as never } }, ctx(4801))).toBe('returned');
    const approved = { ...rb.exit, latest_decision: { id: 1, verdict: 'approve', role: 'PMO Lead', by: 'A', at: '2026-11-25T10:00:00Z', direct: false } } as PlanningExit;
    expect(boardState({ ...rb, exit: approved }, ctx(4801, 'owner_needed'))).toBe('readiness');
    expect(boardState({ register: { ...rb.register, readiness_ids: [1] }, exit: approved }, ctx(4801))).toBe('ready');
    expect(boardState(rb, ctx(4801, 'owner_needed'))).toBe('owner_needed');
  });
});

describe('the D-14 words (AC2)', () => {
  it('maps the five statuses and shows any other value as given in capitals', () => {
    expect(statusWords('current')).toEqual({ text: 'CURRENT', tone: 'verified' });
    expect(statusWords('stale_scope').text).toBe('STALE SCOPE');
    expect(statusWords('restricted_or_authority_changed').text).toBe('AUTHORITY CHANGED');
    expect(statusWords('unknown_or_stale').text).toBe('UNKNOWN OR STALE');
    expect(statusWords('unknown').text).toBe('UNKNOWN');
    expect(statusWords('made_up')).toEqual({ text: 'MADE UP', tone: 'neutral' });
    expect(statusWords('').text).toBe('UNKNOWN');
  });
  it('only "current" is drawn as done', () => {
    for (const s of ['stale_scope', 'restricted_or_authority_changed', 'unknown_or_stale', 'unknown', 'other']) expect(statusWords(s).tone).not.toBe('verified');
  });
});

describe('the sections', () => {
  const sections = (id: number, s?: string, extra: Partial<Readback> = {}) => releaseSections({ ...readback(id), ...extra }, ctx(id, s));
  it('draws four phases in the given order with their checks (AC1)', () => {
    const titles = sections(4801).filter((x) => x.key.startsWith('phase-')).map((x) => x.title);
    expect(titles).toEqual(['Initiation', 'Planning', 'Execution', 'Closure']);
  });
  it('a check with no records has no records cell, so no "0 records" (AC3)', () => {
    const planning = sections(4801).find((x) => x.title === 'Planning')!;
    const [noRecords, oneRecord] = planning.items;
    expect(noRecords.cells!.map((c) => c.column)).toEqual(['check', 'authority', 'status']);
    expect(oneRecord.cells!.find((c) => c.column === 'records')!.text).toBe('1 record');
    expect(JSON.stringify(sections(4801))).not.toMatch(/\b0 records?\b/);
  });
  it('an out-of-scope record shows the plain line and no gates', () => {
    const rb = readback(4801);
    const out = releaseSections({ ...rb, register: { ...rb.register, current_scope: false } }, ctx(4801));
    expect(out.some((x) => x.key.startsWith('phase-'))).toBe(false);
    expect(JSON.stringify(out)).toContain('This record is not for the current scope.');
  });
  it('the planning row gives the checklist as given and "No decision yet" for none', () => {
    const planning = sections(4804).find((x) => x.key === 'planning')!;
    expect(planning.items.map((i) => i.label)).toEqual(['Planning sources', 'Planning decision', 'Latest decision']);
    expect(planning.items.at(-1)!.value).toBe('No decision yet');
  });
  it('the returned state names who returned it, shows blockers as text and no note or resend (AC14, AC15)', () => {
    const text = JSON.stringify(sections(4805));
    expect(text).toMatch(/Kemi Adebayo returned the release on 25 Nov 15:30/);
    expect(text).toContain('ISS-0301');
    expect(text).not.toMatch(/Send for decision again|Client workaround/);
    expect(JSON.stringify(sections(4806))).toContain('Client workaround on file');
  });
  it('the waiting lines: viewer who cannot decide, and a packet not yet ready', () => {
    expect(JSON.stringify(sections(4804))).toContain('Waiting for the PMO Lead');
    expect(JSON.stringify(sections(4803))).toContain('Waiting for the packet');
    expect(JSON.stringify(sections(4801))).not.toMatch(/Waiting for/);
  });
  it('readiness and ready say "Approved by PMO Lead" with the name and time from the read, and the recorded release', () => {
    expect(JSON.stringify(sections(4808))).toMatch(/Preparing release readiness/);
    expect(JSON.stringify(sections(4808))).toMatch(/Approved by PMO Lead, Kemi Adebayo, 25 Nov 15:30 · approved directly/);
    const ready = JSON.stringify(sections(4810));
    expect(ready).toMatch(/Release ready · 1 readiness record/);
    expect(ready).not.toMatch(/Release recorded/);
    expect(JSON.stringify(sections(4811))).toMatch(/Release recorded 25 Nov 17:00 · REL-2026-044 · Production/);
  });
  it('the role words are left out when the role does not say PMO Lead', () => {
    const rb = readback(4809);
    const odd = { ...rb, exit: { ...rb.exit, latest_decision: { ...rb.exit.latest_decision!, role: 'someone' } } };
    expect(JSON.stringify(releaseSections(odd, ctx(4809)))).toMatch(/Approved by Kemi Adebayo,/);
  });
  it('the client testing row (AC22)', () => {
    const base = { case_revision: 1, target_id: null, response_id: null, inspection_id: null, review_id: null, binding_id: null, gate_id: null, contact_choices: [], owned_files: [], proof_files: [] };
    const uat = (patch: object) => JSON.stringify(sections(4801, undefined, { uat: { ...base, outcome: null, proof_current: true, binding_current: true, ...patch } as never }).find((x) => x.key === 'uat'));
    expect(uat({})).toContain('No response recorded');
    expect(uat({ outcome: 'approved_with_workaround', proof_current: false, binding_current: false })).toMatch(/Approved with workaround.*Proof is out of date.*Not tied to this release/);
    expect(uat({ outcome: 'changes_requested' })).toContain('Changes requested');
    expect(sections(4801).some((x) => x.key === 'uat')).toBe(false);
  });
  it('the owner-needed state draws Owner needed and the people and eligibility as given (AC16)', () => {
    const appointments = { case_revision: 1, latest_id: null, active_id: null, people: [{ id: 31, label: 'Tunde Bello' }], proofs: [], can_draft: false, appointments: [{ user_id: 31, roles: ['PM'], eligibility: 'Eligible' }], next_page: null };
    const text = JSON.stringify(sections(4807, 'owner_needed', { appointments }));
    expect(text).toMatch(/PMO Lead assigned.*Owner needed/);
    expect(text).toMatch(/Tunde Bello.*PM.*Eligible/);
  });
  it('draws none of the removed figures (AC23)', () => {
    for (const id of [4801, 4805, 4808]) expect(JSON.stringify(sections(id))).not.toMatch(/Tola|open issues by|changes since|Send for decision again|Reject/);
  });
});

describe('the decision rules (AC5 to AC9)', () => {
  const exit = (id: number) => readback(id).exit;
  it('a direct approval needs no evidence; every other decision needs a chosen proof', () => {
    expect(decisionHeld(exit(4801), { verdict: 'approve', note: '', evidenceId: null })).toBeNull();
    expect(decisionHeld(exit(4814), { verdict: 'approve', note: '', evidenceId: null })).toMatch(/Choose the evidence/);
    expect(decisionHeld(exit(4814), { verdict: 'approve', note: '', evidenceId: ev(61) })).toBeNull();
    expect(decisionHeld(exit(4802), { verdict: 'approve', note: '', evidenceId: null })).toBe(NO_EVIDENCE);
    expect(decisionHeld(exit(4813), { verdict: 'approve', note: '', evidenceId: null })).toBeNull();
  });
  it('a return needs a note and a proof, even for a direct approver', () => {
    expect(decisionHeld(exit(4801), { verdict: 'return', note: '', evidenceId: ev(61) })).toMatch(/note/);
    expect(decisionHeld(exit(4801), { verdict: 'return', note: '   ', evidenceId: ev(61) })).toMatch(/note/);
    expect(decisionHeld(exit(4801), { verdict: 'return', note: 'No', evidenceId: null })).toMatch(/evidence/);
    expect(decisionHeld(exit(4813), { verdict: 'return', note: 'No', evidenceId: null })).toBe(NO_EVIDENCE);
    expect(decisionHeld(exit(4801), { verdict: 'return', note: 'No', evidenceId: ev(61) })).toBeNull();
  });
  it('a verdict the read does not list, or a null packet, holds the press', () => {
    expect(decisionHeld(exit(4804), { verdict: 'approve', note: '', evidenceId: null })).toMatch(/no decision/);
    expect(decisionHeld(exit(4803), { verdict: 'approve', note: '', evidenceId: null })).toBe(NOT_YET);
    expect(decisionHeld({ ...exit(4801), expected_revision: null as never }, { verdict: 'approve', note: '', evidenceId: null })).toBe(NOT_YET);
  });
  it('sends evidence_id only when chosen and listed, issue_id only for a return and a listed blocker, note only when written', () => {
    const e = exit(4801);
    expect(decideInputs(e, { verdict: 'approve', note: '', evidenceId: null, issueId: null })).toEqual({ verdict: 'approve' });
    expect(decideInputs(e, { verdict: 'approve', note: 'ok', evidenceId: ev(61), issueId: 301 })).toEqual({ verdict: 'approve', note: 'ok', evidence_id: 61 });
    expect(decideInputs(e, { verdict: 'return', note: 'no', evidenceId: ev(61), issueId: 301 })).toEqual({ verdict: 'return', note: 'no', evidence_id: 61, issue_id: 301 });
    // an id the read does not list is never sent
    expect(decideInputs(e, { verdict: 'return', note: 'no', evidenceId: ev(999), issueId: 999 })).toEqual({ verdict: 'return', note: 'no' });
  });
  it('an upload id cannot be passed as an evidence id', () => {
    const upload = 12 as UploadId;
    // @ts-expect-error an UploadId is not an EvidenceId
    decideInputs(exit(4801), { verdict: 'approve', note: '', evidenceId: upload, issueId: null });
  });
});

describe('the commands (AC10, AC17, AC19, AC28)', () => {
  const commands = (id: number, revision: number | null = 6) => releaseCommands(readback(id), { workId: id, revision });
  const by = (list: ReturnType<typeof commands>, id: string) => list.find((c) => c.id === id)!;
  it('describes the three writes', () => expect(commands(4801).map((c) => c.id)).toEqual(['release.decide', 'release.prepare_readiness', 'release.observe']));
  it('the decision body has the read\'s tokens and packet and no action', () => {
    const e = readback(4801).exit;
    const body = by(commands(4801), 'release.decide').body({ verdict: 'approve' });
    expect(body).toEqual({ verdict: 'approve', packet: e.packet, expected_revision: 6, case_revision: 41 });
    expect(by(commands(4801), 'release.decide').disabledReason).toBeUndefined();
  });
  it('inputs cannot override the packet or the tokens', () => {
    const body = by(commands(4801), 'release.decide').body({ verdict: 'approve', packet: 'x', expected_revision: 99, case_revision: 98, action: 'evil' });
    expect(body).toMatchObject({ packet: 'a'.repeat(64), expected_revision: 6, case_revision: 41 });
  });
  it('a null packet or token disables the decision with its reason and is never sent as 0', () => {
    expect(by(commands(4803), 'release.decide').disabledReason).toBe(NOT_YET);
    const rb = readback(4801);
    const nullTokens = releaseCommands({ ...rb, exit: { ...rb.exit, expected_revision: null as never, packet: null } }, { workId: 4801, revision: 6 });
    const c = by(nullTokens, 'release.decide');
    expect(c.disabledReason).toBeTruthy();
    expect(c.body({ verdict: 'approve' })).toMatchObject({ expected_revision: null, packet: null });
    expect(JSON.stringify(c.body({}))).not.toMatch(/:0[,}]/);
    expect(by(commands(4801, null), 'release.decide').disabledReason).toMatch(/current version/);
  });
  it('no verdicts: the decision is disabled with the read\'s reason', () => expect(by(commands(4804), 'release.decide').disabledReason).toMatch(/no decision/));
  it('prepare_readiness is open only when the read lists it', () => {
    expect(by(commands(4808), 'release.prepare_readiness').disabledReason).toBeUndefined();
    expect(by(commands(4808), 'release.prepare_readiness').body({})).toEqual({ action: 'prepare_readiness', expected_revision: 6, case_revision: 41 });
    expect(by(commands(4809), 'release.prepare_readiness').disabledReason).toMatch(/isn’t open/);
  });
  it('observe_release is open only when listed and sends checked true, never evidence_id', () => {
    const c = by(commands(4810), 'release.observe');
    expect(c.disabledReason).toBeUndefined();
    const r = readback(4810).register;
    const body = c.body(observeInputs(r, { releasedAt: '2026-11-26T10:00:00.000Z', reference: ' REL-1 ', environment: '  ', note: 'Done', readinessId: null, uploadId: 8001 as UploadId }));
    expect(body).toEqual({ action: 'observe_release', expected_revision: 6, case_revision: 41, readiness_id: 71, released_at: '2026-11-26T10:00:00.000Z', reference: 'REL-1', upload_id: 8001, note: 'Done', environment: null, private_log_id: null, checked: true });
    expect(body).not.toHaveProperty('evidence_id');
    expect(by(commands(4801), 'release.observe').disabledReason).toMatch(/isn’t open/);
  });
  it('readiness_id: the only one is sent; several need a listed choice; none is null', () => {
    const base = { releasedAt: 'x', reference: 'r', environment: '', note: 'n', uploadId: 1 as UploadId };
    const reg = (ids: number[]) => ({ ...readback(4810).register, readiness_ids: ids }) as Register;
    expect(observeInputs(reg([71]), { ...base, readinessId: 99 }).readiness_id).toBe(71);
    expect(observeInputs(reg([71, 72]), { ...base, readinessId: null }).readiness_id).toBeNull();
    expect(observeInputs(reg([71, 72]), { ...base, readinessId: 72 }).readiness_id).toBe(72);
    expect(observeInputs(reg([71, 72]), { ...base, readinessId: 99 }).readiness_id).toBeNull();
    expect(observeInputs(reg([]), { ...base, readinessId: null }).readiness_id).toBeNull();
  });
});
