// @vitest-environment jsdom
// F-89: review (approve, return, refuse) and correct on the weekly report panel of a live work item, against the mock itself.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import type { LiveWeeklyReport } from '@/api/types';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';
import { weeklyReportAdapter } from '@/features/workspace/weeklyReportAdapter';

// @ts-expect-error plain ESM module without type declarations
import { resetWorkLive, workLive } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4130', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let posts: { path: string; body: Record<string, unknown> }[];

beforeEach(() => {
  resetWorkLive();
  setCsrfToken('t');
  resetScopedWriteLocks();
  scenario = undefined;
  posts = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
      const post = request.method !== 'GET';
      const raw = post ? await request.text() : undefined;
      if (post) posts.push({ path: url.pathname, body: JSON.parse(raw ?? '{}') });
      const reply = workLive({ method: request.method.toLowerCase(), url, scenario: post ? scenario : undefined, csrfOk: true, persona: 'finance_lead', rawBytes: raw ? Buffer.from(raw) : undefined }) as [number | 'drop', unknown];
      if (reply[0] === 'drop') throw new TypeError('network');
      return json(reply[0], reply[1]);
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number) => {
  render(<LiveWorkItemView id={String(id)} tab="overview" />);
  await screen.findByRole('heading', { level: 1 }, { timeout: 8000 });
  await screen.findByText('Recipients', {}, { timeout: 8000 });
};
const btn = (name: string) => screen.queryByRole('button', { name });
const report = (id: number) => (workLive({ method: 'get', url: new URL(`/api/v1/work/${id}/weekly-report`, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, LiveWeeklyReport])[1];
const ctx = { workId: 4130, caseId: 'c', revision: 6, caseRevision: 12 };

describe('the descriptors', () => {
  it('lists a button only for a verdict the readback lists, with the exact body and no action', () => {
    const cmds = weeklyReportAdapter.commands!(report(4130), ctx);
    expect(cmds.map((c) => c.id)).toEqual(['weekly-report.correct', 'weekly-report.approve', 'weekly-report.return', 'weekly-report.reject']);
    const approve = cmds[1];
    expect(approve.url).toBe('/api/v1/work/4130/reviews');
    expect(approve.idempotency.field).toBeNull();
    expect(approve.successStatuses).toEqual([200]);
    expect(approve.body({ note: '' })).toEqual({ kind: 'document', expected_revision: 6, case_revision: 12, version_id: 9101, verdict: 'approve', note: '' });
    expect(cmds[3].body({ note: 'x' })).toMatchObject({ verdict: 'reject', note: 'x' });
    expect(weeklyReportAdapter.commands!(report(4131), ctx).map((c) => c.id)).toEqual(['weekly-report.correct', 'weekly-report.approve', 'weekly-report.return']);
  });
  it('offers no review without a version, and holds Approve without the matching text', () => {
    expect(weeklyReportAdapter.commands!(report(4134), ctx).map((c) => c.id)).toEqual(['weekly-report.correct']);
    for (const id of [4136, 4137]) expect(weeklyReportAdapter.commands!(report(id), ctx).map((c) => c.id)).toEqual(['weekly-report.correct', 'weekly-report.return', 'weekly-report.reject']);
  });
  it('describes correct with a reason when it is not offered or has no parts', () => {
    expect(weeklyReportAdapter.commands!(report(4132), ctx)[0].disabledReason).toBeUndefined();
    expect(weeklyReportAdapter.commands!(report(4133), ctx)[0].disabledReason).toBeTruthy();
    expect(weeklyReportAdapter.commands!(report(4135), ctx)[0].disabledReason).toMatch(/aren’t available/);
  });
  it('a missing token holds every command with the reload words', () => {
    const cmds = weeklyReportAdapter.commands!({ ...report(4130), expected_revision: null } as unknown as LiveWeeklyReport, ctx);
    for (const c of cmds.filter((x) => x.id !== 'weekly-report.correct')) expect(c.disabledReason).toMatch(/Reload and try again/);
  });
});

describe('the review block', () => {
  it('4130 shows the text, the note beside Risks, escaped, and all three buttons', async () => {
    await open(4130);
    expect(screen.getByText(/Build is <b>on track<\/b>/)).toBeTruthy();
    expect(screen.getByText('Note from the review')).toBeTruthy();
    for (const n of ['Approve and send', 'Return with a note', 'Refuse']) expect(btn(n)).toBeTruthy();
    expect(screen.getByText('Approving sends this exact version to the client.')).toBeTruthy();
  });
  it('4131 shows two buttons, 4133 none, 4134 none', async () => {
    await open(4131);
    expect(btn('Refuse')).toBeNull();
    expect(btn('Return with a note')).toBeTruthy();
    cleanup();
    await open(4133);
    expect(screen.queryByText('Your review')).toBeNull();
    expect(screen.queryByText('Edit your update')).toBeNull();
    cleanup();
    await open(4134);
    expect(btn('Approve and send')).toBeNull();
  });
  it('4136 and 4137 hold Approve with the line; 4138 draws the other note', async () => {
    await open(4136);
    expect(btn('Approve and send')).toBeNull();
    expect(btn('Refuse')).toBeTruthy();
    expect(screen.getByText(/can’t be approved from this page/)).toBeTruthy();
    cleanup();
    await open(4138);
    expect(screen.getByText('Other notes')).toBeTruthy();
  });
  it('Approve sends one exact body, re-reads, says Recorded and the buttons go', async () => {
    await open(4130);
    fireEvent.click(btn('Approve and send')!);
    await screen.findByText(/Recorded\. This item is now:/);
    expect(posts).toEqual([{ path: '/api/v1/work/4130/reviews', body: { kind: 'document', expected_revision: 6, case_revision: 12, version_id: 9101, verdict: 'approve', note: '' } }]);
    await waitFor(() => expect(btn('Approve and send')).toBeNull());
    expect(screen.queryByText(/Sent|Delivered/)).toBeNull();
    expect(screen.getByText('No receipt yet')).toBeTruthy();
  });
  it('Return and Refuse need a note first, then send it with their verdict', async () => {
    await open(4130);
    fireEvent.click(btn('Return with a note')!);
    expect(await screen.findByText('Write a note first.')).toBeTruthy();
    fireEvent.click(btn('Refuse')!);
    expect(posts).toEqual([]);
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'Fix the dates.' } });
    fireEvent.click(btn('Return with a note')!);
    await screen.findByText(/Recorded\./);
    expect(posts).toHaveLength(1);
    expect(posts[0].body).toMatchObject({ verdict: 'return', note: 'Fix the dates.' });
  });
  it('a double press sends once', async () => {
    await open(4130);
    const b = btn('Approve and send')!;
    fireEvent.click(b);
    fireEvent.click(b);
    await screen.findByText(/Recorded\./);
    expect(posts).toHaveLength(1);
  });
  it('403 shows the server words and keeps the buttons; 409 re-reads and keeps the note', async () => {
    scenario = 'w403';
    await open(4130);
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'keep me' } });
    fireEvent.click(btn('Approve and send')!);
    await screen.findByText(/You can’t do this\./);
    expect(screen.getByText(/You wrote this report/)).toBeTruthy();
    cleanup();
    scenario = 'w409';
    await open(4131);
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'keep me' } });
    fireEvent.click(btn('Return with a note')!);
    await screen.findByText(/This changed while you were working/);
    expect((screen.getByLabelText(/Note/) as HTMLTextAreaElement).value).toBe('keep me');
    expect(posts).toHaveLength(2); // one press each, none repeated
  });
  it('a dropped connection locks all the buttons until the report moves', async () => {
    scenario = 'wdrop0';
    await open(4130);
    fireEvent.click(btn('Approve and send')!);
    await screen.findByText(/We couldn’t confirm that this happened/);
    for (const n of ['Approve and send', 'Return with a note', 'Refuse']) expect((btn(n) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(btn('Refuse')!);
    expect(posts).toHaveLength(1);
  });
});

describe('correct after a return', () => {
  it('4132 quotes the note, prefilled form sends the exact body, then the edit block goes', async () => {
    await open(4132);
    expect(screen.getByText(/Please add the 14 Nov supplier delay/)).toBeTruthy();
    fireEvent.click(btn('Edit your update')!);
    expect(screen.getAllByText('2 records cited').length).toBeGreaterThan(1);
    const send = btn('Send for review') as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Reason for the change/), { target: { value: 'Added the delay' } });
    fireEvent.click(btn('Send for review')!);
    await screen.findByText(/Your update was sent for review\. This item is now:/);
    const { body } = posts[0];
    expect(posts[0].path).toBe('/api/v1/work/4132/weekly-report');
    expect(body).toEqual({
      action: 'correct',
      expected_revision: 6,
      case_revision: 12,
      draft_id: null,
      selection: report(4132).selection,
      parts: {
        status: { text: 'Build is on track.', evidence_ids: [301] },
        risks: { text: 'One supplier is late.', evidence_ids: [302, 303] },
        timeline: { text: 'Hand-over on 5 Dec.', evidence_ids: [] },
        next_steps: { text: 'Confirm the test date.', evidence_ids: [304] },
      },
      reason: 'Added the delay',
    });
    await waitFor(() => expect(btn('Edit your update')).toBeNull());
    expect(within(document.body).queryByText('Reason for the change')).toBeNull();
  });
  it('4135 shows why it cannot be edited and 4133 shows nothing', async () => {
    await open(4135);
    expect(screen.getByText(/aren’t available to edit here/)).toBeTruthy();
    expect(btn('Edit your update')).toBeNull();
  });
});
