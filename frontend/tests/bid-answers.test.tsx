// @vitest-environment jsdom
// F-96: the RFP response panel on a live work item (reads), against the mock itself.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import type { LiveBidAnswers } from '@/api/types';
import { bidAnswersAdapter } from '@/features/workspace/bidAnswersAdapter';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { resetWorkLive, workLive } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4401', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

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
  await screen.findByRole('list', { name: 'Requirements' }, { timeout: 8000 }).catch(() => screen.findByText(/No requirements are listed/, {}, { timeout: 8000 }));
};
const rowOf = (key: string) => screen.getByRole('heading', { level: 3, name: key }).closest('li') as HTMLElement;
const read = (id: number) => (workLive({ method: 'get', url: new URL(`/api/v1/work/${id}/bid-answers`, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, LiveBidAnswers])[1];
const ctx = { workId: 4401, caseId: 'c', revision: 6, caseRevision: 12 };

describe('the reads', () => {
  it('draws every row with its disposition and status words, and sends nothing', async () => {
    await open(4401);
    for (const [key, status] of [['R1', 'Current'], ['R2', 'Suggestion ready'], ['R3', 'Reviewed'], ['R4', 'Queued'], ['R5', 'Tola is working'], ['R6', 'On hold'], ['R7', 'Out of date']]) {
      expect(within(rowOf(key)).getByText(status)).toBeTruthy();
      expect(within(rowOf(key)).getByText('Addressed')).toBeTruthy();
    }
    expect(within(rowOf('R8')).getByText('Needs clarification')).toBeTruthy();
    expect(posts).toEqual([]);
  });
  it('shows Tola’s suggestion with its source, the quote with its page, and an unsaved answer as such', async () => {
    await open(4401);
    const r2 = within(rowOf('R2'));
    expect(r2.getByText('Data is encrypted at rest and in transit.')).toBeTruthy();
    expect(r2.getByText(/Source: synthetic:lagoon-rfp, version 1/)).toBeTruthy();
    expect(r2.getByText(/The supplier shall encrypt client data\./)).toBeTruthy();
    expect(r2.getByText(/page 12/)).toBeTruthy();
    expect(within(rowOf('R8')).queryByText(/page/)).toBeNull();
    expect(r2.getByText('No answer saved.')).toBeTruthy();
    // a reviewed row shows the saved answer once, not the suggestion beside it
    expect(within(rowOf('R3')).getAllByText('Support is available on every business day.')).toHaveLength(1);
  });
  it('draws the counts the live read gives and nothing it does not (no filters, progress bar or checklist)', async () => {
    await open(4401);
    const main = document.body;
    expect(screen.getByText('Requirements', { selector: 'h2' })).toBeTruthy();
    expect(main.textContent).not.toMatch(/Before review|Progress|filter/i);
    expect(screen.queryByText('Not shown to you')).toBeNull();
  });
  it('a read-only response shows the Engineering Lead’s return and the rows the person cannot see', async () => {
    await open(4402);
    expect(screen.getByText(/Engineering Lead: returned/)).toBeTruthy();
    expect(screen.getByText(/The hosting answer needs the region names\./)).toBeTruthy();
    expect(screen.getByText('Not shown to you')).toBeTruthy();
  });
  it('an empty response says so', async () => {
    await open(4403);
    expect(screen.getByText(/No requirements are listed/)).toBeTruthy();
  });
});

describe('the descriptors', () => {
  it('give the exact tokens and one operation key per requirement', () => {
    const cmds = bidAnswersAdapter.commands!(read(4401), ctx);
    const review = cmds.find((c) => c.id === 'bid-answers.review')!;
    expect(review.url).toBe('/api/v1/work/4401/bid-answers');
    expect(review.idempotency.field).toBeNull();
    expect(review.successStatuses).toEqual([201]);
    expect(review.body({ decisions: [] })).toEqual({ decisions: [], action: 'review', expected_revision: 6, case_revision: 12 });
    expect(cmds.find((c) => c.id === 'bid-answers.undo')!.body({ review_id: 7001 })).toEqual({ review_id: 7001, action: 'undo', expected_revision: 6, case_revision: 12 });
    const suggests = cmds.filter((c) => c.id.startsWith('bid-answers.suggest.'));
    expect(suggests).toHaveLength(8);
    const r1 = suggests[0].body({});
    expect(r1).toMatchObject({ action: 'suggest', key: 'R1', expected_revision: 6, case_revision: 12 });
    expect(r1.operation_key).toMatch(/^[0-9a-f-]{36}$/);
    expect(new Set(suggests.map((c) => c.idempotency.value)).size).toBe(8);
  });
  it('hold every write, with a reason, when the person cannot write or the version is unknown', () => {
    expect(bidAnswersAdapter.commands!(read(4402), ctx).every((c) => /can’t change/.test(c.disabledReason ?? ''))).toBe(true);
    const unknown = { ...read(4401), expected_revision: null } as unknown as LiveBidAnswers;
    expect(bidAnswersAdapter.commands!(unknown, ctx).every((c) => /current version/.test(c.disabledReason ?? ''))).toBe(true);
  });
});

const inRow = (key: string, name: string) => within(rowOf(key)).queryByRole('button', { name }) as HTMLButtonElement | null;
const reviewBody = (patch: Record<string, unknown> = {}) => ({
  action: 'review',
  expected_revision: 6,
  case_revision: 12,
  decisions: [{ suggestion: 501, predecessor: 0, verdict: 'accept', answer: 'Data is encrypted at rest and in transit.', disposition: 'addressed', note: '', ...patch }],
});

describe('who sees which control', () => {
  it('the buttons follow the row’s own flags, and nothing is sent until a press', async () => {
    await open(4401);
    for (const n of ['Accept', 'Edit', 'Write your own']) expect(inRow('R2', n)).toBeTruthy();
    expect(inRow('R2', 'Ask Tola')).toBeNull();
    expect(inRow('R3', 'Undo')).toBeTruthy();
    expect(inRow('R3', 'Ask Tola')).toBeNull();
    for (const k of ['R1', 'R7', 'R8']) expect(inRow(k, 'Ask Tola')).toBeTruthy();
    for (const k of ['R4', 'R5', 'R6']) expect(inRow(k, 'Ask Tola')).toBeNull();
    expect(within(rowOf('R6')).getByText(/on hold/)).toBeTruthy();
    expect(inRow('R1', 'Accept')).toBeNull();
    expect(posts).toEqual([]);
  });
  it('a read-only response, and a suggestion with no source, draw no controls', async () => {
    await open(4402);
    expect(screen.queryAllByRole('button').filter((b) => /Accept|Edit|Ask Tola|Undo|Send for review/.test(b.textContent ?? ''))).toEqual([]);
    cleanup();
    await open(4404);
    expect(inRow('R1', 'Accept')).toBeNull();
  });
  it('Send for review is held, with its reason, while the response has no bid pack', async () => {
    await open(4403);
    const send = screen.getByRole('button', { name: 'Send for review' }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    expect(screen.getByText('No bid pack has been prepared yet.')).toBeTruthy();
    fireEvent.click(send);
    expect(posts).toEqual([]);
  });
  it('Send for review sends the pack and version the bid pack read gives, then the page says it is with the reviewer', async () => {
    await open(4401);
    const send = screen.getByRole('button', { name: 'Send for review' }) as HTMLButtonElement;
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    await screen.findByText(/The response was sent for review\. This item is now:/);
    expect(posts).toEqual([{ path: '/api/v1/work/4401/bid-pack/review-request', body: { pack_id: 77, version_id: 801, expected_revision: 6, case_revision: 12 } }]);
    await waitFor(() => expect((screen.getByRole('button', { name: 'Send for review' }) as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getByText('This pack is already with the reviewer.')).toBeTruthy();
  });
});

describe('review decisions', () => {
  it('Accept sends the exact body, re-reads and then shows the saved answer with Undo', async () => {
    await open(4401);
    fireEvent.click(inRow('R2', 'Accept')!);
    await screen.findByText(/Your answer for R2 was saved\. This item is now:/);
    expect(posts).toEqual([{ path: '/api/v1/work/4401/bid-answers', body: reviewBody() }]);
    await waitFor(() => expect(within(rowOf('R2')).getByText('Reviewed')).toBeTruthy());
    expect(inRow('R2', 'Undo')).toBeTruthy();
    expect(inRow('R2', 'Accept')).toBeNull();
    expect(within(rowOf('R2')).getAllByText('Data is encrypted at rest and in transit.')).toHaveLength(1);
  });
  it('Edit starts from the suggestion, sends the edited wording and the chosen disposition', async () => {
    await open(4401);
    fireEvent.click(inRow('R2', 'Edit')!);
    const answer = screen.getByLabelText(/Answer/) as HTMLTextAreaElement;
    expect(answer.value).toBe('Data is encrypted at rest and in transit.');
    fireEvent.change(answer, { target: { value: 'Data is encrypted with keys we hold.' } });
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'tightened' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save answer' }));
    await screen.findByText(/Your answer for R2 was saved\./);
    expect(posts[0].body).toEqual(reviewBody({ verdict: 'edit', answer: 'Data is encrypted with keys we hold.', note: 'tightened' }));
    await waitFor(() => expect(within(rowOf('R2')).getByText('Data is encrypted with keys we hold.')).toBeTruthy());
  });
  it('Write your own starts blank, will not send blank, then sends verdict replace', async () => {
    await open(4401);
    fireEvent.click(inRow('R2', 'Write your own')!);
    expect((screen.getByLabelText(/Answer/) as HTMLTextAreaElement).value).toBe('');
    expect(await screen.findByText('Write the answer first.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Save answer' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Answer/), { target: { value: 'Our own words.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save answer' }));
    await screen.findByText(/Your answer for R2 was saved\./);
    expect(posts[0].body).toEqual(reviewBody({ verdict: 'replace', answer: 'Our own words.' }));
  });
  it('Undo sends the review id and the suggestion can be reviewed again, with the new review as its predecessor', async () => {
    await open(4401);
    fireEvent.click(inRow('R3', 'Undo')!);
    await screen.findByText(/The earlier answer for R3 is back\./);
    expect(posts).toEqual([{ path: '/api/v1/work/4401/bid-answers', body: { action: 'undo', expected_revision: 6, case_revision: 12, review_id: 7001 } }]);
    await waitFor(() => expect(inRow('R3', 'Accept')).toBeTruthy());
    fireEvent.click(inRow('R3', 'Accept')!);
    await screen.findByText(/Your answer for R3 was saved\./);
    const decision = (posts[1].body.decisions as Record<string, unknown>[])[0];
    expect(decision).toMatchObject({ suggestion: 502, predecessor: 9001 });
    expect(posts[1].body.expected_revision).toBe(7);
  });
});

describe('ask Tola', () => {
  it('sends the key, one operation key and no prior answer, then shows the row queued', async () => {
    await open(4401);
    fireEvent.click(inRow('R1', 'Ask Tola')!);
    await screen.findByText(/Tola was asked for R1\./);
    expect(posts[0].body).toMatchObject({ action: 'suggest', key: 'R1', expected_revision: 6, case_revision: 12 });
    expect(posts[0].body.operation_key).toMatch(/^[0-9a-f-]{36}$/);
    expect(posts[0].body).not.toHaveProperty('prior_answer');
    await waitFor(() => expect(within(rowOf('R1')).getByText('Queued')).toBeTruthy());
    expect(inRow('R1', 'Ask Tola')).toBeNull();
  });
  it('offers the earlier winning answers and sends the picked token', async () => {
    await open(4401);
    const r8 = within(rowOf('R8'));
    fireEvent.click(r8.getByRole('combobox', { name: /earlier answer/i }));
    fireEvent.click(await screen.findByRole('option', { name: 'Lagos health RFP, won 2025' }));
    fireEvent.click(inRow('R8', 'Ask Tola')!);
    await screen.findByText(/Tola was asked for R8\./);
    expect(posts[0].body).toMatchObject({ key: 'R8', prior_answer: 'won-2025-lagos' });
  });
});

describe('when a write goes wrong', () => {
  it('422 shows the server words and keeps the person’s answer', async () => {
    scenario = 'w422';
    await open(4401);
    fireEvent.click(inRow('R2', 'Write your own')!);
    fireEvent.change(screen.getByLabelText(/Answer/), { target: { value: 'Kept words.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save answer' }));
    await screen.findByText(/The answer was not accepted\./);
    expect((screen.getByLabelText(/Answer/) as HTMLTextAreaElement).value).toBe('Kept words.');
    expect(posts).toHaveLength(1);
  });
  it('409 re-reads, says it changed, and keeps the form words', async () => {
    scenario = 'w409';
    await open(4401);
    fireEvent.click(inRow('R2', 'Edit')!);
    fireEvent.change(screen.getByLabelText(/Answer/), { target: { value: 'Mine.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save answer' }));
    await screen.findByText(/This changed while you were working/);
    expect((screen.getByLabelText(/Answer/) as HTMLTextAreaElement).value).toBe('Mine.');
  });
  it('a dropped answer says it could not confirm, and locks the buttons until the page moves', async () => {
    scenario = 'wdrop0';
    await open(4401);
    fireEvent.click(inRow('R2', 'Accept')!);
    await screen.findByText(/We couldn’t confirm that this happened/);
    expect(inRow('R2', 'Accept')!.disabled).toBe(true);
    expect(inRow('R1', 'Ask Tola')!.disabled).toBe(true);
    fireEvent.click(inRow('R2', 'Accept')!);
    expect(posts).toHaveLength(1);
  });
});
