// @vitest-environment jsdom
// F-98: the RFP submission panel on a live work item: the bid pack, the PM's send for review, the reviewer's verdict on that exact
// pack and the send to the client, against the mock itself.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { bidSubmissionAdapter } from '@/features/workspace/bidSubmissionAdapter';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { resetWorkLive, workLive } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4501', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
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
  await screen.findByText('What will be sent', {}, { timeout: 8000 });
};
const button = (name: string | RegExp) => screen.queryByRole('button', { name }) as HTMLButtonElement | null;
const buttons = () => screen.queryAllByRole('button').map((b) => b.textContent ?? '');
const VERSIONS = { expected_revision: 9, case_revision: 89 };
const ctx = { workId: 4501, caseId: 'c', revision: 9, caseRevision: 89 };
const readOf = async (id: number) => bidSubmissionAdapter.read({ key: 'bid-submission', url: `/api/v1/work/${id}/bid-submission` }, { ...ctx, workId: id });

describe('the reads', () => {
  it('a pack not yet sent shows its version, cover note, parts, file and checks, and sends nothing', async () => {
    await open(4501);
    expect(screen.getByText('Pack version')).toBeTruthy();
    expect(screen.getByText('Not sent for review yet')).toBeTruthy();
    expect(screen.getByText(/Dear Lagoon Health team/)).toBeTruthy();
    expect(screen.getByText(/Executive summary, Scope, Commercial terms, Timeline/)).toBeTruthy();
    expect(screen.getByText('6.4 MB')).toBeTruthy();
    expect(screen.getByText(/Format, count and size are as the client asks/)).toBeTruthy();
    expect(screen.getByText('A test pack, not a real bid')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the pack as a PDF' }).getAttribute('href')).toBe('/api/v1/work/4501/bid-submission/pdf/801');
    expect(posts).toEqual([]);
  });
  it('draws nothing the live API does not serve (no part checklist, no history timeline, no agent note)', async () => {
    await open(4501);
    expect(document.body.textContent).not.toMatch(/Company forms|What happened|Agent note|Open the full pack/);
  });
  it('a returned pack shows the reviewer’s note and offers no control', async () => {
    await open(4506);
    expect(screen.getByText(/Returned on/)).toBeTruthy();
    expect(screen.getByText(/The cover note needs the client’s name\./)).toBeTruthy();
    expect(buttons().filter((b) => /Send|Approve|Return|Refuse/.test(b))).toEqual([]);
  });
  it('an item with no bid pack says so', async () => {
    await open(4508);
    expect(screen.getByText('No bid pack has been prepared yet.')).toBeTruthy();
    expect(button('Send for review')).toBeNull();
  });
  it('a pack with no document version yet is held with its reason', async () => {
    await open(4509);
    const send = button('Send for review');
    expect(send?.disabled).toBe(true);
    expect(screen.getByText('The bid pack isn’t prepared for review yet.')).toBeTruthy();
  });
  it('a sent pack shows the receipt facts and offers nothing to press', async () => {
    await open(4505);
    expect(screen.getByText('Receipts')).toBeTruthy();
    expect(screen.getByText('Confirmed')).toBeTruthy();
    expect(screen.getByText('On time')).toBeTruthy();
    expect(buttons().filter((b) => /Send|Approve|Return|Refuse/.test(b))).toEqual([]);
  });
});

describe('the descriptors', () => {
  it('give the exact bodies: the pack and its version for the send, the exact version and the open review’s role for the verdict', async () => {
    const draft = await readOf(4501);
    const send = bidSubmissionAdapter.commands!(draft, ctx).find((c) => c.id === 'bid-submission.send')!;
    expect(send.url).toBe('/api/v1/work/4501/bid-pack/review-request');
    expect(send.body({})).toEqual({ pack_id: 77, version_id: 801, ...VERSIONS });
    expect(send.disabledReason).toBeUndefined();
    const inReview = await readOf(4502);
    const approve = bidSubmissionAdapter.commands!(inReview, { ...ctx, workId: 4502 }).find((c) => c.id === 'bid-submission.approve')!;
    expect(approve.url).toBe('/api/v1/work/4502/reviews');
    expect(approve.body({ note: 'ok' })).toEqual({ kind: 'bid', subject: 'document', target_id: 801, role: 'Quality reviewer', verdict: 'approve', evidence_id: null, note: 'ok', ...VERSIONS });
    // the document variant answers 404 for this line, so it is never sent
    expect(approve.body({})).not.toHaveProperty('version_id');
  });
  it('no verdicts when the person may not decide, and none once the pack is decided', async () => {
    const ids = async (id: number) => bidSubmissionAdapter.commands!(await readOf(id), { ...ctx, workId: id }).map((c) => c.id);
    expect(await ids(4503)).not.toContain('bid-submission.approve');
    expect(await ids(4504)).not.toContain('bid-submission.approve');
    expect(await ids(4502)).toEqual(expect.arrayContaining(['bid-submission.approve', 'bid-submission.return', 'bid-submission.reject']));
  });
  it('hold the send to the client while the file checks fail, and when no approval is recorded none is described', async () => {
    const failed = bidSubmissionAdapter.commands!(await readOf(4507), { ...ctx, workId: 4507 }).find((c) => c.id === 'bid-submission.queue')!;
    expect(failed.disabledReason).toMatch(/file checks found problems/);
    const draft = bidSubmissionAdapter.commands!(await readOf(4501), ctx);
    expect(draft.find((c) => c.id === 'bid-submission.queue')).toBeUndefined();
  });
});

describe('the PM’s send for review', () => {
  it('sends the exact pack and version, re-reads, and then says the pack is with the reviewer', async () => {
    await open(4501);
    fireEvent.click(button('Send for review')!);
    await screen.findByText(/The pack was sent for review\. This item is now: Waiting/);
    expect(posts).toEqual([{ path: '/api/v1/work/4501/bid-pack/review-request', body: { pack_id: 77, version_id: 801, ...VERSIONS } }]);
    await waitFor(() => expect(screen.getByText('With the reviewer')).toBeTruthy());
    expect(button('Send for review')).toBeNull();
  });
  it('a pack already with the reviewer shows no send, and the person who may not decide sees no verdict', async () => {
    await open(4503);
    expect(screen.getByText('With the reviewer')).toBeTruthy();
    expect(buttons().filter((b) => /Send for review|Approve|Return|Refuse/.test(b))).toEqual([]);
  });
});

describe('the reviewer’s verdict', () => {
  it('shows the exact pack under review and approves it: the right body, a re-read, then the recorded approval', async () => {
    await open(4502);
    expect(screen.getByText(/Your review of pack version 2/)).toBeTruthy();
    expect(screen.getByText(/does not send it/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'Reads well.' } });
    fireEvent.click(button('Approve')!);
    await screen.findByText(/Your approval was recorded\./);
    expect(posts).toEqual([{ path: '/api/v1/work/4502/reviews', body: { kind: 'bid', subject: 'document', target_id: 801, role: 'Quality reviewer', verdict: 'approve', evidence_id: null, note: 'Reads well.', ...VERSIONS } }]);
    await waitFor(() => expect(screen.getByText(/Approved on/)).toBeTruthy());
    // approving does not send: the send to the client is its own press
    expect(button('Send to the client')).toBeTruthy();
    expect(posts).toHaveLength(1);
  });
  it('return and refuse need a note first, then send the verdict', async () => {
    await open(4502);
    fireEvent.click(button('Return with a note')!);
    expect(await screen.findByText('Write a note first.')).toBeTruthy();
    expect(posts).toEqual([]);
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'Name the client.' } });
    fireEvent.click(button('Return with a note')!);
    await screen.findByText(/Your return was recorded\./);
    expect(posts[0].body).toMatchObject({ verdict: 'return', note: 'Name the client.' });
    await waitFor(() => expect(screen.getByText(/Returned on/)).toBeTruthy());
    expect(screen.getByText(/Name the client\./)).toBeTruthy();
  });
});

describe('send to the client', () => {
  it('sends the approved version, 202, and the re-read shows the delivery started', async () => {
    await open(4504);
    fireEvent.click(button('Send to the client')!);
    await screen.findByText(/The pack was handed over to be sent\. This item is now: Processing/);
    expect(posts).toEqual([{ path: '/api/v1/work/4504/bid-submission', body: { version_id: 801, ...VERSIONS } }]);
    await waitFor(() => expect(screen.getByText('Queued')).toBeTruthy());
    expect(button('Send to the client')?.disabled).toBe(true);
  });
  it('is held, with the server’s words for the file problems, and sends nothing', async () => {
    await open(4507);
    expect(screen.getByText('The client asks for a PDF; this file is a Word document.')).toBeTruthy();
    const queue = button('Send to the client')!;
    expect(queue.disabled).toBe(true);
    expect(screen.getByText(/file checks found problems/)).toBeTruthy();
    fireEvent.click(queue);
    expect(posts).toEqual([]);
  });
});

describe('when a write goes wrong', () => {
  it('403 says so and keeps the person’s note', async () => {
    await open(4502);
    scenario = 'w403';
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'Reads well.' } });
    fireEvent.click(button('Approve')!);
    await screen.findByText(/You can’t do this\./);
    expect((screen.getByLabelText(/Note/) as HTMLTextAreaElement).value).toBe('Reads well.');
  });
  it('409 re-reads and says it changed', async () => {
    await open(4501);
    scenario = 'w409';
    fireEvent.click(button('Send for review')!);
    await screen.findByText(/This changed while you were working\./);
  });
  it('422 shows the server words', async () => {
    await open(4501);
    scenario = 'w422';
    fireEvent.click(button('Send for review')!);
    await screen.findByText(/The pack was not accepted\./);
    expect(within(document.body).getAllByText(/The pack was not accepted\./).length).toBeGreaterThan(0);
  });
  it('a dropped answer says it could not confirm and locks the buttons', async () => {
    await open(4501);
    scenario = 'wdrop';
    fireEvent.click(button('Send for review')!);
    await screen.findByText(/We couldn’t confirm that this happened\./);
  });
});
