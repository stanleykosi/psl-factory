import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { describeStation, diffCounts, floorLabel } from '@/features/floor/support';
import type { Overview } from '@/features/overview/types';

const read = (path: string): Overview => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8'));
const before = read('E-OVERVIEW.json');
const after = read('overview/changed.json');

describe('diffCounts', () => {
  it('returns exactly the stations whose count or needs_person changed', () => {
    expect(diffCounts(before.lines, after.lines).map((c) => [c.line, c.name, c.before.count, c.after.count, c.after.needs_person])).toEqual([
      ['Pre-sale', 'Brief', 1, 2, false],
      ['Invoices', 'Milestone', 3, 1, false],
      ['Payroll', 'Approve', 1, 1, false],
    ]);
  });

  it('returns nothing for identical inputs', () => {
    expect(diffCounts(before.lines, structuredClone(before.lines))).toEqual([]);
  });

  it('matches by line and station name; new or gone stations are not changes', () => {
    const next = structuredClone(before.lines);
    next[0].stations.splice(1, 1);
    next[0].stations.push({ name: 'New', count: 4, needs_person: false });
    next.reverse();
    expect(diffCounts(before.lines, next)).toEqual([]);
  });
});

it('floorLabel names the line count', () => {
  expect(floorLabel(8)).toBe('3D factory floor: 8 lines. The same figures are listed in the flat view below.');
});

it('describeStation reads Line · Station · N items · needs a person', () => {
  expect(describeStation('Invoices', { name: 'Approve', count: 1, needs_person: true })).toBe('Invoices · Approve · 1 item · needs a person');
  expect(describeStation('Planning', { name: 'Scope', count: 2, needs_person: false })).toBe('Planning · Scope · 2 items · no person needed');
  expect(describeStation('Closing', { name: 'Review', count: 0, needs_person: false })).toBe('Closing · Review · 0 items · no person needed');
});
