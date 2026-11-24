import { describe, expect, it } from 'vitest';

import {
  actionsSummaryText,
  ageText,
  buildTabQuery,
  dueText,
  fromText,
  ownerText,
  isTabResponse,
  parseTabView,
  registerCountText,
  tabSearch,
  workHref,
} from '@/features/projects/tabsModel';

describe('URL state', () => {
  it('parses register and q; an unknown register is Issues; only Registers reads register', () => {
    expect(parseTabView(new URLSearchParams('register=changes&q=%20sms%20'), 'registers')).toEqual({ register: 'changes', q: 'sms' });
    expect(parseTabView(new URLSearchParams('register=nope'), 'registers')).toEqual({ register: 'issues', q: undefined });
    expect(parseTabView(new URLSearchParams('register=ISSUES'), 'registers').register).toBe('issues');
    expect(parseTabView(new URLSearchParams('register=changes&q=a'), 'actions')).toEqual({ register: 'issues', q: 'a' });
    expect(parseTabView(new URLSearchParams('q=%20'), 'registers').q).toBeUndefined();
  });

  it('writes register unless Issues and q unless empty; never a cursor', () => {
    expect(tabSearch({ register: 'issues' })).toBe('');
    expect(tabSearch({ register: 'rfps', q: 'a b' })).toBe('?register=rfps&q=a+b');
    expect(tabSearch({ register: 'issues', q: 'x' })).toBe('?q=x');
  });

  it('builds the request: limit always, register only on Registers, q only when set, cursor for more', () => {
    expect(buildTabQuery('documents', { register: 'issues' })).toEqual({ limit: 10 });
    expect(buildTabQuery('registers', { register: 'issues' })).toEqual({ limit: 10, register: 'issues' });
    expect(buildTabQuery('registers', { register: 'rfps', q: 'a' }, 'o20')).toEqual({ limit: 10, register: 'rfps', q: 'a', cursor: 'o20' });
    expect(buildTabQuery('actions', { register: 'changes', q: 'a' })).toEqual({ limit: 10, q: 'a' });
  });
});

describe('response check', () => {
  it('needs the typed array of the tab with well-formed rows; items alone is not enough', () => {
    expect(isTabResponse({ items: [{}], as_of: 'x' }, 'documents')).toBe(false);
    expect(isTabResponse({ documents: [] }, 'documents')).toBe(true);
    expect(isTabResponse({ documents: [{ title: 'x' }] }, 'documents')).toBe(false);
    expect(isTabResponse({ registers: [{ reference: 'R', title: 'T' }] }, 'registers')).toBe(true);
    expect(isTabResponse({ registers: [{ reference: 'R' }] }, 'registers')).toBe(false);
    expect(isTabResponse({ actions: [{ action_id: 'A', title: 'T', state: 'open' }] }, 'actions')).toBe(true);
    expect(isTabResponse(null, 'actions')).toBe(false);
  });
});

describe('owner, age, due, from', () => {
  it('age: days from one day, hours from one hour, <1h below; none when absent or unreadable', () => {
    expect(ageText(2 * 86400 + 5)).toBe('2d');
    expect(ageText(86400)).toBe('1d');
    expect(ageText(86399)).toBe('23h');
    expect(ageText(3600)).toBe('1h');
    expect(ageText(3599)).toBe('<1h');
    expect(ageText(0)).toBe('<1h');
    expect(ageText(undefined)).toBeUndefined();
    expect(ageText(-5)).toBeUndefined();
    expect(ageText(Number.NaN)).toBeUndefined();
    expect(ageText('3')).toBeUndefined();
  });

  it('due: a date as dd Mon; unknown, absent or unreadable is undefined', () => {
    expect(dueText({ date: '2026-11-13', unknown: false })).toBe('13 Nov');
    expect(dueText({ unknown: true })).toBeUndefined();
    expect(dueText({ date: '2026-11-13', unknown: true })).toBeUndefined();
    expect(dueText({ unknown: false })).toBeUndefined();
    expect(dueText(undefined)).toBeUndefined();
    expect(dueText({ date: 'soon', unknown: false })).toBeUndefined();
  });

  it('owner: role · name, (recorded by PM), nothing when absent; outside_party adds no text', () => {
    expect(ownerText({ name: 'Lagoon Health', role: 'Client', outside_party: true })).toBe('Client · Lagoon Health');
    expect(ownerText({ name: 'Engineering', recorded_by_pm: true })).toBe('Engineering (recorded by PM)');
    expect(ownerText({ name: 'Tunde Bello', role: 'PM', recorded_by_pm: true })).toBe('PM · Tunde Bello (recorded by PM)');
    expect(ownerText({ name: 'Tunde Bello' })).toBe('Tunde Bello');
    expect(ownerText(undefined)).toBeUndefined();
  });

  it('from: meeting and day, the meeting alone, or nothing', () => {
    expect(fromText({ meeting: 'Weekly sync', at: '2026-11-10' })).toBe('From Weekly sync · 10 Nov');
    expect(fromText({ meeting: 'Weekly sync' })).toBe('From Weekly sync');
    expect(fromText(undefined)).toBeUndefined();
  });

  it('counts come from the summary as sent; nothing is counted here', () => {
    expect(actionsSummaryText({ actions: { total: 9, overdue: 3, without_owner: 1 } })).toBe('9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER');
    expect(actionsSummaryText({ actions: { total: 9 } })).toBe('9 ACTIONS');
    expect(actionsSummaryText({ actions: { total: 0 } })).toBe('0 ACTIONS');
    expect(actionsSummaryText(undefined)).toBe('');
    expect(registerCountText({ registers: { issues: 3, rfps: 1 } }, 'issues')).toBe('3 ISSUES');
    expect(registerCountText({ registers: { issues: 3, rfps: 1 } }, 'rfps')).toBe('1 RFP');
    expect(registerCountText({ registers: { issues: 3 } }, 'changes')).toBe('');
    expect(registerCountText(undefined, 'issues')).toBe('');
  });

  it('a work link only for a real work_id, encoded', () => {
    expect(workHref('W-1002')).toBe('/work/W-1002');
    expect(workHref('a/b')).toBe('/work/a%2Fb');
    expect(workHref(undefined)).toBeUndefined();
    expect(workHref('')).toBeUndefined();
  });
});
