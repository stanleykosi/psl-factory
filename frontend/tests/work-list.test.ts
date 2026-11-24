// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { coverageNotes, lineTitle, MAX_EMPTY_PAGES, mergeRefresh, shownText, stateTag, useWorkCounts, useWorkList, type WorkListPage, type WorkListRow } from '@/features/work-list';

import { page as basePage, row as baseRow } from './work-list-rows';

// The shared live work list (F-62): paging that skips empty pages, filters that restart, coverage and errors.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const row = (id: number, over: Partial<WorkListRow> = {}) => baseRow(id, { title: `Item ${id}`, owner: null, ...over });
const page = (n: number, items: WorkListRow[], next: number | null, over: Partial<WorkListPage> = {}) =>
  basePage(items, { page: n, next_page: next, evaluated: n * 8, lines: [{ key: 'finance-ledger/v1', title: 'Finance ledger' }], ...over });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));
const asked = () => urls().map((u) => u.searchParams.get('page'));
const serve = (answer: (url: URL) => Response | Promise<Response>) => fetchStub.mockImplementation(async (request) => answer(new URL(request.url)));

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const ready = (result: { current: ReturnType<typeof useWorkList> }) => {
  const { state } = result.current;
  if (state.status !== 'ready') throw new Error(`not ready: ${state.status}`);
  return state;
};
const settled = (result: { current: ReturnType<typeof useWorkList> }) => waitFor(() => expect(result.current.state.status).not.toBe('loading'));

describe('useWorkList', () => {
  it('asks page 1 of the queue, keeps the server order and de-duplicates by id on later pages', async () => {
    serve((url) => (url.searchParams.get('page') === '1' ? json(200, page(1, [row(9), row(3), row(7)], 2)) : json(200, page(2, [row(7), row(1)], null))));
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    expect(urls()[0].pathname).toBe('/api/v1/work');
    expect(urls()[0].searchParams.get('queue')).toBe('verified');
    expect(asked()).toEqual(['1']);
    expect(ready(result).items.map((r) => r.id)).toEqual([9, 3, 7]);
    expect(ready(result).more).toBe('idle');
    await act(() => result.current.loadMore());
    expect(ready(result).items.map((r) => r.id)).toEqual([9, 3, 7, 1]);
    expect(ready(result).more).toBe('done');
  });

  it('works the same for another queue (My work reuses it unchanged)', async () => {
    serve(() => json(200, page(1, [row(5, { state: 'ready' })], null)));
    const { result } = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(result);
    expect(urls()[0].searchParams.get('queue')).toBe('needs_me');
    expect(ready(result).items).toHaveLength(1);
    expect(ready(result).more).toBe('done');
  });

  it('Show more skips an empty page: page 2 empty with next_page 3 adds the rows of page 3 in one click', async () => {
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n === 1 ? page(1, [row(1)], 2) : n === 2 ? page(2, [], 3) : page(3, [row(30)], null));
    });
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    await act(() => result.current.loadMore());
    expect(asked()).toEqual(['1', '2', '3']);
    expect(ready(result).items.map((r) => r.id)).toEqual([1, 30]);
  });

  it('after ten empty pages in a click the button says Keep looking, the shown rows stay, and one more click asks ten more', async () => {
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n === 1 ? page(1, [row(1)], 2) : n === 25 ? page(25, [row(250)], null) : page(n, [], n + 1));
    });
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    await act(() => result.current.loadMore());
    expect(asked().slice(1)).toEqual(Array.from({ length: MAX_EMPTY_PAGES }, (_, i) => String(i + 2)));
    expect(ready(result).more).toBe('keep-looking');
    expect(ready(result).items.map((r) => r.id)).toEqual([1]);
    await act(() => result.current.loadMore());
    expect(asked()).toHaveLength(1 + 2 * MAX_EMPTY_PAGES);
    expect(ready(result).more).toBe('keep-looking');
    await act(() => result.current.loadMore());
    expect(ready(result).items.map((r) => r.id)).toEqual([1, 250]);
    expect(ready(result).more).toBe('done');
  });

  it('an empty first page with next_page set keeps asking before any empty state', async () => {
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n < 3 ? page(n, [], n + 1) : page(3, [row(3)], null));
    });
    const { result } = renderHook(() => useWorkList({ queue: 'exceptions' }));
    await settled(result);
    expect(asked()).toEqual(['1', '2', '3']);
    expect(ready(result).items.map((r) => r.id)).toEqual([3]);
  });

  it('a first page that stays empty for ten pages is keep-looking, not empty; an empty last page is complete', async () => {
    serve((url) => json(200, page(Number(url.searchParams.get('page')), [], Number(url.searchParams.get('page')) + 1)));
    const first = renderHook(() => useWorkList({ queue: 'exceptions' }));
    await settled(first.result);
    expect(ready(first.result).more).toBe('keep-looking');
    expect(ready(first.result).items).toEqual([]);
    serve(() => json(200, page(1, [], null)));
    const second = renderHook(() => useWorkList({ queue: 'exceptions' }));
    await settled(second.result);
    expect(ready(second.result).more).toBe('done');
  });

  it('titles come from lines[]; a key it does not list shows as received', () => {
    const lines = [{ key: 'finance-ledger/v1', title: 'Finance ledger' }];
    expect(lineTitle(lines, 'finance-ledger/v1')).toBe('Finance ledger');
    expect(lineTitle(lines, 'pmo-minutes/v1')).toBe('pmo-minutes/v1');
  });

  it('a line filter or search restarts from page 1, sends line and q, and keeps the line choices of the unfiltered list', async () => {
    const lines = [{ key: 'finance-ledger/v1', title: 'Finance ledger' }, { key: 'pmo-minutes/v1', title: 'PMO minutes' }];
    serve((url) => json(200, page(1, [row(1)], 2, { lines: url.searchParams.has('line') ? [lines[0]] : lines })));
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    await act(() => result.current.loadMore());
    act(() => result.current.setFilters((f) => ({ ...f, line: 'finance-ledger/v1' })));
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('line')).toBe('finance-ledger/v1'));
    await settled(result);
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
    expect(ready(result).lineOptions).toEqual(lines);
    expect(ready(result).lines).toEqual([lines[0]]);
    act(() => result.current.setFilters((f) => ({ ...f, q: 'lagoon' })));
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('q')).toBe('lagoon'));
    await settled(result);
    expect(urls().at(-1)!.searchParams.get('line')).toBe('finance-ledger/v1');
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
  });

  it('a late answer from an earlier request does not replace newer rows', async () => {
    let releaseFirst: (response: Response) => void = () => undefined;
    serve((url) => (url.searchParams.has('q') ? json(200, page(1, [row(2, { title: 'New' })], null)) : new Promise<Response>((resolve) => (releaseFirst = resolve))));
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await waitFor(() => expect(fetchStub).toHaveBeenCalledTimes(1));
    act(() => result.current.setFilters({ q: 'new' }));
    await settled(result);
    expect(ready(result).items.map((r) => r.title)).toEqual(['New']);
    await act(async () => releaseFirst(json(200, page(1, [row(1, { title: 'Old' })], null))));
    expect(ready(result).items.map((r) => r.title)).toEqual(['New']);
  });

  it('a failed Show more keeps the rows and offers Try again; the next press asks the same page again', async () => {
    let fail = true;
    serve((url) => {
      if (url.searchParams.get('page') === '1') return json(200, page(1, [row(1)], 2));
      if (fail) return json(500, { code: 'server_error', message: 'Something went wrong.' });
      return json(200, page(2, [row(2)], null));
    });
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    await act(() => result.current.loadMore());
    expect(ready(result).more).toBe('failed');
    expect(ready(result).items.map((r) => r.id)).toEqual([1]);
    fail = false;
    await act(() => result.current.loadMore());
    expect(asked()).toEqual(['1', '2', '2']);
    expect(ready(result).items.map((r) => r.id)).toEqual([1, 2]);
  });

  it('errors: 401 unauthenticated, 403 forbidden, 400 bad_request and a network failure are typed; retry reloads', async () => {
    for (const [status, kind] of [[401, 'unauthenticated'], [403, 'forbidden'], [400, 'bad_request'], [422, 'invalid']] as const) {
      serve(() => json(status, { code: 'x', message: 'No.' }));
      const { result, unmount } = renderHook(() => useWorkList({ queue: 'exceptions' }));
      await settled(result);
      expect(result.current.state).toMatchObject({ status: 'error', error: { kind } });
      unmount();
    }
    serve(() => {
      throw new TypeError('offline');
    });
    const { result } = renderHook(() => useWorkList({ queue: 'exceptions' }));
    await settled(result);
    expect(result.current.state).toMatchObject({ status: 'error', error: { kind: 'network' } });
    serve(() => json(200, page(1, [row(1)], null)));
    await act(() => result.current.retry());
    expect(ready(result).items).toHaveLength(1);
  });

  it('never writes', async () => {
    serve(() => json(200, page(1, [row(1)], 2)));
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    await act(() => result.current.loadMore());
    expect(fetchStub.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
  });
});

describe('coverage and labels', () => {
  const base = { limited: false, evaluated: 24, deferredCount: 0 };
  it('as-of always; the incomplete and still-being-checked lines only when they apply; never a total', () => {
    expect(coverageNotes(base, '2026-11-23T11:00:00Z')).toEqual(['As of 23 Nov 12:00']);
    expect(coverageNotes({ ...base, limited: true, deferredCount: 1 }, '2026-11-23T11:00:00Z')).toEqual([
      'As of 23 Nov 12:00',
      'This list may be incomplete. Some work could not be checked yet.',
      '1 more item is still being checked.',
    ]);
    expect(coverageNotes({ ...base, deferredCount: 3 }, '2026-11-23T11:00:00Z')[1]).toBe('3 more items are still being checked.');
    expect(coverageNotes({ ...base, deferredCount: 8 }, '2026-11-23T11:00:00Z')[1]).toBe('8 or more items are still being checked.');
    expect(coverageNotes({ ...base, limited: true, deferredCount: 8 }, '2026-11-23T11:00:00Z').slice(1).join(' ')).not.toMatch(/ of |evaluated|24/);
  });
  it('the count says so far while more pages exist', () => {
    expect(shownText(8, 'idle')).toBe('8 shown so far');
    expect(shownText(8, 'keep-looking')).toBe('8 shown so far');
    expect(shownText(3, 'done')).toBe('3 shown');
  });
  it('every live state has its own tag', () => {
    expect(stateTag('action_needed').text).toBe('Action needed');
    expect(stateTag('awaiting_reconciliation').text).toBe('Awaiting reconciliation');
    expect(stateTag('effect_uncertain').text).toBe('Effect uncertain');
    expect(stateTag('ready').text).toBe('Ready to continue');
  });
});

describe('useWorkList: rows per page, state, totals and refresh (F-63)', () => {
  it('sends no limit or state unless asked (Verified and Exceptions are unchanged)', async () => {
    serve(() => json(200, page(1, [row(1)], null)));
    const { result } = renderHook(() => useWorkList({ queue: 'verified' }));
    await settled(result);
    expect([...urls()[0].searchParams.keys()].sort()).toEqual(['page', 'queue']);
  });

  it('sends limit and state, and a change of either restarts from page 1', async () => {
    serve(() => json(200, page(1, [row(1)], 2)));
    const { result, rerender } = renderHook((props: { limit?: 10 | 20; state?: 'waiting' }) => useWorkList({ queue: 'needs_me', ...props }), { initialProps: { limit: 10 } });
    await settled(result);
    await act(() => result.current.loadMore());
    expect(asked()).toEqual(['1', '2']);
    expect(urls()[0].searchParams.get('limit')).toBe('10');
    rerender({ limit: 20 });
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('limit')).toBe('20'));
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
    rerender({ limit: 20, state: 'waiting' });
    await waitFor(() => expect(urls().at(-1)!.searchParams.get('state')).toBe('waiting'));
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
    expect(urls().at(-1)!.searchParams.get('limit')).toBe('20');
  });

  it('answers to an earlier limit are dropped', async () => {
    let first: (r: Response) => void = () => undefined;
    serve((url) => (url.searchParams.get('limit') === '20' ? json(200, page(1, [row(2)], null)) : new Promise<Response>((resolve) => (first = resolve))));
    const { result, rerender } = renderHook((props: { limit: 10 | 20 }) => useWorkList({ queue: 'needs_me', ...props }), { initialProps: { limit: 10 } });
    rerender({ limit: 20 });
    await waitFor(() => expect(ready(result).items.map((r) => r.id)).toEqual([2]));
    await act(async () => first(json(200, page(1, [row(1)], null))));
    expect(ready(result).items.map((r) => r.id)).toEqual([2]);
  });

  it('total is exact only when the server marks it complete', async () => {
    serve(() => json(200, page(1, [row(1)], null, { total: 24, total_coverage: 'complete', page_size: 10 })));
    const complete = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(complete.result);
    expect([ready(complete.result).total, ready(complete.result).totalComplete, ready(complete.result).pageSize]).toEqual([24, true, 10]);
    serve(() => json(200, page(1, [row(1)], null, { total: 24, total_coverage: 'incomplete' })));
    const incomplete = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(incomplete.result);
    expect(ready(incomplete.result).totalComplete).toBe(false);
    serve(() => json(200, page(1, [row(1)], null, { total: null, total_coverage: 'complete' })));
    const none = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(none.result);
    expect([ready(none.result).total, ready(none.result).totalComplete]).toEqual([null, false]);
  });

  it('refresh re-reads page 1, keeps rows loaded later and drops ids now on page 1', async () => {
    let round = 0;
    serve((url) => {
      const n = Number(url.searchParams.get('page'));
      if (n === 2) return json(200, page(2, [row(3), row(4)], null));
      return json(200, round === 0 ? page(1, [row(1), row(2)], 2) : page(1, [row(9), row(3)], 2, { as_of: '2026-11-23T11:15:00Z' }));
    });
    const { result } = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(result);
    await act(() => result.current.loadMore());
    expect(ready(result).items.map((r) => r.id)).toEqual([1, 2, 3, 4]);
    round = 1;
    let ok = false;
    await act(async () => {
      ok = await result.current.refresh();
    });
    expect(ok).toBe(true);
    expect(ready(result).items.map((r) => r.id)).toEqual([9, 3, 4]);
    expect(ready(result).asOf).toBe('2026-11-23T11:15:00Z');
    expect(urls().at(-1)!.searchParams.get('page')).toBe('1');
  });

  it('a failed refresh keeps the rows and answers false; a 401 signs out', async () => {
    let fail: Response | undefined;
    serve(() => fail ?? json(200, page(1, [row(1)], null)));
    const { result } = renderHook(() => useWorkList({ queue: 'needs_me' }));
    await settled(result);
    fail = json(500, { code: 'server_error', message: 'x' });
    let ok = true;
    await act(async () => {
      ok = await result.current.refresh();
    });
    expect(ok).toBe(false);
    expect(ready(result).items.map((r) => r.id)).toEqual([1]);
    fail = json(401, { code: 'not_signed_in', message: 'x' });
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.state.status).toBe('error');
  });

  it('a list that is not enabled asks for nothing', async () => {
    serve(() => json(200, page(1, [row(1)], null)));
    const { result } = renderHook(() => useWorkList({ queue: 'unassigned', enabled: false }));
    await act(async () => {
      await result.current.refresh();
    });
    expect(urls()).toEqual([]);
  });

  it('mergeRefresh puts page 1 first and keeps later rows once', () => {
    const items = [row(1), row(2), row(3), row(4)];
    expect(mergeRefresh(items, 2, [row(3), row(8)]).map((r) => r.id)).toEqual([3, 8, 4]);
  });
});

describe('useWorkCounts (F-63)', () => {
  const body = { as_of: '2026-11-24T09:42:00Z', evaluated: 3, limited: false, verified_month: '2026-11', queues: [{ key: 'needs_me', observed: 3, total: 3 }], lines: [] };

  it('reads /work/counts with no parameters and keeps the numbers when a refresh fails', async () => {
    let fail = false;
    serve(() => (fail ? json(500, { code: 'server_error', message: 'x' }) : json(200, body)));
    const { result } = renderHook(() => useWorkCounts());
    await waitFor(() => expect(result.current.state.status).toBe('ready'));
    expect(urls()[0].pathname).toBe('/api/v1/work/counts');
    expect([...urls()[0].searchParams.keys()]).toEqual([]);
    fail = true;
    let ok = true;
    await act(async () => {
      ok = await result.current.refresh();
    });
    expect(ok).toBe(false);
    expect(result.current.state.status).toBe('ready');
  });

  it('a first read that fails is an error', async () => {
    serve(() => json(500, { code: 'server_error', message: 'x' }));
    const { result } = renderHook(() => useWorkCounts());
    await waitFor(() => expect(result.current.state.status).toBe('error'));
  });
});
