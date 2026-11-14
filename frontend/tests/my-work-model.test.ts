import { describe, expect, it } from 'vitest';

import {
  buildWorkQuery,
  formatAge,
  lineOptions,
  mergeRefresh,
  miniSegments,
  parseView,
  resultCount,
  shownText,
  showMoreLabel,
  stateTag,
  STATE_KEYS,
  STATES,
  stationText,
  viewSearch,
  type View,
  type WorkItem,
} from '@/features/my-work/model';

const view = (v: Partial<View> = {}): View => ({ queue: 'needs_me', limit: 20, ...v });
const item = (id: string, extra: Partial<WorkItem> = {}): WorkItem => ({
  id,
  title: id,
  line: 'Prepare an invoice',
  reference: 'R',
  kind: 'do',
  state: 'ready',
  station: { index: 1, count: 3, name: 'S' },
  waiting_on: 'X',
  age_seconds: 60,
  sample: true,
  ...extra,
});

describe('state words and families (CMP-05)', () => {
  it.each([
    ['ready', 'Ready to continue', 'person'],
    ['processing', 'Processing', 'agent'],
    ['waiting', 'Waiting', 'waiting'],
    ['owner_needed', 'Owner needed', 'person'],
    ['setup_needed', 'Setup needed', 'person'],
    ['action_needed', 'Action needed', 'person'],
    ['effect_uncertain', 'Effect uncertain', 'person'],
    ['awaiting_reconciliation', 'Awaiting reconciliation', 'waiting'],
    ['verified', 'Verified', 'done'],
    ['cancelled', 'Cancelled', 'neutral'],
    ['followup_needed', 'Stopped: invoice follow-up needed', 'person'],
  ])('%s → %s (%s)', (state, words, family) => {
    expect(stateTag(state)).toEqual({ words, family });
  });

  it('covers the 11 contract states in order; an unknown state shows raw and neutral', () => {
    expect(STATE_KEYS).toHaveLength(11);
    expect(Object.keys(STATES)).toEqual(STATE_KEYS);
    expect(stateTag('on_hold')).toEqual({ words: 'on_hold', family: 'neutral' });
    expect(stateTag('toString')).toEqual({ words: 'toString', family: 'neutral' });
  });
});

describe('mini station bar (CMP-03) and age', () => {
  it('waiting at 4 of 7: three done, the fourth w, then empty', () => {
    expect(miniSegments({ index: 4, count: 7, name: 'Finance review' }, 'waiting')).toEqual(['d', 'd', 'd', 'w', '', '', '']);
    expect(stationText({ index: 4, count: 7, name: 'Finance review' }, 'waiting')).toBe('Station 4 of 7 · Finance review');
  });

  it('maps the current segment by family; followup is s, cancelled has none, verified is all done then v', () => {
    const s = { index: 2, count: 3, name: 'N' };
    expect(miniSegments(s, 'action_needed')[1]).toBe('p');
    expect(miniSegments(s, 'processing')[1]).toBe('a');
    expect(miniSegments(s, 'awaiting_reconciliation')[1]).toBe('w');
    expect(miniSegments(s, 'followup_needed')[1]).toBe('s');
    expect(miniSegments(s, 'cancelled')).toEqual(['d', '', '']);
    expect(miniSegments({ index: 4, count: 4, name: 'Verified' }, 'verified')).toEqual(['d', 'd', 'd', 'v']);
    expect(stationText({ index: 4, count: 4, name: 'Verified' }, 'verified')).toBe('All 4 stations done');
  });

  it.each([
    [0, '1m'],
    [30, '1m'],
    [3599, '59m'],
    [3600, '1h'],
    [7200, '2h'],
    [86399, '23h'],
    [86400, '1d'],
    [691200, '8d'],
  ])('%i seconds → %s', (s, text) => expect(formatAge(s)).toBe(text));
});

describe('view and query', () => {
  it('reads the URL, falling back on invalid values', () => {
    expect(parseView(new URLSearchParams('queue=done&q=lagoon&state=verified&limit=50&line=X'))).toEqual({
      queue: 'done',
      q: 'lagoon',
      line: 'X',
      state: 'verified',
      limit: 50,
    });
    expect(parseView(new URLSearchParams('queue=bogus&limit=7&state=nope&q=%20%20'))).toEqual(view());
  });

  it('builds the query: queue and limit always, q trimmed and never empty, cursor only when given', () => {
    expect(buildWorkQuery(view())).toEqual({ queue: 'needs_me', limit: 20 });
    expect(buildWorkQuery(view({ q: '  ' }))).toEqual({ queue: 'needs_me', limit: 20 });
    expect(buildWorkQuery(view({ q: ' lagoon ', line: 'L', state: 'waiting', limit: 10 }), 'o10')).toEqual({
      queue: 'needs_me',
      limit: 10,
      q: 'lagoon',
      line: 'L',
      state: 'waiting',
      cursor: 'o10',
    });
  });

  it('writes the URL without defaults', () => {
    expect(viewSearch(view())).toBe('');
    expect(viewSearch(view({ queue: 'done', limit: 10, line: 'Prepare an invoice' }))).toBe('?queue=done&line=Prepare+an+invoice&limit=10');
  });
});

describe('counts, footer and merging', () => {
  const counts = { needs_me: 24, waiting_on_others: 12, done: 6 };

  it('result count', () => {
    expect(resultCount(view(), counts, 20, true)).toBe('24 ITEMS');
    expect(resultCount(view({ q: 'x' }), counts, 2, false)).toBe('2 OF 24 ITEMS');
    expect(resultCount(view({ state: 'ready' }), counts, 20, true)).toBe('20+ OF 24 ITEMS');
    expect(resultCount(view(), null, 20, true)).toBe('20+ ITEMS');
    expect(resultCount(view(), null, 3, false)).toBe('3 ITEMS');
  });

  it('shown text and Show more label', () => {
    expect(shownText(view(), counts, 20, true)).toBe('20 of 24 showing');
    expect(shownText(view(), counts, 24, false)).toBe('All 24 showing');
    expect(shownText(view({ q: 'x' }), counts, 20, true)).toBe('20 showing');
    expect(showMoreLabel(view(), counts, 20)).toBe('Show 4 more');
    expect(showMoreLabel(view({ limit: 10 }), counts, 10)).toBe('Show 10 more');
    expect(showMoreLabel(view({ q: 'x' }), counts, 10)).toBe('Show more');
  });

  it('line options are distinct, include the applied line and sort A–Z', () => {
    expect(lineOptions([item('a', { line: 'B' }), item('b', { line: 'A' }), item('c', { line: 'B' })], 'C')).toEqual(['A', 'B', 'C']);
  });

  it('a refresh replaces page 1 and keeps later rows not now on page 1', () => {
    const loaded = [item('1'), item('2'), item('3'), item('4')];
    expect(mergeRefresh(loaded, 2, [item('1', { state: 'verified' }), item('3')]).map((i) => [i.id, i.state])).toEqual([
      ['1', 'verified'],
      ['3', 'ready'],
      ['4', 'ready'],
    ]);
  });
});
