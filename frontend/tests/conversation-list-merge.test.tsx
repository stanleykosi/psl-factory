// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useConversationList } from '@/features/assistant/useConversationList';

const row = (n: number) => ({ conversation_id: `CV-${n}`, title: `Chat ${n}`, agent: 'tola', status: 'idle', updated_at: '2026-11-14T09:00:00Z' });
const reply = (items: unknown[], next?: string) =>
  new Response(JSON.stringify({ items, as_of: '2026-11-14T10:00:00Z', ...(next ? { next_cursor: next } : {}) }), { status: 200, headers: { 'content-type': 'application/json' } });

afterEach(() => vi.unstubAllGlobals());

describe('conversation list refresh (TECH-1-1)', () => {
  it('keeps the pages already loaded, merges page 1 at the top and keeps the cursor', async () => {
    let first = [row(0), row(1), row(2)];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (request: Request) => {
        const url = new URL(request.url);
        if (url.searchParams.get('cursor') === 'o3') return reply([row(3), row(4)], 'o5');
        return reply(first, 'o3');
      }),
    );
    const { result } = renderHook(() => useConversationList());
    await waitFor(() => expect(result.current.state.status).toBe('ready'));
    await act(async () => {
      await result.current.more(10);
    });
    await waitFor(() => expect(result.current.state.status === 'ready' && result.current.state.items.length).toBe(5));
    // a send moved Chat 2 to the top and added a new Chat 9
    first = [row(9), row(2), row(0)];
    await act(async () => {
      await result.current.refresh();
    });
    const state = result.current.state;
    if (state.status !== 'ready') throw new Error('not ready');
    expect(state.items.map((r) => r.conversation_id)).toEqual(['CV-9', 'CV-2', 'CV-0', 'CV-1', 'CV-3', 'CV-4']);
    expect(state.next).toBe('o5');
  });

  it('with only page 1 loaded, a refresh takes the new first page and its cursor', async () => {
    let first = [row(0)];
    let next = 'o1';
    vi.stubGlobal('fetch', vi.fn(async () => reply(first, next)));
    const { result } = renderHook(() => useConversationList());
    await waitFor(() => expect(result.current.state.status).toBe('ready'));
    first = [row(7), row(0)];
    next = 'o2';
    await act(async () => {
      await result.current.refresh();
    });
    const state = result.current.state;
    if (state.status !== 'ready') throw new Error('not ready');
    expect(state.items).toHaveLength(2);
    expect(state.next).toBe('o2');
  });
});
