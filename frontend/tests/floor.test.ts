import { describe, expect, it } from 'vitest';

import { describeStation, floorLabel } from '@/features/floor/support';

it('floorLabel names the line count', () => {
  expect(floorLabel(5)).toBe('3D factory floor: 5 lines. The same figures are listed in the flat view below.');
  expect(floorLabel(1)).toBe('3D factory floor: 1 line. The same figures are listed in the flat view below.');
});

describe('describeStation', () => {
  const station = (count: number, needs_person: number) => ({ key: 'decision', name: 'Decision', count, needs_person });

  it('says "needs a person" only when needs_person is above 0', () => {
    expect(describeStation('Costing', station(1, 2))).toBe('Costing · Decision · 1 item · needs a person');
    expect(describeStation('Costing', station(2, 0))).toBe('Costing · Decision · 2 items');
  });

  it('never says "no person needed": the counts are a sample', () => {
    expect(describeStation('Costing', station(0, 0))).toBe('Costing · Decision · 0 items');
  });
});
