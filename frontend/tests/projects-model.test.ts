import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { buildProjectsQuery, isJourney, isProjectList, parseProjectsView, projectsSearch } from '@/features/projects/model';

const view = (search: string) => parseProjectsView(new URLSearchParams(search));

describe('projects view and query', () => {
  it('reads q and limit from the URL; an empty q and an invalid limit fall back to the defaults', () => {
    expect(view('')).toEqual({ q: undefined, limit: 20 });
    expect(view('q=lagoon&limit=10')).toEqual({ q: 'lagoon', limit: 10 });
    expect(view('q=%20%20&limit=7')).toEqual({ q: undefined, limit: 20 });
    expect(view('limit=50')).toEqual({ q: undefined, limit: 50 });
    expect(view('limit=abc')).toEqual({ q: undefined, limit: 20 });
  });

  it('writes q only when set and limit only when not 20; never a cursor', () => {
    expect(projectsSearch({ limit: 20 })).toBe('');
    expect(projectsSearch({ q: 'lagoon', limit: 20 })).toBe('?q=lagoon');
    expect(projectsSearch({ q: 'a b', limit: 10 })).toBe('?q=a+b&limit=10');
    expect(projectsSearch({ limit: 50 })).toBe('?limit=50');
  });

  it('always sends limit, sends q only with text and the cursor only when given', () => {
    expect(buildProjectsQuery({ limit: 20 })).toEqual({ limit: 20 });
    expect(buildProjectsQuery({ q: '  ', limit: 10 })).toEqual({ limit: 10 });
    expect(buildProjectsQuery({ q: ' lagoon ', limit: 20 }, 'o20')).toEqual({ limit: 20, q: 'lagoon', cursor: 'o20' });
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
