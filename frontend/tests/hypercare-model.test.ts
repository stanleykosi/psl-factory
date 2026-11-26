// F-115: the hypercare model: page state, the criterion words, every section, and the open issues read. Pure functions over the mock's reads.
import { describe, expect, it, vi } from 'vitest';

import { criterionLabel, ruleText, type Criteria } from '@/features/hypercare/hypercareLabels';
import { blocksHypercare, eventsSections, hypercareState, issuesSection, MAX_ISSUES, nextSection, readOpenIssues, stabilitySections, type IssuesPage, type RegisterIssue, type Stability, type StabilityEvents } from '@/features/hypercare/hypercareModel';

// @ts-expect-error plain ESM module without type declarations
import { hypercareLive } from '../mock/hypercare-live.mjs';

const get = (path: string) => hypercareLive({ method: 'get', url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead' })[1];
const stab = (id: number) => get(`/api/v1/work/${id}/stability`) as Stability;
const evts = (id: number) => get(`/api/v1/work/${id}/stability/events`) as StabilityEvents;
const flat = (sections: ReturnType<typeof stabilitySections>) => JSON.stringify(sections);
const find = (sections: ReturnType<typeof stabilitySections>, key: string) => sections.find((s) => s.key === key);

describe('the state (AC6)', () => {
  const state = (criteria: unknown, qualified: boolean | null) => hypercareState({ criteria, qualified } as never);
  it('derives from the four fixtures', () => {
    expect(hypercareState(stab(5201))).toBe('setup');
    expect(hypercareState(stab(5202))).toBe('evaluating');
    expect(hypercareState(stab(5203))).toBe('qualified');
    expect(hypercareState(stab(5204))).toBe('not_met');
  });
  it('follows the stated order on the edge combinations', () => {
    expect(state({}, true)).toBe('qualified');
    expect(state({}, false)).toBe('not_met');
    expect(state({}, null)).toBe('evaluating');
    for (const q of [true, false, null]) expect(state(null, q)).toBe('setup');
  });
});

describe('the criterion words (AC5)', () => {
  const criteria = stab(5204).criteria as unknown as Criteria;
  it('maps each key', () => {
    expect(criterionLabel('confirmation', 'Engineering', criteria)).toEqual({ label: 'Engineering confirms stability' });
    expect(criterionLabel('elapsed_hours', 'Infrastructure', criteria)).toEqual({ label: 'Infrastructure observed after 720 hours' });
    expect(criterionLabel('metric:error_rate', 'Engineering', criteria)).toEqual({ label: 'Engineering · error_rate', detail: 'at most 2 percent' });
    expect(criterionLabel('metric:uptime', 'Infrastructure', criteria)).toEqual({ label: 'Infrastructure · uptime', detail: 'at least 99.5 percent' });
    expect(criterionLabel('issue_clearance', null, criteria)).toEqual({ label: 'No blocking issues', detail: 'Blocking: Critical, High severity, Open, In Progress' });
  });
  it('words the three operators and keeps an unknown one as given', () => {
    expect(ruleText({ operator: 'eq', threshold: 0, unit: 'errors' })).toBe('exactly 0 errors');
    expect(ruleText({ operator: 'lte', threshold: 1, unit: 'ms' })).toBe('at most 1 ms');
    expect(ruleText({ operator: 'gt', threshold: 1, unit: 'ms' })).toBe('gt 1 ms');
  });
  it('shows an unrecognised key as its raw text, and a rule it cannot match without one', () => {
    expect(criterionLabel('something_new', 'Engineering', criteria)).toEqual({ label: 'something_new' });
    expect(criterionLabel('metric:gone', 'Engineering', criteria)).toEqual({ label: 'Engineering · gone' });
    expect(criterionLabel('issue_clearance', null, null)).toEqual({ label: 'No blocking issues' });
  });
});

describe('what each state draws (AC1 to AC4, AC7, AC8)', () => {
  it('Setup needed: the tag, the not-set line, the held check, no window and no criteria rows', () => {
    const s = stabilitySections(stab(5201));
    const text = flat(s);
    expect(text).toContain('Setup needed');
    expect(text).toContain('Hypercare criteria are not set.');
    expect(text).toContain('An admin can draft them in Setup');
    expect(find(s, 'checks')).toBeDefined();
    expect(text).toContain('"label":"Stability"');
    expect(find(s, 'criteria')).toBeUndefined();
    expect(find(s, 'readings')).toBeUndefined();
    expect(text).not.toContain('Window ends');
    expect(text).not.toContain('hours from the release');
  });
  it('Setup needed when the viewer cannot draft criteria: says an admin sets them', () => {
    const s = stabilitySections({ ...stab(5201), can_draft_criteria: false });
    expect(flat(s)).toContain('An admin sets the criteria in Setup.');
    expect(flat(s)).not.toContain('can draft');
  });
  it('Evaluating: unknown results read Not known, one reading, the other owner has no reading yet', () => {
    const s = stabilitySections(stab(5202));
    const criteria = find(s, 'criteria')!;
    const tags = criteria.items.map((i) => i.tag?.label);
    expect(tags).toContain('Not known');
    expect(tags).toContain('Met');
    expect(tags).not.toContain('Not met');
    expect(flat(s)).toContain('Tola is evaluating hypercare.');
    const rows = find(s, 'readings')!.items.map((i) => i.cells!.map((c) => c.text));
    expect(rows).toEqual([['Engineering', 'Recorded', '1 of 1 met'], ['Infrastructure', 'No reading yet', '0 of 1 met']]);
  });
  it('Qualified: every criterion Met, and Verified', () => {
    const s = stabilitySections(stab(5203));
    expect(find(s, 'criteria')!.items.every((i) => i.tag?.label === 'Met')).toBe(true);
    expect(flat(s)).toContain('Hypercare qualified.');
    expect(find(s, 'result')!.items.map((i) => i.text)).toEqual(['Hypercare qualified.', 'Verified']);
    expect(nextSection(stab(5203))).toBeNull();
  });
  it('Qualified but not verified says so', () => {
    expect(flat(stabilitySections({ ...stab(5203), verified: false }))).toContain('Qualified, not yet verified');
  });
  it('Not met: the findings in order, the unmet and unknown criteria, and the next lines', () => {
    const s = stabilitySections(stab(5204));
    const result = find(s, 'result')!.items.map((i) => i.text);
    expect(result).toEqual(['Engineering/error_rate fails the configured criterion', 'Infrastructure has not confirmed stability']);
    const byLabel = Object.fromEntries(find(s, 'criteria')!.items.map((i) => [i.label + (i.detail ? ` ${i.detail}` : ''), i.tag?.label]));
    expect(byLabel['Engineering · error_rate at most 2 percent']).toBe('Not met');
    expect(byLabel['Infrastructure confirms stability']).toBe('Not known');
    expect(nextSection(stab(5204))!.items.map((i) => i.text)).toEqual(['Fix the findings above. Tola evaluates again when they are resolved.', 'Closure stays blocked until then.']);
  });
  it('the closure line is left off when no stability or acceptance check is held', () => {
    const s = { ...stab(5204), checks: [{ name: 'release', status: 'held', finding: 'x' }, { name: 'stability', status: 'ready', finding: null }] } as Stability;
    expect(nextSection(s)!.items.map((i) => i.text)).toEqual(['Fix the findings above. Tola evaluates again when they are resolved.']);
  });
  it('a missing due_at says hours from the release, never a day count; a null finding draws no line', () => {
    const s = stabilitySections({ ...stab(5202), due_at: null });
    expect(flat(s)).toContain('720 hours from the release');
    expect(flat(s)).not.toMatch(/Day \d|of 30|Window ends/);
    const checks = find(stabilitySections(stab(5203)), 'checks')!;
    expect(checks.items.every((i) => i.detail === undefined)).toBe(true);
  });
  it('with criteria set and no results yet, the criteria rows carry no result tag', () => {
    const s = stabilitySections({ ...stab(5202), criterion_results: [] });
    const rows = find(s, 'criteria')!.items;
    expect(rows.length).toBe(7);
    expect(rows.every((i) => i.tag === undefined)).toBe(true);
  });
  it('a result it does not know is shown as given, never as Met', () => {
    const s = stabilitySections({ ...stab(5202), criterion_results: [{ owner: 'Engineering', key: 'confirmation', status: 'mystery' as never }] });
    expect(find(s, 'criteria')!.items[0].tag).toEqual({ label: 'mystery', tone: 'uncertain' });
  });
  it('draws no actual reading value, no heading for an empty section and none of the hidden words', () => {
    for (const id of [5201, 5202, 5203, 5204]) {
      const s = stabilitySections(stab(id));
      for (const section of s) expect(section.items.length, `${id} ${section.key}`).toBeGreaterThan(0);
      expect(flat(s)).not.toMatch(/Day \d|Log an|Record release|Ask Tola|ISS-|OBS-/);
    }
  });
});

describe('release and acceptance (AC9)', () => {
  const facts = (e: StabilityEvents) => Object.fromEntries(eventsSections(e)[0].items.map((i) => [i.label, i.value]));
  it('counts what the read lists', () => {
    expect(facts(evts(5203))).toEqual({ 'Release evidence': '1 recorded', 'Go-live signatures': '2 recorded', 'Acceptance packet': `${'c'.repeat(12)}…`, Receipts: expect.stringMatching(/^1 receipt, latest /) });
  });
  it('zero release evidence is None recorded and a null packet is Not recorded; the line is never hidden', () => {
    const f = facts(evts(5201));
    expect(f['Release evidence']).toBe('None recorded');
    expect(f['Acceptance packet']).toBe('Not recorded');
    expect(f.Receipts).toBe('None recorded');
  });
  it('can_record_release with no evidence adds one line and no button', () => {
    const s = eventsSections(evts(5201));
    expect(s.map((x) => x.key)).toEqual(['events', 'events-note']);
    expect(JSON.stringify(s)).toContain('The release has not been recorded.');
    expect(eventsSections({ ...evts(5201), can_record_release: false }).map((x) => x.key)).toEqual(['events']);
  });
});

const issue = (id: number, status: string, severity: string | null = 'High', owner = 4): RegisterIssue => ({ id, state_id: id, reference: `ISS-${id}`, title: `Issue ${id}`, kind: 'defect', status, severity, owner_id: owner, next_action: '', opened_at: null, age_days: 6, acknowledged_at: null, resolved_at: null }) as RegisterIssue;
const page = (issues: RegisterIssue[], next: number | null): IssuesPage => ({ case_revision: 1, issues, next_before: next, owners: [{ id: 4, name: 'Tunde Bello' }], proofs: [] });

describe('open issues (AC4, AC10)', () => {
  const criteria = stab(5204).criteria as unknown as Criteria;
  it('lists open rows apart from the readings, tags the blocking one, and an owner it cannot find reads No owner', () => {
    const section = issuesSection({ issues: [issue(1, 'Open', 'High'), issue(2, 'In Progress', 'Low', 99)], owners: [{ id: 4, name: 'Tunde Bello' }] }, criteria);
    expect(section.title).toBe('Open issues');
    const [a, b] = section.items.map((i) => i.cells!);
    expect(a.find((c) => c.column === 'blocks')?.tag?.label).toBe('Blocks hypercare');
    expect(a.find((c) => c.column === 'owner')?.text).toBe('Tunde Bello');
    expect(b.find((c) => c.column === 'blocks')).toBeUndefined();
    expect(b.find((c) => c.column === 'owner')?.text).toBe('No owner');
    expect(b.find((c) => c.column === 'age')?.text).toBe('6 days open');
  });
  it('nothing open says so', () => expect(JSON.stringify(issuesSection({ issues: [], owners: [] }, criteria))).toContain('No open issues.'));
  it('blocking needs both the status and the severity, and a null severity never blocks', () => {
    expect(blocksHypercare({ status: 'Open', severity: 'High' }, criteria)).toBe(true);
    expect(blocksHypercare({ status: 'Open', severity: 'Low' }, criteria)).toBe(false);
    expect(blocksHypercare({ status: 'Resolved', severity: 'High' }, criteria)).toBe(false);
    expect(blocksHypercare({ status: 'Open', severity: null }, criteria)).toBe(false);
    expect(blocksHypercare({ status: 'Open', severity: 'High' }, { ...criteria, issue_clearance: undefined })).toBe(false);
  });
  it('follows next_before across two pages and drops Resolved and Closed rows', async () => {
    const reads = vi.fn(async (before: number | null) => (before === null ? page([issue(5, 'Open'), issue(4, 'Resolved')], 4) : page([issue(3, 'Closed'), issue(2, 'In Progress')], null)));
    const open = await readOpenIssues(reads);
    expect(reads.mock.calls.map((c) => c[0])).toEqual([null, 4]);
    expect(open.issues.map((i) => i.id)).toEqual([5, 2]);
  });
  it('stops at 100 rows read', async () => {
    let n = 1000;
    const reads = vi.fn(async () => page(Array.from({ length: 40 }, () => issue(n--, 'Open')), n));
    const open = await readOpenIssues(reads);
    expect(reads).toHaveBeenCalledTimes(3);
    expect(open.issues.length).toBe(120);
    expect(MAX_ISSUES).toBe(100);
  });
  it('a failed page fails the read (the block shows its own retry)', async () => {
    await expect(readOpenIssues(async (before) => (before === null ? page([issue(1, 'Open')], 1) : Promise.reject(new Error('503'))))).rejects.toThrow('503');
  });
});
