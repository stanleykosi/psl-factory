import { describe, expect, it } from 'vitest';

import { actionBody, actionProblems, carriedDecisions, defaultActionReference, defaultReference, deadlineText, meetingIdFromUrl, occurredIso, ownerText, positiveInt, saveBody, saveProblems, STATUS_WORDS, stripChecks, type MeetingAction, type SaveDraft } from '@/features/retrospective/model';

const NOW = new Date('2026-11-23T12:00:00Z');
const draft = (over: Partial<SaveDraft> = {}): SaveDraft => ({
  reference: 'Retrospective 2026-11-23',
  occurredAt: '2026-11-23T10:00',
  whole: null,
  boxes: { well: 'UAT finished on time.', didnt: '', lessons: '' },
  other: '',
  participantIds: [12, 15],
  decisions: [],
  evidenceId: '87',
  meetingId: null,
  ...over,
});

describe('saveBody', () => {
  it('builds the first save', () => {
    const body = saveBody(draft(), 41);
    expect(body).toMatchObject({ revision: 41, reference: 'Retrospective 2026-11-23', kind: 'retrospective', purpose: 'Project retrospective', summary: '## What went well\nUAT finished on time.', participant_ids: [12, 15], decisions: [], evidence_id: 87, meeting_id: null });
    expect(body.occurred_at).toBe(new Date('2026-11-23T10:00').toISOString());
  });
  it('appends a version with the meeting id', () => {
    expect(saveBody(draft({ meetingId: 301 }), 42).meeting_id).toBe(301);
  });
  it('sends a summary with no headings back unchanged', () => {
    expect(saveBody(draft({ whole: 'Plain notes.\n\nTwo.' }), 1).summary).toBe('Plain notes.\n\nTwo.');
  });
  it('carries previous decisions unchanged, including change_evidence_id', () => {
    const decisions = carriedDecisions([{ text: 'Ask early.', evidence_id: 88, change_evidence_id: 90 }, { text: 'Plain.', evidence_id: 88 }]);
    expect(saveBody(draft({ decisions }), 1).decisions).toEqual([{ text: 'Ask early.', evidence_id: 88, change_evidence_id: 90 }, { text: 'Plain.', evidence_id: 88 }]);
  });
});

describe('saveProblems', () => {
  it('accepts a complete draft', () => {
    expect(saveProblems(draft(), 2, NOW).any).toBe(false);
  });
  it('needs a box with text', () => {
    expect(saveProblems(draft({ boxes: { well: '  ', didnt: '', lessons: '' } }), 2, NOW).boxes).toBeTruthy();
  });
  it('needs a notes file, and says so when the project has none', () => {
    expect(saveProblems(draft({ evidenceId: '' }), 2, NOW).evidence).toBe('Choose the notes file.');
    expect(saveProblems(draft({ evidenceId: '' }), 0, NOW).evidence).toContain('No supporting file is recorded');
  });
  it('stops a joined summary over 16000 characters', () => {
    expect(saveProblems(draft({ boxes: { well: 'x'.repeat(16000), didnt: '', lessons: '' } }), 2, NOW).boxes).toContain('over');
    expect(saveProblems(draft({ whole: 'x'.repeat(16001) }), 2, NOW).boxes).toBeTruthy();
    expect(saveProblems(draft({ whole: 'x'.repeat(16000) }), 2, NOW).any).toBe(false);
  });
  it('refuses a heading line in a box', () => {
    expect(saveProblems(draft({ boxes: { well: 'a\n## What went well', didnt: '', lessons: '' } }), 2, NOW).boxLines.well).toBe('That line is a section heading. Reword it.');
  });
  it('refuses a time in the future and a missing time', () => {
    expect(saveProblems(draft({ occurredAt: '2099-01-01T10:00' }), 2, NOW).occurredAt).toBeTruthy();
    expect(saveProblems(draft({ occurredAt: '' }), 2, NOW).occurredAt).toBeTruthy();
  });
  it('needs text and a file on every decision', () => {
    const rows = [{ key: 0, text: '', evidenceId: '88', changeEvidenceId: null }, { key: 1, text: 'ok', evidenceId: '', changeEvidenceId: null }];
    const out = saveProblems(draft({ decisions: rows }), 2, NOW);
    expect(out.decisions[0]).toBeTruthy();
    expect(out.decisions[1]).toBeTruthy();
  });
});

describe('actionBody', () => {
  const base = { description: 'Ask early', ownerId: '', dueAt: '', reason: 'Lesson', evidenceId: '88', reference: ' Retro action 1 ' };
  it('sends null owner and null deadline when empty, with the meeting id and no link call fields', () => {
    expect(actionBody(base, 41, 301)).toEqual({ revision: 41, reference: 'Retro action 1', description: 'Ask early', owner_id: null, due_at: null, evidence_id: 88, reason: 'Lesson', meeting_id: 301 });
  });
  it('sends a chosen owner and deadline', () => {
    const body = actionBody({ ...base, ownerId: '12', dueAt: '2026-12-01T09:00' }, 41, 301);
    expect(body.owner_id).toBe(12);
    expect(body.due_at).toBe(new Date('2026-12-01T09:00').toISOString());
  });
  it('flags a taken reference and missing parts', () => {
    expect(actionProblems(base, ['Retro action 1'])).toEqual({ reference: 'Action reference already exists.' });
    expect(Object.keys(actionProblems({ ...base, description: '', reason: '', evidenceId: '' }, []))).toEqual(['description', 'reason', 'evidenceId']);
  });
});

describe('null handling and words', () => {
  const action = (owner: { id: number; label: string } | null, deadline: string | null) => ({ current: { owner, deadline } }) as MeetingAction;
  it('reads no owner and no deadline in words', () => {
    expect(ownerText(action(null, null))).toBe('No owner');
    expect(deadlineText(action(null, null), String)).toBe('No deadline set');
    expect(ownerText(action({ id: 12, label: 'Tunde Bello' }, null))).toBe('Tunde Bello');
  });
  it('names every checklist status', () => {
    expect(STATUS_WORDS).toEqual({ current: 'Current', recorded: 'Recorded', closed: 'Closed', held: 'Not yet', unknown: 'Unknown', unavailable: 'Unavailable' });
  });
  it('keeps the six strip checks in the order returned and drops context and report', () => {
    const checks = ['context', 'go_live', 'report', 'retrospective', 'finance'].map((key) => ({ key, title: key, status: 'closed', summary: '', references: [], finding: null })) as Parameters<typeof stripChecks>[0];
    expect(stripChecks(checks).map((c) => c.key)).toEqual(['go_live', 'retrospective', 'finance']);
  });
  it('reads the meeting id out of the checklist url', () => {
    expect(meetingIdFromUrl('/api/v1/projects/x/meetings/301?version_id=9001')).toBe(301);
    expect(meetingIdFromUrl(null)).toBeNull();
  });
  it('reads only plain positive integers from the query', () => {
    expect(positiveInt('301')).toBe(301);
    for (const bad of ['0', '-1', '1.5', '1e3', 'abc', '', null, undefined, '12 ']) expect(positiveInt(bad)).toBeNull();
  });
  it('builds references and times', () => {
    expect(defaultReference(new Date(2026, 10, 23))).toBe('Retrospective 2026-11-23');
    expect(defaultActionReference(1)).toBe('Retro action 2');
    expect(occurredIso('nope')).toBeNull();
  });
});
