import { describe, expect, it } from 'vitest';

import { deliveryRows, holdReasons, isChecklist, isOverview, LINE_KEYS, reasonsNeeded, stateWords, type DeliveryOverview } from '../src/features/projects/deliveryModel';
// @ts-expect-error plain ESM module without type declarations
import { deliveryRead } from '../mock/delivery-overview.mjs';

const idOf = (v: string) => v;
const overviewOf = (caseId: string) => deliveryRead({ pathname: `/api/v1/projects/${caseId}/delivery-overview`, idOf })[1] as DeliveryOverview;
const clone = () => structuredClone(overviewOf('P-0101'));

describe('rows', () => {
  it('draws six rows in the fixed order and numbers 01 to 06 even when the lines come shuffled', () => {
    const shuffled = clone();
    expect(shuffled.lines.map((l) => l.key)).not.toEqual([...LINE_KEYS]);
    const rows = deliveryRows(shuffled);
    expect(rows.map((r) => r.line.key)).toEqual([...LINE_KEYS]);
    expect(rows.map((r) => r.number)).toEqual(['01', '02', '03', '04', '05', '06']);
    expect(rows[0].href).toBe('/work/2501');
    expect(rows[5].href).toBeNull();
    expect(rows[5].reference).toBeNull();
    expect(rows[5].updatedAt).toBeNull();
  });
});

describe('state words', () => {
  const cases: [string | null, string][] = [
    ['ready', 'READY'], ['waiting', 'WAITING'], ['action_needed', 'ACTION NEEDED'], ['owner_needed', 'NEEDS AN OWNER'], ['setup_needed', 'SET-UP NEEDED'],
    ['verified', 'VERIFIED'], ['cancelled', 'CANCELLED'], ['awaiting_reconciliation', 'CHECKING WHAT HAPPENED'], ['followup_needed', 'FOLLOW-UP NEEDED'],
    ['processing', 'IN PROGRESS'], ['effect_uncertain', 'RESULT UNCERTAIN'], [null, 'NOT STARTED'],
  ];
  it.each(cases)('%s reads %s', (state, text) => {
    expect(stateWords({ state: state as never, gate_state: (state ?? 'not_started') as never }).text).toBe(text);
  });
  it('a made-up value reads UNKNOWN, also for prototype names', () => {
    expect(stateWords({ state: 'made_up' as never, gate_state: 'made_up' as never }).text).toBe('UNKNOWN');
    expect(stateWords({ state: 'constructor' as never, gate_state: 'ready' }).text).toBe('UNKNOWN');
  });
  it('a null state takes a started gate_state', () => {
    expect(stateWords({ state: null, gate_state: 'waiting' }).text).toBe('WAITING');
  });
});

describe('response check', () => {
  it('accepts the fixtures', () => {
    expect(isOverview(clone())).toBe(true);
    expect(isOverview(overviewOf('P-0102'))).toBe(true);
  });
  it.each([
    ['five lines', (o: DeliveryOverview) => { o.lines.pop(); }],
    ['no lines', (o: DeliveryOverview) => { o.lines = []; }],
    ['a duplicated key', (o: DeliveryOverview) => { o.lines[1] = { ...o.lines[0] }; }],
    ['an unknown key', (o: DeliveryOverview) => { (o.lines[0] as { key: string }).key = 'delivery-other/v1'; }],
    ['a missing field', (o: DeliveryOverview) => { delete (o.lines[0] as Partial<DeliveryOverview['lines'][0]>).gate_state; }],
    ['a missing as_of', (o: DeliveryOverview) => { delete (o as Partial<DeliveryOverview>).as_of; }],
  ])('refuses %s', (_, mutate) => {
    const o = clone();
    mutate(o);
    expect(isOverview(o)).toBe(false);
  });
  it.each([null, 'x', [], {}])('refuses %j', (v) => expect(isOverview(v)).toBe(false));
});

describe('closure reasons', () => {
  const checklist = (ready: boolean) => ({ ready_to_prepare: ready, checks: [
    { title: 'A', status: 'held', finding: 'why' }, { title: 'B', status: 'current', finding: null }, { title: 'C', status: 'unknown', finding: null },
    { title: 'D', status: 'unavailable', finding: null }, { title: 'E', status: 'closed', finding: null }, { title: 'F', status: 'recorded', finding: 'x' },
  ] });
  it('lists held, unknown and unavailable checks in the order sent', () => {
    expect(holdReasons(checklist(false) as never)).toEqual([{ title: 'A', finding: 'why' }, { title: 'C', finding: null }, { title: 'D', finding: null }]);
  });
  it('lists nothing when ready to prepare', () => expect(holdReasons(checklist(true) as never)).toEqual([]));
  it('checks the checklist shape', () => {
    expect(isChecklist(checklist(false))).toBe(true);
    expect(isChecklist({ checks: [] })).toBe(false);
  });
  it('is read only when closure has no work and release has work', () => {
    expect(reasonsNeeded(clone())).toBe(true);
    expect(reasonsNeeded(overviewOf('P-0102'))).toBe(false);
    const started = clone();
    started.lines.find((l) => l.key === 'delivery-closure/v1')!.work_id = 9;
    expect(reasonsNeeded(started)).toBe(false);
  });
});
