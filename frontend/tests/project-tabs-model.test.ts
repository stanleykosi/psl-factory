import { describe, expect, it } from 'vitest';

import {
  actionsSummaryText,
  ageText,
  amountText,
  buildTabQuery,
  completionText,
  dueText,
  fromText,
  hasChanges,
  ownerText,
  invoiceWord,
  isTabResponse,
  paidWord,
  parseTabView,
  PAID_WORDS,
  registerCountText,
  tabSearch,
  workHref,
  type MilestoneRow,
  type Paid,
} from '@/features/projects/tabsModel';

const ngn = (amount?: string, unknown = false) => ({ amount, currency: 'NGN', unknown });
const milestone = (over: Partial<MilestoneRow> = {}): MilestoneRow => ({ position: 1, name: 'M', contract_amount: ngn('1.00'), completion: { status: 'not_yet' }, ...over });

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
    expect(buildTabQuery('milestones', { register: 'issues' })).toEqual({ limit: 10 });
    expect(buildTabQuery('registers', { register: 'issues' })).toEqual({ limit: 10, register: 'issues' });
    expect(buildTabQuery('registers', { register: 'rfps', q: 'a' }, 'o20')).toEqual({ limit: 10, register: 'rfps', q: 'a', cursor: 'o20' });
    expect(buildTabQuery('actions', { register: 'changes', q: 'a' })).toEqual({ limit: 10, q: 'a' });
  });
});

describe('response check', () => {
  it('needs the typed array of the tab with well-formed rows; items alone is not enough', () => {
    expect(isTabResponse({ items: [{}], as_of: 'x' }, 'milestones')).toBe(false);
    expect(isTabResponse({ milestones: [] }, 'milestones')).toBe(true);
    expect(isTabResponse({ milestones: [{ name: 'x' }] }, 'milestones')).toBe(false);
    expect(isTabResponse({ registers: [{ reference: 'R', title: 'T' }] }, 'registers')).toBe(true);
    expect(isTabResponse({ registers: [{ reference: 'R' }] }, 'registers')).toBe(false);
    expect(isTabResponse({ actions: [{ action_id: 'A', title: 'T', state: 'open' }] }, 'actions')).toBe(true);
    expect(isTabResponse(null, 'actions')).toBe(false);
  });
});

describe('amounts: Unknown is never 0', () => {
  it('NGN with the sign, other currencies with their code, unknown or missing as undefined', () => {
    expect(amountText(ngn('4250000.00'))).toBe('₦4,250,000.00');
    expect(amountText(ngn('4250000'))).toBe('₦4,250,000.00');
    expect(amountText({ amount: '1250000.50', currency: 'USD', unknown: false })).toBe('USD 1,250,000.50');
    expect(amountText(ngn(undefined, true))).toBeUndefined();
    expect(amountText(ngn('5.00', true))).toBeUndefined();
    expect(amountText(ngn(undefined, false))).toBeUndefined();
    expect(amountText(ngn('abc'))).toBeUndefined();
    expect(amountText({ amount: 'abc', currency: 'USD', unknown: false })).toBeUndefined();
    expect(amountText(undefined)).toBeUndefined();
  });
});

describe('completion, invoice and paid are separate facts', () => {
  it('completion text follows the row only', () => {
    expect(completionText(milestone({ completion: { status: 'done', at: '2026-10-27T10:00:00Z', evidence_id: 'E' } }))).toBe('Done 27 Oct · proof');
    expect(completionText(milestone({ completion: { status: 'done', at: '2026-11-11T10:00:00Z', proof: 'client UAT sign-off' } }))).toBe('Done 11 Nov · client UAT sign-off');
    expect(completionText(milestone({ completion: { status: 'done' } }))).toBe('Done');
    expect(completionText(milestone({ completion: { status: 'not_yet' }, amount_note: 'amount set at go-live' }))).toBe('Not yet · amount set at go-live');
    // a not-yet milestone with an invoice and a paid record still reads Not yet
    expect(completionText(milestone({ invoice: { reference: 'INV-1', state: 'verified' }, paid: { status: 'paid' } }))).toBe('Not yet');
  });

  it('every paid status has its own word and unknown has none (drawn as the Unknown tag)', () => {
    const statuses = ['paid', 'part_paid', 'not_paid', 'not_due', 'finance_tracks'] as const;
    expect(statuses.map((status) => paidWord({ status }))).toEqual(['Paid', 'Part paid', 'Not paid', 'Not due', 'Tracked by Finance']);
    expect(Object.keys(PAID_WORDS)).toEqual([...statuses]);
    expect(paidWord({ status: 'unknown' })).toBeUndefined();
    expect(paidWord({ status: 'surprise' } as unknown as Paid)).toBeUndefined();
  });

  it('paid reads only the paid object: an invoice that is verified or paid-looking changes nothing', () => {
    const a = milestone({ invoice: { reference: 'INV-1', state: 'verified' } });
    const b = milestone({ invoice: { reference: 'INV-1', state: 'verified' }, paid: { status: 'not_paid' } });
    expect(a.paid && paidWord(a.paid)).toBeUndefined();
    expect(b.paid && paidWord(b.paid)).toBe('Not paid');
  });

  it('the invoice state word comes from the shared tag words; an absent or unlisted state has none', () => {
    expect(invoiceWord('verified')).toBe('Verified');
    expect(invoiceWord('waiting')).toBe('Waiting');
    expect(invoiceWord(undefined)).toBeUndefined();
    expect(invoiceWord('toString')).toBeUndefined();
  });

  it('knows when any milestone has a change', () => {
    expect(hasChanges([milestone(), milestone({ changes: [] })])).toBe(false);
    expect(hasChanges([milestone(), milestone({ changes: [{ reference: 'CR-1', amount: ngn(undefined, true) }] })])).toBe(true);
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
