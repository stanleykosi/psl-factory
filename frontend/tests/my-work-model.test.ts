import { describe, expect, it } from 'vitest';

import {
  filterCount,
  formatAge,
  isNarrowed,
  LINE_KEYS,
  miniSegments,
  parseView,
  QUEUES,
  recordsText,
  resultCount,
  showUnassigned,
  startAge,
  stationText,
  tabCount,
  viewSearch,
  type View,
} from '@/features/my-work/model';
import type { WorkCounts } from '@/features/work-list';

import { row } from './work-list-rows';

const parse = (search: string) => parseView(new URLSearchParams(search));
const PROJECT = '7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11';
const station = (index: number, count = 5) => ({ key: 'execution' as const, index, count, name: 'Approval' });

describe('queues', () => {
  it('lists the eight tabs in order with their live queue values', () => {
    expect(QUEUES.map((x) => x.key)).toEqual(['needs_me', 'waiting', 'mine', 'active', 'decisions', 'exceptions', 'unassigned', 'verified']);
    expect(QUEUES.map((x) => x.label)).toEqual(['Needs me', 'Waiting on others', 'Started by me', 'Active', 'Decisions', 'Exceptions', 'Unassigned', 'Verified']);
  });
});

describe('parseView (acceptance 2, 7, 17)', () => {
  it('defaults to Needs me, ten rows and no filters', () => {
    expect(parse('')).toEqual({ queue: 'needs_me', q: undefined, line: undefined, project: undefined, state: undefined, limit: 10 });
  });

  it.each(['done', 'waiting_on_others', 'nope', 'NEEDS_ME', ' waiting', 'waiting%00'])('drops the queue %j', (queue) => {
    expect(parse(`queue=${queue}`).queue).toBe('needs_me');
  });

  it.each(LINE_KEYS)('keeps the line key %s', (line) => {
    expect(parse(`line=${line}`).line).toBe(line);
  });

  it.each(['nope', '', 'Finance-Ledger/v1', 'finance-ledger/v1 ', 'finance-ledger', '../finance-ledger/v1', 'finance-ledger/v2'])('drops the line %j', (line) => {
    expect(parse(new URLSearchParams({ line }).toString()).line).toBeUndefined();
  });

  it.each(['not-a-uuid', '', PROJECT.slice(1), `${PROJECT} `, ` ${PROJECT}`, `${PROJECT}/..`, `https://x/${PROJECT}`, `//${PROJECT}`, 'C-LAGOON-HEALTH', '%2e%2e'])('drops the project %j', (project) => {
    expect(parse(new URLSearchParams({ project }).toString()).project).toBeUndefined();
  });

  it('keeps a uuid project in either case', () => {
    expect(parse(`project=${PROJECT}`).project).toBe(PROJECT);
    expect(parse(`project=${PROJECT.toUpperCase()}`).project).toBe(PROJECT.toUpperCase());
  });

  it.each(['nope', '', 'WAITING', 'verified ', 'awaiting_finance_decision'])('drops the state %j', (state) => {
    expect(parse(new URLSearchParams({ state }).toString()).state).toBeUndefined();
  });

  it('keeps each of the 11 states', () => {
    for (const state of ['ready', 'processing', 'waiting', 'owner_needed', 'setup_needed', 'action_needed', 'effect_uncertain', 'awaiting_reconciliation', 'verified', 'cancelled', 'followup_needed']) {
      expect(parse(`state=${state}`).state).toBe(state);
    }
  });

  it.each(['8', '15', '0', '-10', '100', '10.0', '', 'abc', '2e1'])('drops the limit %j', (limit) => {
    expect(parse(`limit=${limit}`).limit).toBe(10);
  });

  it('keeps 20 and 50', () => {
    expect(parse('limit=20').limit).toBe(20);
    expect(parse('limit=50').limit).toBe(50);
  });

  it('trims the search and cuts it to 120 characters', () => {
    expect(parse('q=%20%20lagoon%20').q).toBe('lagoon');
    expect(parse(`q=${'a'.repeat(130)}`).q).toBe('a'.repeat(120));
    expect(parse('q=%20%20').q).toBeUndefined();
  });

  it('never reads the old parameters', () => {
    const view = parse('waiting_on=agent&cursor=o10&assign=W-1&counts=1');
    expect(Object.keys(view).sort()).toEqual(['limit', 'line', 'project', 'q', 'queue', 'state']);
  });
});

describe('viewSearch', () => {
  const base: View = { queue: 'needs_me', limit: 10 };

  it('leaves the defaults out', () => {
    expect(viewSearch(base)).toBe('');
  });

  it('writes what differs, once', () => {
    expect(viewSearch({ ...base, queue: 'verified', limit: 20, state: 'ready', line: 'finance-ledger/v1', project: PROJECT, q: 'lagoon' })).toBe(
      `?queue=verified&q=lagoon&line=finance-ledger%2Fv1&project=${PROJECT}&state=ready&limit=20`,
    );
  });

  it('round-trips through parseView', () => {
    const view: View = { queue: 'mine', q: 'a b', line: 'pmo-minutes/v1', project: PROJECT, state: 'waiting', limit: 50 };
    expect(parse(viewSearch(view))).toEqual(view);
  });
});

describe('filters', () => {
  it('counts line, project and state, not the search', () => {
    expect(filterCount({ queue: 'needs_me', limit: 10, q: 'x' })).toBe(0);
    expect(filterCount({ queue: 'needs_me', limit: 10, state: 'ready', project: PROJECT })).toBe(2);
    expect(isNarrowed({ queue: 'needs_me', limit: 10, q: 'x' })).toBe(true);
    expect(isNarrowed({ queue: 'needs_me', limit: 10 })).toBe(false);
  });
});

const counts = (queues: WorkCounts['queues'], over: Partial<WorkCounts> = {}): WorkCounts => ({ as_of: '2026-11-24T09:42:00Z', evaluated: 5, limited: false, verified_month: '2026-11', queues, lines: [], ...over });

describe('tabCount (acceptance 5)', () => {
  it('shows the total, "at least" the observed count, nothing when unknown, and a real 0', () => {
    const c = counts([
      { key: 'needs_me', observed: 3, total: 3 },
      { key: 'waiting', observed: 2, total: null },
      { key: 'mine', observed: 0, total: null },
      { key: 'decisions', observed: 0, total: 0 },
    ]);
    expect(tabCount(c, 'needs_me')).toEqual({ count: 3, atLeast: false });
    expect(tabCount(c, 'waiting')).toEqual({ count: 2, atLeast: true });
    expect(tabCount(c, 'mine')).toBeUndefined();
    expect(tabCount(c, 'decisions')).toEqual({ count: 0, atLeast: false });
    expect(tabCount(c, 'active')).toBeUndefined();
    expect(tabCount(undefined, 'needs_me')).toBeUndefined();
  });
});

describe('showUnassigned (acceptance 18)', () => {
  it('draws the tab for a count above zero, an observed count, or an address that names it', () => {
    expect(showUnassigned(counts([{ key: 'unassigned', observed: 0, total: 2 }]), 'needs_me')).toBe(true);
    expect(showUnassigned(counts([{ key: 'unassigned', observed: 1, total: null }]), 'needs_me')).toBe(true);
    expect(showUnassigned(counts([{ key: 'unassigned', observed: 0, total: 0 }]), 'needs_me')).toBe(false);
    expect(showUnassigned(counts([]), 'needs_me')).toBe(false);
    expect(showUnassigned(undefined, 'needs_me')).toBe(false);
    expect(showUnassigned(undefined, 'unassigned')).toBe(true);
  });
});

describe('recordsText (acceptance 6)', () => {
  const line = (open: number) => ({ key: 'finance-ledger/v1' as const, needs_person: 0, held: 0, open, stopped: 0, verified: 0, verified_this_month: 0, stations: [] });
  it('adds the open records of every line', () => {
    expect(recordsText(counts([], { lines: [line(3), line(4)] }))).toBe('7 open records you can see');
    expect(recordsText(counts([], { lines: [line(1)] }))).toBe('1 open record you can see');
  });
  it('says "at least" when limited, and is absent without counts', () => {
    expect(recordsText(counts([], { limited: true, lines: [line(3), line(4)] }))).toBe('at least 7 open records you can see');
    expect(recordsText(undefined)).toBeUndefined();
  });
});

describe('ages and times', () => {
  it('writes minutes, hours and days', () => {
    expect(formatAge(30)).toBe('1m');
    expect(formatAge(59 * 60)).toBe('59m');
    expect(formatAge(7200)).toBe('2h');
    expect(formatAge(3 * 86400)).toBe('3d');
  });

  it('measures the start age to the list clock, not the browser clock', () => {
    expect(startAge(row(1, { started_at: '2026-11-24T07:00:00Z' }), '2026-11-24T09:42:00Z')).toBe('2h');
    expect(startAge(row(1, { started_at: '2026-11-24T10:00:00Z' }), '2026-11-24T09:42:00Z')).toBe('1m');
  });
});

describe('station bar', () => {
  it('marks done, current by who holds it, and to-do', () => {
    expect(miniSegments(station(3), 'action_needed')).toEqual(['d', 'd', 'p', '', '']);
    expect(miniSegments(station(2), 'processing')).toEqual(['d', 'a', '', '', '']);
    expect(miniSegments(station(2), 'waiting')).toEqual(['d', 'w', '', '', '']);
    expect(miniSegments(station(2), 'ready')).toEqual(['d', 'p', '', '', '']);
    expect(miniSegments(station(2), 'followup_needed')).toEqual(['d', 's', '', '', '']);
    expect(miniSegments(station(2), 'cancelled')).toEqual(['d', '', '', '', '']);
    expect(miniSegments(station(5), 'verified')).toEqual(['d', 'd', 'd', 'd', 'v']);
  });

  it('writes the station in words', () => {
    expect(stationText(station(3), 'action_needed')).toBe('Station 3 of 5 · Approval');
    expect(stationText(station(5), 'verified')).toBe('All 5 stations done');
  });
});

describe('resultCount (acceptance 11)', () => {
  it('is exact only when the server marks the total complete', () => {
    expect(resultCount(10, true, 24, true)).toBe('10 OF 24 ITEMS');
    expect(resultCount(24, false, 24, true)).toBe('24 ITEMS');
    expect(resultCount(10, true, null, false)).toBe('10+ ITEMS');
    expect(resultCount(10, false, null, false)).toBe('10 ITEMS');
    expect(resultCount(10, true, 40, false)).toBe('10+ ITEMS');
  });
});
