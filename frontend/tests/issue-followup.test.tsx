// @vitest-environment jsdom
// F-111: the issue follow-up panel, read only: the mapper for the four states and the three reads through the adapter.
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/api/errors';
import { issueFollowupAdapter } from '@/features/issue-followup/issueFollowupAdapter';
import { ageText, allowedActions, errorText, sections, type Followup, type Readback } from '@/features/issue-followup/model';
import { adapterFor, type LineContext } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';

// @ts-expect-error plain ESM module without type declarations
import { issuesRoute, resetIssues } from '../mock/issues.mjs';

const CASE = '6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f';
const reads: string[] = [];
let overrideCase: string | null = null;

function stubFetch(scenario?: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url, 'http://m.local');
      reads.push(`${request.method} ${url.pathname}`);
      let reply = issuesRoute({ method: request.method.toLowerCase(), url, scenario, persona: 'finance_lead' });
      if (overrideCase && reply?.[0] === 200 && /^\/api\/v1\/work\/\d+$/.test(url.pathname)) reply = [200, { ...reply[1], case_id: overrideCase }];
      const [status, body] = reply ?? [404, { code: 'not_found', message: 'x' }];
      return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
    }),
  );
}

const read = (id: number) => issueFollowupAdapter.read({ key: 'issue-followup', url: `/api/v1/work/${id}/issue-followup` });
const ctx = (id: number): LineContext => ({ workId: id, caseId: CASE, revision: 3, caseRevision: 7 });
const draw = (list: Section[]) => render(<>{list.map((s) => <SectionView key={s.key} section={s} level={2} />)}</>);
const text = (list: Section[]) => JSON.stringify(list);

afterEach(() => {
  vi.unstubAllGlobals();
  reads.length = 0;
  overrideCase = null;
  resetIssues();
});

describe('the adapter (AC16, AC14, AC8)', () => {
  it('is registered under issue-followup and describes no command', async () => {
    stubFetch();
    expect(adapterFor('issue-followup')).toBe(issueFollowupAdapter);
    expect(issueFollowupAdapter.commands!(await read(5101), ctx(5101))).toEqual([]);
  });

  it('reads the follow-up, the work item, the detail and the messages, and only with GET', async () => {
    stubFetch();
    const r = await read(5101);
    expect(new Set(reads)).toEqual(
      new Set([
        'GET /api/v1/work/5101/issue-followup',
        'GET /api/v1/work/5101',
        `GET /api/v1/projects/${CASE}/issues/233`,
        `GET /api/v1/projects/${CASE}/issues/233/messages`,
      ]),
    );
    expect(r.followup.expected_revision).toBe(3);
    expect(r.followup.case_revision).toBe(7);
  });

  it('takes the case id from the work item, never from another body (AC14)', async () => {
    overrideCase = 'other-case';
    stubFetch();
    // the mock does not know that case for this issue: the read answers 404, which replaces the page
    await expect(read(5101)).rejects.toMatchObject({ status: 404 });
    expect(reads).toContain('GET /api/v1/projects/other-case/issues/233');
    expect(reads.some((p) => p.includes(CASE) && p.includes('/issues/'))).toBe(false);
  });

  it('a missing record replaces the page (AC12); a lost session does too (AC13)', async () => {
    stubFetch();
    await expect(read(5106)).rejects.toMatchObject({ status: 404 });
    stubFetch('401');
    await expect(read(5101)).rejects.toMatchObject({ kind: 'unauthenticated' });
  });
});

describe('the four states', () => {
  it('5101 in progress (AC1, AC2)', async () => {
    stubFetch();
    const list = sections(await read(5101), CASE);
    draw(list);
    for (const t of ['ISS-0233', 'High', 'In Progress', 'Engineering', '3 days', 'Go-live', 'What has happened', 'Chasing', 'Reminder due', 'Escalate by']) expect(screen.getAllByText(new RegExp(t)).length).toBeGreaterThan(0);
    const happened = list.find((s) => s.key === 'happened')!;
    expect(happened.items.map((i) => `${i.label}|${i.text}`)).toEqual(['Status changed|Open', 'Update requested|Sent', 'Owner acknowledged|Acknowledged', 'Status changed|In Progress']);
    expect(screen.getByRole('link', { name: 'Go-live' }).getAttribute('href')).toBe(`/projects/${CASE}`);
    expect(list.some((s) => s.note)).toBe(false);
  });

  it('5102 overdue shows the banner from the flags (AC3)', async () => {
    stubFetch();
    const r = await read(5102);
    draw(sections(r, CASE));
    expect(screen.getByText('No response since 09 Nov')).toBeTruthy();
    expect(screen.getByText('No receipt yet')).toBeTruthy();
    expect(screen.getByText('PMO lead')).toBeTruthy();
    const t = (r.messages as { timing: { reminder_overdue: boolean; escalation_overdue: boolean } }).timing;
    t.reminder_overdue = false;
    t.escalation_overdue = false;
    expect(sections(r, CASE).some((s) => s.key === 'overdue')).toBe(false);
  });

  it('an overdue flag with an empty finding reads the default sentence', async () => {
    stubFetch();
    const r = await read(5102);
    (r.messages as { timing: { finding: string } }).timing.finding = '';
    expect(sections(r, CASE).find((s) => s.key === 'overdue')!.note).toBe('The owner has not responded in time.');
  });

  it('5103 no owner: banner, no owner name, no zero, no severity, no timing (AC4, AC9)', async () => {
    stubFetch();
    const r = await read(5103);
    const list = sections(r, CASE);
    expect(list.find((s) => s.key === 'no-owner')!.note).toBe('This issue has no owner. Choose an owner for this issue.');
    const facts = list.find((s) => s.key === 'issue')!.items;
    expect(facts.map((i) => i.label)).toEqual(['Reference', 'Status', 'Raised', 'Age']);
    expect(facts.find((i) => i.label === 'Raised')!.value).toBe('Not recorded');
    expect(facts.find((i) => i.label === 'Age')!.value).toBe('Not recorded');
    expect(text(list)).not.toMatch(/0 days|Unassigned|Reminder due/);
    expect(list.find((s) => s.key === 'chasing')!.items[0].text).toBe('No message has been sent to the owner.');
    expect(allowedActions(r.followup)).toEqual({ requestUpdate: false, record: false, resolve: false, hasResponseTask: false });
    expect(allowedActions((await read(5101)).followup)).toMatchObject({ requestUpdate: true, record: true });
  });

  it('5104 verified: lead sentence, planned UAT is not a link, never "Closed" (AC5, AC6)', async () => {
    stubFetch();
    const list = sections(await read(5104), CASE);
    draw(list);
    expect(screen.getByText('The fix was confirmed by Engineering on 22 Nov.')).toBeTruthy();
    expect(screen.getByText('UAT (planned UAT)')).toBeTruthy();
    expect(screen.queryByRole('link', { name: /UAT/ })).toBeNull();
    expect(text(list)).not.toMatch(/Closed/);
    expect(list.some((s) => s.key === 'no-owner')).toBe(false);
  });

  it('both blocked milestones null leave the Blocks fact out (AC6)', async () => {
    stubFetch();
    const r = await read(5104);
    r.followup.blocked_planned_milestone = null;
    r.followup.blocked_milestone = null;
    expect(text(sections(r, CASE))).not.toMatch(/Blocks/);
  });

  it('banned v7 words never appear (AC7)', async () => {
    stubFetch();
    for (const id of [5101, 5102, 5103, 5104]) expect(text(sections(await read(id), CASE))).not.toMatch(/FIX IN TESTING|FOLLOW-UP VERIFIED|recorded by PM|not available/i);
  });
});

describe('separate section states (AC10, AC11)', () => {
  it('5105 messages 403: the rest shows, Chasing says it is not available to you', async () => {
    stubFetch();
    const list = sections(await read(5105), CASE);
    expect(list.find((s) => s.key === 'chasing')!.items[0].text).toBe('Chasing is not available to you');
    expect(list.find((s) => s.key === 'happened')!.kind).toBe('timeline');
    expect(list.some((s) => s.key === 'issue') && list.some((s) => s.key === 'next')).toBe(true);
  });

  it('5107 detail 503: facts and Next show, What has happened shows the mapped message', async () => {
    stubFetch();
    const list = sections(await read(5107), CASE);
    expect(list.find((s) => s.key === 'happened')!.items[0].text).toBe('Try again shortly.');
    expect(list.some((s) => s.key === 'issue') && list.some((s) => s.key === 'next')).toBe(true);
  });

  it('maps errors to the spec wording (AC12, AC13)', () => {
    const e = (status: number, kind: ApiError['kind']) => new ApiError(status, kind, 'x', 'server words');
    expect(errorText(e(404, 'not_found'))).toBe('This record is unavailable.');
    expect(errorText(e(403, 'csrf'))).toBe('Refresh your session and try again.');
    expect(errorText(e(403, 'forbidden'))).not.toBe('Refresh your session and try again.');
    expect(errorText(e(429, 'rate_limited'))).toBe('Try again shortly.');
    expect(errorText(e(0, 'network'))).toBe('We couldn’t reach the server.');
  });
});

describe('the mapper edge cases (AC19)', () => {
  const base = async (): Promise<Readback> => {
    stubFetch();
    return read(5101);
  };

  it('age words: null is not 0, 1 day, Today', () => {
    expect([ageText(null), ageText(0), ageText(1), ageText(3)]).toEqual(['Not recorded', 'Today', '1 day', '3 days']);
  });

  it('an unknown timeline kind and an empty status show raw text; an empty timeline says so', async () => {
    const r = await base();
    (r.detail as { timeline: unknown[] }).timeline = [{ id: null, kind: 'odd', status: '', at: '2026-11-20T08:30:00Z' }];
    expect(sections(r, CASE).find((s) => s.key === 'happened')!.items[0].text).toBe('odd');
    (r.detail as { timeline: unknown[] }).timeline = [];
    expect(sections(r, CASE).find((s) => s.key === 'happened')!.items[0].text).toBe('Nothing has happened yet.');
  });

  it('null timing draws no timing rows; null dates read Not set; the target is drawn when sent', async () => {
    const r = await base();
    const m = r.messages as { timing: Record<string, unknown> | null };
    m.timing = { ...m.timing, reminder_due_at: null, escalation_target: 'PMO lead' };
    const timing = sections(r, CASE).find((s) => s.key === 'timing')!;
    expect(timing.items.map((i) => i.value)).toEqual(['Not set', expect.any(String), 'PMO lead']);
    m.timing = null;
    expect(sections(r, CASE).some((s) => s.key === 'timing')).toBe(false);
  });

  it('a no-owner banner is not shown on a Resolved issue', async () => {
    const r = await base();
    r.followup = { ...r.followup, team: { ...r.followup.team, assignment_id: null }, issue: { ...r.followup.issue, status: 'Resolved' } } as Followup;
    expect(sections(r, CASE).some((s) => s.key === 'no-owner')).toBe(false);
  });
});
