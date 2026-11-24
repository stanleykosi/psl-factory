import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { floorOf, FLOOR_MAP_VERSION, FLOORS, OTHER_FLOOR } from '@/features/overview/lines';
import { coverageText, figure, floorsOf, monthLabel, totalsOf, workLink } from '@/features/overview/model';
import type { Overview, WorkCounts } from '@/features/overview/types';

const read = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/floor', path), 'utf8'));
const OVERVIEW: Overview = read('overview.json');
const COUNTS: WorkCounts = read('counts.json');

const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, { get: { parameters: { name: string; schema: { enum?: string[] } }[] } }>;
};
const ENUM = contract.paths['/api/v1/work/counts'].get.parameters.find((p) => p.name === 'line')!.schema.enum!;

describe('the local key-to-floor map', () => {
  it('is version 1', () => expect(FLOOR_MAP_VERSION).toBe(1));

  it('puts every one of the 26 /work/counts line keys on exactly one floor', () => {
    expect(ENUM).toHaveLength(26);
    const listed = FLOORS.flatMap((f) => f.keys);
    expect(new Set(listed).size).toBe(listed.length);
    for (const key of ENUM) {
      const floors = FLOORS.filter((f) => f.keys.includes(key));
      expect(floors.length <= 1, key).toBe(true);
      expect(floorOf(key)).toBe(floors[0]?.name ?? OTHER_FLOOR);
    }
    expect(listed.every((k) => ENUM.includes(k))).toBe(true);
    expect(ENUM.filter((k) => floorOf(k) === OTHER_FLOOR).sort()).toEqual(
      ['pmo-change/v1', 'pmo-emergency/v1', 'pmo-escalation/v1', 'pmo-issues/v1', 'pmo-leadership-report/v1', 'pmo-minutes/v1', 'pmo-weekly-report/v1', 'process-handoff/v1'],
    );
  });

  it('keeps a key it does not know under "Other lines"', () => expect(floorOf('future-line/v1')).toBe(OTHER_FLOOR));
});

describe('floorsOf', () => {
  it('groups in drawn order with "Other lines" last, sums the totals and leaves empty floors out', () => {
    const floors = floorsOf(OVERVIEW, COUNTS);
    expect(floors.map((f) => [f.name, f.total])).toEqual([['Pre-sale', 4], ['Invoices', 4], [OTHER_FLOOR, 7]]);
    expect(floors[2].lines.map((l) => [l.key, l.total])).toEqual([['pmo-minutes/v1', 2], ['future-line/v1', 5]]);
  });

  it('draws five stations for a line with counts, and five known zeros for an absent line when the counts are not limited', () => {
    const floors = floorsOf(OVERVIEW, COUNTS);
    const commercial = floors[0].lines.find((l) => l.key === 'commercial/v1')!;
    expect(commercial.stations!.map((s) => [s.name, s.count, s.needs_person])).toEqual([['Intake', 1, 0], ['Execution', 1, 0], ['Decision', 1, 2], ['Delivery', 0, 0], ['Verified', 1, 0]]);
    const later = floors[2].lines.find((l) => l.key === 'future-line/v1')!;
    expect(later.stations!.map((s) => s.count)).toEqual([0, 0, 0, 0, 0]);
  });

  it('an absent line is unknown (null, never zeros) when the counts are limited, and so is every line when the counts failed', () => {
    const limited = { ...COUNTS, limited: true, evaluated: 50, lines: COUNTS.lines.filter((l) => l.key !== 'commercial/v1') };
    expect(floorsOf(OVERVIEW, limited)[0].lines.find((l) => l.key === 'commercial/v1')!.stations).toBeNull();
    expect(floorsOf(OVERVIEW, limited)[0].lines.find((l) => l.key === 'rfp-response/v1')!.stations).not.toBeNull();
    expect(floorsOf(OVERVIEW, null).flatMap((f) => f.lines).every((l) => l.stations === null)).toBe(true);
  });
});

describe('totals and wording', () => {
  it('sums every line the counts return, including lines /overview does not list', () => {
    expect(totalsOf(COUNTS)).toEqual({ inProgress: 10, needPerson: 4, stopped: 1, verifiedThisMonth: 3 });
    const extra = { ...COUNTS, lines: [...COUNTS.lines, { ...COUNTS.lines[0], key: 'pmo-issues/v1' as const, open: 5 }] };
    expect(totalsOf(extra).inProgress).toBe(15);
  });

  it('"at least N" whenever limited, never a bare number', () => {
    expect(figure(10, false)).toBe('10');
    expect(figure(10, true)).toBe('at least 10');
    expect(figure(0, true)).toBe('at least 0');
  });

  it('coverage line, month label and the queue link', () => {
    expect(coverageText(COUNTS)).toBe('Counted from all 15 items you can see');
    expect(coverageText({ ...COUNTS, limited: true, evaluated: 50 })).toBe('Counted from the 50 most recent items you can see');
    expect(monthLabel('2026-11')).toBe('Nov 2026');
    expect(workLink('commercial/v1')).toBe('/my-work?line=commercial%2Fv1');
  });
});
