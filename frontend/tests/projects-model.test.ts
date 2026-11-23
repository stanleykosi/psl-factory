import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  buildProjectsQuery,
  clientOf,
  countOf,
  factText,
  isJourney,
  isProjectList,
  MAX_Q,
  parseProjectsView,
  projectCounts,
  projectsSearch,
  routeCaseId,
  shownText,
  visibleTabs,
  whereText,
} from '@/features/projects/model';

const view = (search: string) => parseProjectsView(new URLSearchParams(search));

describe('projects view and query', () => {
  it('reads q and the tab from the URL; an empty q or an unknown status fall back, and an old limit is ignored', () => {
    expect(view('')).toEqual({ q: undefined, tab: 'active' });
    expect(view('q=lagoon&limit=20')).toEqual({ q: 'lagoon', tab: 'active' });
    expect(view('q=%20%20&limit=7')).toEqual({ q: undefined, tab: 'active' });
    expect(view('limit=50&status=closed')).toEqual({ q: undefined, tab: 'closed' });
    expect(view('status=all')).toEqual({ q: undefined, tab: 'all' });
    expect(view('status=open')).toEqual({ q: undefined, tab: 'active' });
  });

  it('writes status only when not Active and q only when set; never a cursor or a limit', () => {
    expect(projectsSearch({ tab: 'active' })).toBe('');
    expect(projectsSearch({ q: 'lagoon', tab: 'active' })).toBe('?q=lagoon');
    expect(projectsSearch({ q: 'a b', tab: 'all' })).toBe('?status=all&q=a+b');
    expect(projectsSearch({ tab: 'closed' })).toBe('?status=closed');
  });

  it('always sends status (the live default is All), q only with text, trimmed and at most 120 long, the cursor only when given, and no limit', () => {
    expect(buildProjectsQuery({ tab: 'active' })).toEqual({ status: 'active' });
    expect(buildProjectsQuery({ q: '  ', tab: 'all' })).toEqual({ status: 'all' });
    expect(buildProjectsQuery({ q: ' lagoon ', tab: 'closed' }, 'o20')).toEqual({ status: 'closed', q: 'lagoon', cursor: 'o20' });
    for (const query of [buildProjectsQuery({ q: 'x'.repeat(200), tab: 'active' }), buildProjectsQuery(view(`q=${'y'.repeat(300)}`))]) {
      expect(query.q?.length).toBeLessThanOrEqual(MAX_Q);
      expect(query).not.toHaveProperty('limit');
    }
    // a cut that lands on a space does not leave a trailing one
    expect(buildProjectsQuery({ q: `${'a'.repeat(119)} b`, tab: 'active' }).q).toBe('a'.repeat(119));
  });

  it('names the client from the title, and decodes the route segment once', () => {
    expect(clientOf('Lagoon Health · patient app')).toBe('Lagoon Health');
    expect(clientOf('Standalone fit-out')).toBeUndefined();
    expect(clientOf(' · odd')).toBeUndefined();
    expect(routeCaseId('P%2F..%3Cb%3E')).toBe('P/..<b>');
    expect(routeCaseId('P-0101')).toBe('P-0101');
    expect(routeCaseId('%E0%A4%A')).toBe('%E0%A4%A');
  });

  it('says where it is from phase, then lifecycle, then Unknown; and counts loaded rows only', () => {
    expect(whereText({ phase: 'Release · UAT with client', lifecycle: 'active' })).toBe('Release · UAT with client');
    expect(whereText({ phase: null, lifecycle: 'active' })).toBe('active');
    expect(whereText({ phase: null, lifecycle: null })).toBe('Unknown');
    expect(shownText(20, true)).toBe('20 shown, more available');
    expect(shownText(5, false)).toBe('5 shown');
  });
});

describe('values the response may not carry', () => {
  it('a null figure reads Not available and never 0; a real 0 reads 0', () => {
    expect(factText(null)).toBe('Not available');
    expect(factText(undefined)).toBe('Not available');
    expect(factText('')).toBe('Not available');
    expect(factText(Number.NaN)).toBe('Not available');
    expect(factText(0)).toBe('0');
    expect(factText(4)).toBe('4');
    expect(factText('UAT sign-off')).toBe('UAT sign-off');
    expect([countOf(0), countOf(4), countOf(null), countOf(-1), countOf(1.5), countOf('2')]).toEqual([0, 4, undefined, undefined, undefined, undefined]);
  });

  it('counts come from the whole project facts', () => {
    const journey = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/P-0101.json'), 'utf8'));
    expect(projectCounts(journey)).toEqual({ pieces: 8, waiting: 2, stopped: 1 });
  });
});

describe('tabs', () => {
  it('keeps the keys the frontend routes, in the returned order; Delivery and unrouted keys never show', () => {
    const keys = (list: string[]) => visibleTabs(list.map((key) => ({ key }))).map((t) => t.key);
    expect(keys(['journey', 'milestones', 'documents', 'templates', 'money', 'month-end', 'registers', 'actions', 'hr'])).toEqual(['journey', 'milestones', 'documents', 'money', 'registers', 'actions']);
    expect(keys(['actions', 'journey', 'delivery'])).toEqual(['actions', 'journey']);
    expect(keys(['journey', 'milestones'])).toEqual(['journey', 'milestones']);
    expect(keys([])).toEqual([]);
  });
});

describe('response checks', () => {
  const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
  const journey = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/P-0101.json'), 'utf8'));
  const list = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/list.json'), 'utf8'));

  it('accepts the live bodies and refuses others, such as the /me body', () => {
    expect(isProjectList({ items: list.rows.map((r: { item: unknown }) => r.item), next_cursor: null, as_of: list.as_of })).toBe(true);
    expect(isProjectList({ items: [], next_cursor: null, as_of: '2026-11-23T09:00:00Z' })).toBe(true);
    expect(isJourney(journey)).toBe(true);
    expect(isJourney({ ...journey, items: [] })).toBe(true);
    for (const body of [me, null, 'text', [], { items: 'x' }, { items: [{}] }]) expect(isProjectList(body)).toBe(false);
    for (const body of [me, null, { items: [] }, { ...journey, items: undefined }, { ...journey, title: '' }, { ...journey, facts: undefined }]) expect(isJourney(body)).toBe(false);
  });
});
