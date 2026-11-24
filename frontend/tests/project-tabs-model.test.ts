import { describe, expect, it } from 'vitest';

import {
  amountText,
  buildTabQuery,
  completionText,
  hasChanges,
  invoiceWord,
  isTabResponse,
  paidWord,
  PAID_WORDS,
  workHref,
  type MilestoneRow,
  type Paid,
} from '@/features/projects/tabsModel';

const ngn = (amount?: string, unknown = false) => ({ amount, currency: 'NGN', unknown });
const milestone = (over: Partial<MilestoneRow> = {}): MilestoneRow => ({ position: 1, name: 'M', contract_amount: ngn('1.00'), completion: { status: 'not_yet' }, ...over });

describe('request', () => {
  it('builds the request: limit always, register only on Registers, q only when set, cursor for more', () => {
    expect(buildTabQuery('documents', { register: 'issues' })).toEqual({ limit: 10 });
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

describe('work link', () => {
  it('a work link only for a real work_id, encoded', () => {
    expect(workHref('W-1002')).toBe('/work/W-1002');
    expect(workHref('a/b')).toBe('/work/a%2Fb');
    expect(workHref(undefined)).toBeUndefined();
    expect(workHref('')).toBeUndefined();
  });
});
