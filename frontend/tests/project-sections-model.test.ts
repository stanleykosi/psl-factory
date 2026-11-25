import { describe, expect, it } from 'vitest';

import {
  actionsHeaderText,
  ageText,
  availableRegisters,
  buildSectionQuery,
  dueText,
  fromText,
  isSectionsBody,
  knownPriority,
  mergePage,
  parseSectionView,
  REGISTER_SECTIONS,
  registerCountText,
  sectionSearch,
  selectedRegister,
  stateTone,
  type Section,
  type SectionItem,
} from '@/features/projects/sectionsModel';

const item = (record_id: number, over: Partial<SectionItem> = {}): SectionItem => ({
  title: `ISS-${record_id}`,
  state: 'Open',
  state_code: 'open',
  detail: null,
  at: null,
  due: null,
  severity: null,
  owner: null,
  django_url: '/x',
  record_id,
  api_url: `/api/v1/x/${record_id}`,
  reference: null,
  age_days: null,
  origin_meeting: null,
  ...over,
});
const section = (key: string, items: SectionItem[], over: Partial<Section> = {}): Section => ({ key, title: key, items, page: 1, has_more: false, total: items.length, counts: null, django_url: '/x', api_url: null, ...over });
const body = (over: Record<string, unknown> = {}) => ({ case_id: 'c', tab: 'registers', as_of: '2026-11-12T15:40:00Z', sections: [section('issues', [item(1)])], ...over });

describe('isSectionsBody', () => {
  it('accepts a sections body for the requested tab, with or without rows', () => {
    expect(isSectionsBody(body(), 'registers')).toBe(true);
    expect(isSectionsBody(body({ sections: [] }), 'registers')).toBe(true);
    expect(isSectionsBody(body({ sections: [section('meetings', [], { counts: { total: 0, overdue: 0, unassigned: 0 } })], tab: 'actions' }), 'actions')).toBe(true);
    expect(isSectionsBody(body({ tab: 'documents' }), 'documents')).toBe(true);
    expect(isSectionsBody(body({ tab: 'documents' }), 'registers')).toBe(false);
  });

  it('refuses another tab, a non-object, a missing key, total, page, has_more or state_code, bad counts and a bad age', () => {
    expect(isSectionsBody(body({ tab: 'actions' }), 'registers')).toBe(false);
    expect(isSectionsBody(null, 'registers')).toBe(false);
    expect(isSectionsBody([], 'registers')).toBe(false);
    expect(isSectionsBody(body({ case_id: undefined }), 'registers')).toBe(false);
    expect(isSectionsBody(body({ sections: 'x' }), 'registers')).toBe(false);
    const bad = (over: Record<string, unknown>) => isSectionsBody(body({ sections: [{ ...section('issues', [item(1)]), ...over }] }), 'registers');
    expect(bad({ key: undefined })).toBe(false);
    expect(bad({ total: undefined })).toBe(false);
    expect(bad({ total: -1 })).toBe(false);
    expect(bad({ total: 1.5 })).toBe(false);
    expect(bad({ page: 0 })).toBe(false);
    expect(bad({ has_more: 'no' })).toBe(false);
    expect(bad({ counts: { total: 1 } })).toBe(false);
    expect(bad({ counts: { total: 1, overdue: -1, unassigned: 0 } })).toBe(false);
    expect(bad({ items: [{ ...item(1), state_code: undefined }] })).toBe(false);
    expect(bad({ items: [{ ...item(1), title: '' }] })).toBe(false);
    expect(bad({ items: [{ ...item(1), age_days: -1 }] })).toBe(false);
    expect(bad({ items: [{ ...item(1), age_days: 0 }] })).toBe(true);
  });
});

describe('the drawn registers match on key, never on title', () => {
  it('keeps the table order and the registers that came back; Escalations and unknown keys are not drawn', () => {
    const sections = [section('escalations', []), section('rfp', []), section('issues', []), section('mystery', [])];
    expect(availableRegisters(sections).map((r) => r.id)).toEqual(['issues', 'rfps']);
    expect(availableRegisters([])).toEqual([]);
  });

  it('a renamed title with key rfp is still RFPs; a title that says Issues under another key is not Issues', () => {
    const renamed = { ...section('rfp', []), title: 'Bid requests' };
    const lookalike = { ...section('other', []), title: 'Issues' };
    expect(availableRegisters([renamed]).map((r) => r.label)).toEqual(['RFPs']);
    expect(availableRegisters([lookalike])).toEqual([]);
  });

  it('the selected register is the one the URL names when it came back, else the first that came back', () => {
    const available = availableRegisters([section('changes', []), section('rfp', [])]);
    expect(selectedRegister(available, 'rfps')?.id).toBe('rfps');
    expect(selectedRegister(available, 'issues')?.id).toBe('changes');
    expect(selectedRegister(available)?.id).toBe('changes');
    expect(selectedRegister([], 'issues')).toBeUndefined();
  });
});

describe('URL state and request', () => {
  it('reads register only on Registers and only a drawn one; q is trimmed, cut at 120, empty is none', () => {
    expect(parseSectionView(new URLSearchParams('register=changes&q=%20sms%20'), 'registers')).toEqual({ register: 'changes', q: 'sms' });
    expect(parseSectionView(new URLSearchParams('register=rfps'), 'registers').register).toBe('rfps');
    expect(parseSectionView(new URLSearchParams('register=nope'), 'registers').register).toBeUndefined();
    expect(parseSectionView(new URLSearchParams('register=ISSUES'), 'registers').register).toBeUndefined();
    expect(parseSectionView(new URLSearchParams('register=changes&q=a'), 'actions')).toEqual({ register: undefined, q: 'a' });
    expect(parseSectionView(new URLSearchParams('q=%20'), 'registers').q).toBeUndefined();
    expect(parseSectionView(new URLSearchParams(`q=${'a'.repeat(200)}`), 'actions').q).toHaveLength(120);
  });

  it('writes register for any register but Issues and q when set; never a page', () => {
    expect(sectionSearch({})).toBe('');
    expect(sectionSearch({ register: 'issues' })).toBe('');
    expect(sectionSearch({ register: 'rfps', q: 'a b' })).toBe('?register=rfps&q=a+b');
    expect(sectionSearch({ register: 'issues', q: 'x' })).toBe('?q=x');
    expect(sectionSearch({ q: 'x' })).toBe('?q=x');
  });

  it('the request carries q and page only: never limit, register, cursor, state, owner or severity', () => {
    expect(buildSectionQuery()).toEqual({});
    expect(buildSectionQuery('android')).toEqual({ q: 'android' });
    expect(buildSectionQuery(undefined, 2)).toEqual({ page: 2 });
    expect(buildSectionQuery('a', 3)).toEqual({ q: 'a', page: 3 });
    expect(buildSectionQuery('')).toEqual({});
  });
});

describe('mergePage', () => {
  const held = [section('issues', [item(1), item(2)], { total: 3, has_more: true }), section('changes', [item(9)], { total: 1 })];

  it('appends a section whose page is the page asked for, and takes its page, has_more, total and counts', () => {
    const next = [section('issues', [item(3)], { page: 2, total: 3 }), section('changes', [item(9)], { page: 1 })];
    const merged = mergePage(held, next, 2);
    expect(merged[0].items.map((i) => i.record_id)).toEqual([1, 2, 3]);
    expect([merged[0].page, merged[0].has_more, merged[0].total]).toEqual([2, false, 3]);
  });

  it('a clamped section (it answered an earlier page again) is not appended twice and is done', () => {
    const next = [section('issues', [item(3)], { page: 2 }), section('changes', [item(9)], { page: 1, has_more: true })];
    const merged = mergePage(held, next, 2);
    expect(merged[1].items.map((i) => i.record_id)).toEqual([9]);
    expect(merged[1].has_more).toBe(false);
    expect(merged[1].page).toBe(1);
  });

  it('skips a row already held, matched by api_url and record_id', () => {
    const next = [section('issues', [item(2), item(3), item(2, { api_url: '/api/v1/other/2' })], { page: 2 })];
    expect(mergePage(held, next, 2)[0].items.map((i) => `${i.api_url}`)).toEqual(['/api/v1/x/1', '/api/v1/x/2', '/api/v1/x/3', '/api/v1/other/2']);
  });

  it('takes counts from the newest answer', () => {
    const actions = [section('meetings', [item(1)], { counts: { total: 2, overdue: 0, unassigned: 0 }, has_more: true })];
    const next = [section('meetings', [item(2)], { page: 2, counts: { total: 2, overdue: 1, unassigned: 0 } })];
    expect(mergePage(actions, next, 2)[0].counts).toEqual({ total: 2, overdue: 1, unassigned: 0 });
  });

  it('a new key is added whole; a key the answer leaves out stays as held', () => {
    const merged = mergePage(held, [section('rfp', [item(5)], { page: 2 })], 2);
    expect(merged.map((s) => s.key)).toEqual(['issues', 'changes', 'rfp']);
    expect(merged[0]).toEqual(held[0]);
  });
});

describe('display text', () => {
  it('Actions tags: open, in progress and paused wait; completed is done; cancelled and any other code are neutral', () => {
    expect(['open', 'in_progress', 'paused'].map(stateTone)).toEqual(['waiting', 'waiting', 'waiting']);
    expect(stateTone('completed')).toBe('done');
    expect(stateTone('cancelled')).toBe('neutral');
    expect(stateTone('surprise')).toBe('neutral');
    expect(stateTone('toString')).toBe('neutral');
  });

  it('severity: high, medium and low in any case use the shared priority; Critical and anything else do not', () => {
    expect(['High', 'medium', 'LOW'].map(knownPriority)).toEqual(['high', 'medium', 'low']);
    expect(knownPriority('Critical')).toBeUndefined();
    expect(knownPriority(null)).toBeUndefined();
  });

  it('age: whole days, 0 reads 0d, an unknown age reads a dash and never 0', () => {
    expect(ageText(2)).toBe('2d');
    expect(ageText(0)).toBe('0d');
    expect(ageText(null)).toBe('—');
    expect(ageText(undefined)).toBe('—');
    expect(ageText(-1)).toBe('—');
    expect(ageText(1.5)).toBe('—');
  });

  it('due: a date-time as dd Mon (Africa/Lagos); absent or unreadable is undefined', () => {
    expect(dueText('2026-11-13T00:00:00Z')).toBe('13 Nov');
    expect(dueText('2026-11-04T00:00:00Z')).toBe('04 Nov');
    expect(dueText(null)).toBeUndefined();
    expect(dueText('')).toBeUndefined();
    expect(dueText('soon')).toBeUndefined();
  });

  it('from: reference and day; nothing without a meeting', () => {
    expect(fromText({ id: 4, reference: 'Weekly sync', at: '2026-11-10T09:00:00Z' })).toBe('From Weekly sync · 10 Nov');
    expect(fromText({ id: 4, reference: 'Weekly sync', at: 'x' })).toBe('From Weekly sync');
    expect(fromText(null)).toBeUndefined();
    expect(fromText(undefined)).toBeUndefined();
  });

  it('counts are the server’s: a known 0 reads 0, and null counts draw no line', () => {
    expect(actionsHeaderText({ total: 9, overdue: 2, unassigned: 1 })).toBe('9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER');
    expect(actionsHeaderText({ total: 0, overdue: 0, unassigned: 0 })).toBe('0 ACTIONS · 0 OVERDUE · 0 WITHOUT OWNER');
    expect(actionsHeaderText(null)).toBe('');
    expect(actionsHeaderText(undefined)).toBe('');
    const [issues, , , rfps] = REGISTER_SECTIONS;
    expect([registerCountText(issues, 3), registerCountText(issues, 1), registerCountText(rfps, 1), registerCountText(rfps, 0)]).toEqual(['3 ISSUES', '1 ISSUE', '1 RFP', '0 RFPS']);
  });
});
