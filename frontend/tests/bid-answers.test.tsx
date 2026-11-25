// @vitest-environment jsdom
// F-96: the RFP response panel on a live work item (reads), against the mock itself.
import { cleanup, render, screen, within } from '@testing-library/react';
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
