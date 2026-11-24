import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { isLiveWorkRequest, liveWorkCounts, liveWorkList } from '../mock/live-work.mjs';

// The live work list and counts in the mock (F-63): all eight queues, limit, state and total; v7 callers are left alone.
const url = (search: string) => new URL(`http://mock/api/v1/work?${search}`);
const list = (search: string, persona = 'finance_lead', dataset?: string) => liveWorkList({ url: url(search), persona, dataset }) as { status: number; body: any };
const counts = (persona = 'finance_lead', dataset?: string) => liveWorkCounts({ persona, dataset }).body as any;

describe('which requests are live', () => {
  it('takes live-only queues and any request with page; leaves the decision desk read to v7', () => {
    expect(isLiveWorkRequest(url('queue=needs_me&page=1'))).toBe(true);
    expect(isLiveWorkRequest(url('queue=waiting'))).toBe(true);
    expect(isLiveWorkRequest(url('queue=needs_me&limit=50'))).toBe(false);
    expect(isLiveWorkRequest(url('queue=unassigned'))).toBe(false);
    expect(isLiveWorkRequest(url('queue=done'))).toBe(false);
  });
});

describe('liveWorkList', () => {
  it.each(['needs_me', 'waiting', 'mine', 'active', 'decisions', 'exceptions', 'unassigned', 'verified'])('serves the live row shape for %s', (queue) => {
    const { status, body } = list(`queue=${queue}&page=1&limit=10`);
    expect(status).toBe(200);
    expect(body.page_size).toBe(10);
    for (const row of body.items) {
      expect(typeof row.id).toBe('number');
      expect(row).toHaveProperty('action_kind');
      expect(row).toHaveProperty('station');
      expect(row).toHaveProperty('started_at');
    }
  });

  it('counts exactly and completely for the persona queues; verified and exceptions are not totalled', () => {
    const needs = list('queue=needs_me&page=1&limit=10').body;
    expect([needs.items.length, needs.total, needs.total_coverage, needs.next_page]).toEqual([10, 24, 'complete', 2]);
    expect(list('queue=verified&page=1').body.total).toBeNull();
  });

  it('limit sets the page size and state narrows', () => {
    expect(list('queue=needs_me&page=1&limit=20').body.items).toHaveLength(20);
    const waiting = list('queue=needs_me&page=1&limit=50&state=waiting').body;
    expect(waiting.items.every((r: any) => r.state === 'waiting')).toBe(true);
  });

  it('refuses what the contract refuses', () => {
    expect(list('queue=nope&page=1').status).toBe(400);
    expect(list('queue=needs_me&page=1&limit=12').status).toBe(400);
    expect(list('queue=needs_me&page=1&state=nope').status).toBe(400);
    expect(list('queue=needs_me&page=0').status).toBe(400);
    expect(list('queue=exceptions&page=1', 'pm').status).toBe(403);
    expect(list('queue=unassigned&page=1', 'pm').status).toBe(403);
  });

  it('the persona with no work gets empty pages', () => {
    expect(list('queue=needs_me&page=1', 'none').body.items).toEqual([]);
  });

  it('can serve an empty middle page with a next_page after it', () => {
    const body = list('queue=needs_me&page=1&limit=8&state=effect_uncertain').body;
    expect(body.next_page).not.toBeNull();
  });
});

describe('liveWorkCounts', () => {
  it('lists every queue with observed and total, and per-line summaries', () => {
    const body = counts();
    expect(body.queues.map((q: any) => q.key)).toEqual(['needs_me', 'waiting', 'mine', 'active', 'decisions', 'exceptions', 'unassigned', 'verified']);
    expect(body.queues.find((q: any) => q.key === 'exceptions')).toMatchObject({ observed: 20, total: null });
    expect(body.lines[0]).toHaveProperty('open');
  });

  it('leaves Unassigned out for people who cannot see it, and everything at 0 for the persona with no work', () => {
    expect(counts('pm').queues.map((q: any) => q.key)).not.toContain('unassigned');
    expect(counts('none').queues.every((q: any) => q.total === 0 && q.observed === 0)).toBe(true);
  });

  it('the board dataset carries the board counts', () => {
    expect(counts('finance_lead', 'board').queues.find((q: any) => q.key === 'verified').total).toBe(28);
  });
});
