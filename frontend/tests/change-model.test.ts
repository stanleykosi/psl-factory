// F-112: the change model's rules without a page: the stage track, the status tag, what is drawn, the exact write bodies and what is refused
// before any request.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  assessHeld, assessInputs, authorizeInputs, authorizeOffered, changeCommands, changeSections, choiceValue, decideHeld, decideInputs, emptyOutputs, impactRows, isApproved, isRejected, scopeItems, statusTag, stepOf, stepStates, TEXT,
  type AssessChoice, type Change,
} from '@/features/change-request/changeModel';
import { bodyOf, EMPTY_DRAFT, isCaptured, isRegisterRead, problemsOf } from '@/features/change-request/logChange';

import { start } from './change-fixture';

const rb = (id: number, patch: Partial<Change> = {}) => ({ change: { ...start(id), ...patch }, register: null });
const ctx = { workId: 4901, revision: 6 };
const choice = (patch: Partial<AssessChoice> = {}): AssessChoice => ({ team: 'Security', note: ' Uses the existing provider. ', effort: ' 0.5 ', cost: 'no', timeline: 'unknown', clientFacing: 'yes', production: 'no', scope: '', outputs: emptyOutputs(), evidence: '7901', ...patch });

describe('the stage track (D-6)', () => {
  it('source, impact and authorization light step 1; notice, execution, go_live and signatures light 2 to 5; complete finishes step 5', () => {
    expect(['source', 'impact', 'authorization'].map(stepOf)).toEqual([0, 0, 0]);
    expect(['notice', 'execution', 'go_live', 'signatures', 'complete'].map(stepOf)).toEqual([1, 2, 3, 4, 4]);
    expect(stepStates('notice')).toEqual(['done', 'now', 'next', 'next', 'next']);
    expect(stepStates('signatures')).toEqual(['done', 'done', 'done', 'done', 'now']);
    expect(stepStates('complete')).toEqual(['done', 'done', 'done', 'done', 'done']);
  });
  it('a stage outside the eight codes lights no step, whatever its spelling', () => {
    for (const stage of ['review_pending', '', 'Impact', 'IMPACT', ' impact', 'constructor', '__proto__', 'toString', 'hasOwnProperty']) {
      expect(stepOf(stage)).toBeNull();
      expect(stepStates(stage)).toBeNull();
    }
  });
});

describe('the status tag', () => {
  it('is derived from the stage, the counts and the deciders', () => {
    expect(statusTag(start(4901))?.label).toBe('Being assessed · 3 of 4');
    expect(statusTag(start(4912))?.label).toBe('Being assessed · 0 of 4');
    expect(statusTag(start(4902))?.label).toBe('Deciding · 2 of 5');
    expect(statusTag(start(4903))?.label).toBe('Rejected');
    expect(statusTag(start(4904))?.label).toBe('Approved · to authorise');
    expect(statusTag(start(4906))?.label).toBe('Authorised');
  });
  it('"approved" is read from the decider’s own words: "Not approved" and "Awaiting approval" are not approvals', () => {
    expect(isApproved({ status: 'Approved' })).toBe(true);
    expect(isApproved({ status: ' approved 12 Nov' })).toBe(true);
    for (const status of ['Not approved', 'Awaiting approval', 'Waiting', 'Returned', 'Rejected', '']) expect(isApproved({ status })).toBe(false);
    expect(isRejected({ status: 'Rejected' })).toBe(true);
    expect(isRejected({ status: 'Not rejected' })).toBe(false);
  });
  it('"to authorise" needs can_authorize, no authorisation yet, and every served decider approved; an empty list is not approval', () => {
    const c = start(4904);
    expect(statusTag({ ...c, can_authorize: false })?.label).not.toBe('Approved · to authorise');
    expect(statusTag({ ...c, decisions: [] })?.label).not.toBe('Approved · to authorise');
    expect(statusTag({ ...c, decisions: [...c.decisions.slice(1), { role: 'Client', status: 'Not approved', verdicts: [] }] })?.label).not.toBe('Approved · to authorise');
  });
});

describe('what is drawn', () => {
  const text = (id: number) => JSON.stringify(changeSections(rb(id)));
  it('the impact table always has the four teams in order; a team the read leaves out is a missing row, an unrecorded effort is "Not recorded"', () => {
    expect(impactRows(start(4912)).map((r) => r.team)).toEqual(['Engineering', 'QA', 'Infra', 'Security']);
    const section = changeSections(rb(4901)).find((s) => s.key === 'impact')!;
    const cells = (team: string) => section.items.find((i) => i.id === team)!.cells!;
    expect(cells('Infra').find((x) => x.column === 'effort')?.text).toBe('Not recorded');
    expect(cells('Security').find((x) => x.column === 'assessment')?.text).toBe('Not given yet');
    expect(cells('Engineering').find((x) => x.column === 'effort')?.text).toBe('4');
    expect(JSON.stringify(section)).not.toMatch(/"text":"0/);
  });
  it('the deciders table has exactly the served rows', () => {
    const rows = (id: number) => changeSections(rb(id)).find((s) => s.key === 'deciders')?.items.map((i) => i.id) ?? [];
    expect(rows(4902)).toHaveLength(5);
    expect(rows(4911)).toEqual(['Product', 'Engineering']);
    expect(rows(4910)).toEqual([]);
  });
  it('the reference and module come only from the list row for this version; none matching leaves them out', () => {
    const register = { case_revision: 1, evidence: [], catalogue: [], catalogue_finding: '', records: [{ id: 1, version_id: 1, reference: 'CR-0031', category: 'Normal' as const, module: 'Appointments', description: 'd' }] };
    const keys = (r: typeof register | null, id = 4901) => changeSections({ change: start(id), register: r }).find((s) => s.key === 'summary')!.items.map((i) => i.id);
    expect(keys(register)).toContain('reference');
    expect(keys(register)).toContain('module');
    expect(keys(register, 4902)).not.toContain('reference');
    expect(keys(null)).toEqual(['category', 'status']);
  });
  it('never says deployment is authorised, names no agent or person, and the finding shows only when it has words', () => {
    for (const id of [4901, 4902, 4903, 4904, 4906]) expect(text(id)).not.toMatch(/deployment|Tola|Recorded by|Authorised by/i);
    expect(changeSections(rb(4901)).find((s) => s.key === 'next')!.items.map((i) => i.id)).toEqual(['next']);
    expect(changeSections(rb(4903)).find((s) => s.key === 'next')!.items.map((i) => i.id)).toEqual(['next', 'finding', 'later']);
    expect(changeSections(rb(4903)).find((s) => s.key === 'next')!.items.find((i) => i.id === 'later')?.text).toBe(TEXT.newChange);
  });
});

describe('the assess body', () => {
  it('has every contract key; unknown is null, never false; the effort is the typed string trimmed; no upload', () => {
    expect(assessInputs(choice())).toEqual({
      contributor: 'Security',
      cost_impact: false,
      timeline_impact: null,
      client_facing: true,
      production_impact: false,
      scope_items: null,
      outputs: null,
      effort_person_days: '0.5',
      evidence: 7901,
      note: 'Uses the existing provider.',
      proof_upload: null,
    });
    expect([choiceValue('yes'), choiceValue('no'), choiceValue('unknown'), choiceValue(undefined)]).toEqual([true, false, null, null]);
    expect(assessInputs(choice({ effort: '   ' })).effort_person_days).toBeNull();
  });
  it('scope items drop blank lines; the output notes are an object only when one is written, the blanks null', () => {
    expect(scopeItems('a\n\n  b  \n')).toEqual(['a', 'b']);
    expect(scopeItems(' \n ')).toBeNull();
    expect(assessInputs(choice({ outputs: { ...emptyOutputs(), cost_resource: ' Two extra days ' } })).outputs).toEqual({ discipline: null, timeline: null, cost_resource: 'Two extra days', risk: null, dependency: null });
  });
  it('is held until the read’s team, a note, every answer and a listed proof are there', () => {
    const c = start(4901);
    expect(assessHeld(c, choice())).toBeNull();
    expect(assessHeld(c, choice({ team: 'QA' }))).toMatch(/isn’t open to you/);
    expect(assessHeld(c, choice({ note: '  ' }))).toBe('Add the assessment note.');
    expect(assessHeld(c, choice({ note: 'x'.repeat(4001) }))).toMatch(/4000/);
    expect(assessHeld(c, choice({ effort: 'x'.repeat(33) }))).toMatch(/32/);
    expect(assessHeld(c, choice({ cost: undefined }))).toMatch(/Answer each question/);
    expect(assessHeld(c, choice({ scope: 'x'.repeat(241) }))).toMatch(/240/);
    expect(assessHeld(c, choice({ evidence: undefined }))).toBe('Choose the proof for this assessment.');
    expect(assessHeld(c, choice({ evidence: '1' }))).toBe('Choose the proof for this assessment.');
    expect(assessHeld({ ...c, evidence: [] }, choice())).toBe(TEXT.noProof);
  });
});

describe('the decide and authorize bodies', () => {
  it('decide sends the role, the verdict, the chosen proof and the trimmed note', () => {
    expect(decideInputs({ role: 'Client', verdict: 'return', note: ' n ', evidence: '7902' })).toEqual({ role: 'Client', verdict: 'return', evidence: 7902, note: 'n' });
  });
  it('decide is held without a note, a listed proof and a verdict the row lists; an empty verdicts list holds every verdict', () => {
    const c = start(4902);
    expect(decideHeld(c, { role: 'Client', verdict: 'reject', note: '', evidence: '7902' })).toBe('Add a note for this decision.');
    expect(decideHeld(c, { role: 'Client', verdict: 'reject', note: 'n', evidence: undefined })).toBe('Choose the proof for this decision.');
    for (const verdict of ['approve', 'return', 'reject'] as const) expect(decideHeld(c, { role: 'Product', verdict, note: 'n', evidence: '7902' })).toMatch(/isn’t open to you/);
    expect(decideHeld(c, { role: 'Security Manager' as const, verdict: 'approve', note: 'n', evidence: '7902' })).toMatch(/isn’t open to you/);
  });
  it('authorize is offered only for can_authorize with no authorisation; the commercial item is a listed one or null', () => {
    const c = start(4904);
    expect(authorizeOffered(c)).toBe(true);
    expect(authorizeInputs(c, undefined)).toEqual({ commercial: null });
    expect(authorizeInputs(c, '12')).toEqual({ commercial: 12 });
    expect(authorizeInputs(c, '1e1')).toEqual({ commercial: null });
  });
});

describe('the descriptors', () => {
  it('only assess, decide and authorize exist, with no key field; the descriptor’s own action, revisions and version win over the inputs', () => {
    const cmds = changeCommands(rb(4902), { workId: 4902, revision: 6 });
    expect(cmds.map((c) => c.id)).toEqual(['change.assess', 'change.decide', 'change.authorize']);
    for (const c of cmds) expect(c.idempotency).toEqual({ field: null, value: null });
    const decide = cmds.find((c) => c.id === 'change.decide')!;
    expect(decide.url).toBe('/api/v1/work/4902/change');
    expect(decide.successStatuses).toEqual([201]);
    expect(decide.body({ ...decideInputs({ role: 'Client', verdict: 'approve', note: 'n', evidence: '7902' }), action: 'close', expected_revision: 1, case_revision: 1, change_version_id: 999 })).toEqual({
      action: 'decide', expected_revision: 6, case_revision: 41, change_version_id: 2, role: 'Client', verdict: 'approve', evidence: 7902, note: 'n',
    });
  });
  it('an unknown (null) revision disables every write with the words; a read with nothing open disables its own', () => {
    for (const c of changeCommands(rb(4901), { workId: 4901, revision: null })) expect(c.disabledReason).toBe(TEXT.noToken);
    const read = changeCommands(rb(4905), ctx);
    expect(read.map((c) => c.disabledReason)).toEqual(['No assessment is open to you.', 'No decision is open to you.', 'The authorisation isn’t open to you.']);
    expect(changeCommands(rb(4904), ctx).find((c) => c.id === 'change.authorize')!.disabledReason).toBeUndefined();
    const stale = rb(4904);
    stale.change.expected_revision = null as unknown as number;
    expect(changeCommands(stale, ctx).every((c) => c.disabledReason === TEXT.noToken)).toBe(true);
  });
  it('no request code for notice, execution, the go-live note, closure, retry, cancel or restart exists in the feature', () => {
    const dir = join(__dirname, '../src/features/change-request');
    const source = readdirSync(dir).map((f) => readFileSync(join(dir, f), 'utf8')).join('\n');
    expect(source).not.toMatch(/document_review|operate_delivery|['"]close['"]|['"]restart['"]|['"]execution['"]|change-milestone-link|change-versions/);
    expect(source).not.toMatch(/setTimeout|setInterval/);
  });
});

describe('log a change', () => {
  const data = { case_revision: 12, records: [], evidence: [{ id: 7901, version: 1, kind: 'security_assessment' }], catalogue: [], catalogue_finding: '' };
  const draft = { reference: ' CR-0099 ', category: 'Standard', module: ' Billing ', description: ' d ', reason: ' r ', evidence: '7901' };
  it('every field is required, the proof is a listed one and the category one of the two words', () => {
    expect(problemsOf(draft, data)).toEqual({});
    expect(Object.keys(problemsOf(EMPTY_DRAFT, data)).sort()).toEqual(['category', 'description', 'evidence', 'module', 'reason', 'reference']);
    expect(problemsOf({ ...draft, category: 'Emergency' }, data).category).toBeTruthy();
    expect(problemsOf({ ...draft, evidence: '1' }, data).evidence).toBeTruthy();
    expect(problemsOf({ ...draft, reference: 'x'.repeat(161) }, data).reference).toMatch(/160/);
    expect(problemsOf({ ...draft, reason: '   ' }, data).reason).toBeTruthy();
  });
  it('the capture body has exactly the contract keys with the read’s case revision', () => {
    expect(bodyOf(draft, 12)).toEqual({ action: 'capture', case_revision: 12, reference: 'CR-0099', category: 'Standard', module: 'Billing', description: 'd', reason: 'r', evidence_id: 7901 });
  });
  it('a response that is not the change list or the 201 shape is refused', () => {
    expect(isRegisterRead(data)).toBe(true);
    expect(isRegisterRead({ ...data, records: [{ id: 1 }] })).toBe(false);
    expect(isRegisterRead({ ...data, catalogue_finding: null })).toBe(false);
    expect(isCaptured({ id: 5, case_revision: 13 })).toBe(true);
    expect(isCaptured({ id: 0, case_revision: 13 })).toBe(false);
    expect(isCaptured({})).toBe(false);
  });
});
