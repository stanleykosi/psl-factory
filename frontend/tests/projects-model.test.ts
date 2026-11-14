import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  buildProjectsQuery,
  clientOf,
  isJourney,
  isProjectList,
  parseProjectsView,
  projectsSearch,
  routeCaseId,
  workCounts,
} from '@/features/projects/model';

const view = (search: string) => parseProjectsView(new URLSearchParams(search));

describe('projects view and query', () => {
  it('reads q, limit and the tab from the URL; an empty q, an invalid limit or an unknown status fall back to the defaults', () => {
    expect(view('')).toEqual({ q: undefined, limit: 20, tab: 'active' });
    expect(view('q=lagoon&limit=10')).toEqual({ q: 'lagoon', limit: 10, tab: 'active' });
    expect(view('q=%20%20&limit=7')).toEqual({ q: undefined, limit: 20, tab: 'active' });
    expect(view('limit=50&status=closed')).toEqual({ q: undefined, limit: 50, tab: 'closed' });
    expect(view('limit=abc&status=all')).toEqual({ q: undefined, limit: 20, tab: 'all' });
    expect(view('status=open')).toEqual({ q: undefined, limit: 20, tab: 'active' });
  });

  it('writes status only when not Active, q only when set and limit only when not 20; never a cursor', () => {
    expect(projectsSearch({ limit: 20, tab: 'active' })).toBe('');
    expect(projectsSearch({ q: 'lagoon', limit: 20, tab: 'active' })).toBe('?q=lagoon');
    expect(projectsSearch({ q: 'a b', limit: 10, tab: 'all' })).toBe('?status=all&q=a+b&limit=10');
    expect(projectsSearch({ limit: 50, tab: 'closed' })).toBe('?status=closed&limit=50');
  });

  it('always sends limit, status for Active and Closed only, q only with text and the cursor only when given', () => {
    expect(buildProjectsQuery({ limit: 20, tab: 'active' })).toEqual({ limit: 20, status: 'active' });
    expect(buildProjectsQuery({ q: '  ', limit: 10, tab: 'all' })).toEqual({ limit: 10 });
    expect(buildProjectsQuery({ q: ' lagoon ', limit: 20, tab: 'closed' }, 'o20')).toEqual({ limit: 20, status: 'closed', q: 'lagoon', cursor: 'o20' });
  });

  it('counts pieces of work and distinct lines, names the client and decodes the route segment once', () => {
    const lines = [
      { line: 'Prepare an invoice', state: 'verified', work_id: 'W-1' },
      { line: 'Prepare an invoice', state: 'waiting', work_id: 'W-2' },
      { line: 'RFP response', state: 'verified', work_id: 'W-3' },
    ] as const;
    expect(workCounts([...lines])).toEqual({ pieces: 3, lines: 2 });
    expect(workCounts([])).toEqual({ pieces: 0, lines: 0 });
    const journey = { case_id: 'P-1', title: 'Lagoon Health · patient app', lines: [], next: 'x' };
    expect(clientOf(journey)).toBe('Lagoon Health');
    expect(clientOf({ ...journey, client: 'Lagoon' })).toBe('Lagoon');
    expect(routeCaseId('P%2F..%3Cb%3E')).toBe('P/..<b>');
    expect(routeCaseId('P-0101')).toBe('P-0101');
    expect(routeCaseId('%E0%A4%A')).toBe('%E0%A4%A');
  });
});

describe('response checks', () => {
  const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
  const journey = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-PROJECT.json'), 'utf8'));
  const list = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-PROJECTS.json'), 'utf8'));

  it('accepts the contract bodies and refuses others, such as the E-ME body', () => {
    expect(isProjectList(list)).toBe(true);
    expect(isProjectList({ items: [], as_of: '2026-11-14T09:00:00Z' })).toBe(true);
    expect(isJourney(journey)).toBe(true);
    expect(isJourney({ ...journey, lines: [] })).toBe(true);
    for (const body of [me, null, 'text', [], { items: 'x' }, { items: [{}] }]) expect(isProjectList(body)).toBe(false);
    for (const body of [me, null, list, { ...journey, lines: undefined }, { ...journey, next: '' }]) expect(isJourney(body)).toBe(false);
  });
});
