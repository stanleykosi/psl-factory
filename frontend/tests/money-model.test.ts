import { describe, expect, it } from 'vitest';

import { amountText, invoiceLines, isMoney, stageLabel, type Money, type MoneyItem } from '@/features/projects/moneyModel';

const item = (over: Partial<MoneyItem> = {}): MoneyItem => ({
  key: 'k',
  label: 'Stage',
  amount: '1000.00',
  currency: 'NGN',
  due_date: null,
  milestone_id: null,
  stage_position: null,
  completed_at: null,
  contract_stage: true,
  missing_reason: null,
  invoices: [],
  sources: [],
  changes: [],
  ...over,
});
const invoice = (over: Partial<MoneyItem['invoices'][number]> = {}) => ({ id: 1, reference: 'INV-1', version: 1, currency: 'NGN', paid: null, owed: null, status: 'Issued', at: '2026-11-20T09:00:00Z', api_url: '/x', ...over });
const body = (items: MoneyItem[] = [item()], over: Partial<Money> = {}): Money => ({ items, limited: false, as_of: '2026-11-12T15:40:00Z', finance_url: '/f', ...over });

describe('amountText: the currency code, never a symbol, never 0', () => {
  it('puts the item currency before the grouped amount with two decimals', () => {
    expect(amountText('1000', 'USD')).toBe('USD 1,000.00');
    expect(amountText('4250000.00', 'NGN')).toBe('NGN 4,250,000.00');
    expect(amountText('1200.5', 'GBP')).toBe('GBP 1,200.50');
    expect(amountText('4250000.00', 'USD')).not.toContain('₦');
  });

  it('null and non-numeric amounts are undefined, so the caller draws Unknown', () => {
    expect(amountText(null, 'NGN')).toBeUndefined();
    expect(amountText('', 'NGN')).toBeUndefined();
    expect(amountText('abc', 'NGN')).toBeUndefined();
    expect(amountText('1e5', 'NGN')).toBeUndefined();
  });

  it('keeps digits a number would lose', () => {
    expect(amountText('9223372036854775807.00', 'NGN')).toBe('NGN 9,223,372,036,854,775,807.00');
  });
});

describe('invoice lines: status as given, paid and owed never worked out', () => {
  it('lists every invoice in order with its own status, paid and owed', () => {
    const lines = invoiceLines(item({ invoices: [invoice({ id: 1, reference: 'A', status: 'Delivered', paid: '5.00', owed: '1.00' }), invoice({ id: 2, reference: 'B', status: 'Awaiting Finance decision' })] }));
    expect(lines).toEqual([
      { id: 1, reference: 'A', status: 'Delivered', paid: 'NGN 5.00', owed: 'NGN 1.00' },
      { id: 2, reference: 'B', status: 'Awaiting Finance decision', paid: undefined, owed: undefined },
    ]);
  });

  it('paid equal to the amount changes no text, and Delivered is not paid', () => {
    const plain = invoiceLines(item({ amount: '100.00', invoices: [invoice({ status: 'Delivered', paid: null, owed: null })] }));
    const equal = invoiceLines(item({ amount: '100.00', invoices: [invoice({ status: 'Delivered', paid: '100.00', owed: null })] }));
    expect(plain[0].status).toBe('Delivered');
    expect(equal[0].status).toBe('Delivered');
    expect(plain[0].paid).toBeUndefined();
    expect(JSON.stringify(plain)).not.toMatch(/part|"paid"?:"paid/i);
  });

  it('an invoice in another currency keeps its own code', () => {
    expect(invoiceLines(item({ invoices: [invoice({ currency: 'USD', paid: '2.00' })] }))[0].paid).toBe('USD 2.00');
  });
});

describe('stage label', () => {
  it('shows the position before the label and nothing when there is none (never the index)', () => {
    expect(stageLabel(item({ label: 'UAT', stage_position: 2 }))).toBe('2 · UAT');
    expect(stageLabel(item({ label: 'UAT', stage_position: null }))).toBe('UAT');
  });
});

describe('isMoney guard', () => {
  it('accepts a live body, including none and null figures', () => {
    expect(isMoney(body())).toBe(true);
    expect(isMoney(body([]))).toBe(true);
    expect(isMoney(body([item({ amount: null, missing_reason: 'Not stated', invoices: [invoice()], sources: [{ label: 'S', django_url: '/d', at: null, kind: null, record_id: null, reference: null, api_url: null }] })]))).toBe(true);
  });

  it.each([
    ['null', null],
    ['a list', []],
    ['no items', { limited: false, as_of: 'x' }],
    ['items not a list', { ...body(), items: {} }],
    ['limited missing', { items: [], as_of: 'x' }],
    ['as_of missing', { items: [], limited: false }],
    ['an item without a key', body([{ ...item(), key: undefined } as unknown as MoneyItem])],
    ['an amount that is a number', body([item({ amount: 1000 as unknown as string })])],
    ['a stage position that is text', body([item({ stage_position: '1' as unknown as number })])],
    ['an invoice with no status', body([item({ invoices: [{ ...invoice(), status: undefined } as never] })])],
    ['an invoice without an id', body([item({ invoices: [{ ...invoice(), id: undefined } as never] })])],
    ['an invoice without a currency', body([item({ invoices: [{ ...invoice(), currency: undefined } as never] })])],
    ['a change without a link_id', body([item({ changes: [{ reference: 'C', note: 'n', additional_amount: null } as never] })])],
    ['a paid that is a number', body([item({ invoices: [invoice({ paid: 0 as unknown as string })] })])],
    ['a source without a label', body([item({ sources: [{ django_url: '/d' } as never] })])],
    ['a change with an amount', body([item({ changes: [{ link_id: 1, version_id: 1, reference: 'C', number: 1, note: 'n', plan_id: 1, additional_amount: '5.00' as unknown as null, api_url: '/x' }] })])],
  ])('rejects %s', (_name, value) => {
    expect(isMoney(value)).toBe(false);
  });
});
