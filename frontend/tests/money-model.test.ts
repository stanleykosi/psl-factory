import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { amountText, figureOf, figureTitle, invoiceText, isReport, moneyViewOf, PAID_WORDS, paidWords, valuesDiffer, type MoneyRow, type Report } from '@/features/projects/moneyModel';

// F-26 money model: guards, the paid words in one place, amounts as text only. No money is computed anywhere.
const fixture = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8'));
const NGN = (amount: string) => ({ amount, currency: 'NGN', unknown: false });

describe('amounts are formatted text, never numbers (Exact decimals)', () => {
  it('two decimals with ₦, every digit kept, other currencies by code', () => {
    expect(amountText(NGN('4250000.00'))).toBe('₦4,250,000.00');
    expect(amountText(NGN('3000000.00'))).toBe('₦3,000,000.00');
    expect(amountText({ amount: '1200.00', currency: 'USD', unknown: false })).toBe('1,200.00 USD');
    // 19 digits: a float would print 9223372036854775808.
    expect(amountText(NGN('9223372036854775807.00'))).toBe('₦9,223,372,036,854,775,807.00');
    expect(amountText(NGN('-250.50'))).toBe('-₦250.50');
  });

  it('Unknown is not zero: unknown, no amount or an unreadable amount give no text (the caller shows Unknown)', () => {
    expect(amountText({ currency: 'NGN', unknown: true })).toBeUndefined();
    expect(amountText({ amount: '4250000.00', currency: 'NGN', unknown: true })).toBeUndefined();
    expect(amountText({ currency: 'NGN', unknown: false })).toBeUndefined();
    expect(amountText({ amount: 'NaN', currency: 'NGN', unknown: false })).toBeUndefined();
    expect(amountText({ amount: 'abc', currency: 'USD', unknown: false })).toBeUndefined();
    expect(figureTitle(undefined)).toBe('Where this figure comes from');
  });
});

describe('the paid words come from one table (INV-FACTS)', () => {
  it('every contract status has its words; a status outside the enum shows its raw value', () => {
    expect(PAID_WORDS).toEqual({ paid: 'Paid', part_paid: 'Part paid', not_paid: 'Not paid', not_due: '—', finance_tracks: 'Finance tracks', unknown: 'Unknown' });
    expect(paidWords('finance_tracks')).toBe('Finance tracks');
    expect(paidWords('written_off')).toBe('written_off');
    expect(paidWords('toString')).toBe('toString');
  });

  it('the invoice cell reads only invoice fields: the composed status, else the reference', () => {
    const row = (extra: Partial<MoneyRow>): MoneyRow => ({ position: 1, stage: 'S', amount: NGN('1.00'), ...extra });
    expect(invoiceText(row({ invoice_status: 'Verified 03 Nov', invoice: { reference: 'INV-0398' } }))).toBe('Verified 03 Nov');
    expect(invoiceText(row({ invoice: { reference: 'INV-0503' } }))).toBe('INV-0503');
    expect(invoiceText(row({ paid: { status: 'paid' } }))).toBeUndefined();
  });
});

describe('guards: the money body and the report', () => {
  it('P-0101: four rows in position order, the report id and the time', () => {
    const view = moneyViewOf(fixture('projects/money/P-0101.json'))!;
    expect(view.rows.map((r) => r.stage)).toEqual(['Stage 1 · kick-off', 'Stage 2 · UAT', 'Stage 3 · go-live', 'Stage 4 · hypercare']);
    expect(view.reportId).toBe('R-0101');
    expect(view.asOf).toBe('2026-11-12T15:40:00Z');
  });

  it('P-0102 rows sent out of order are shown by position; the input is not changed', () => {
    const body = fixture('projects/money/P-0102.json');
    const sent = body.money.map((r: MoneyRow) => r.position);
    expect(moneyViewOf(body)!.rows.map((r) => r.position)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(body.money.map((r: MoneyRow) => r.position)).toEqual(sent);
  });

  it('a body without money, or with a malformed row, is refused whole; items are never read', () => {
    const rows = fixture('projects/money/P-0101.json').money;
    expect(moneyViewOf({ items: rows, as_of: 'x' })).toBeNull();
    expect(moneyViewOf({ money: [...rows, { position: '5', stage: 'x', amount: NGN('1.00') }] })).toBeNull();
    expect(moneyViewOf({ money: [{ position: 1, stage: 'x', amount: { amount: '1.00' } }] })).toBeNull();
    expect(moneyViewOf({ money: [{ position: 1, stage: 'x' }] })).toBeNull();
    expect(moneyViewOf({ money: [{ position: 1.5, stage: 'x', amount: NGN('1.00') }] })).toBeNull();
    expect(moneyViewOf(null)).toBeNull();
    expect(moneyViewOf({ money: [], items: [] })).toEqual({ rows: [], reportId: undefined, asOf: undefined });
  });

  it('TECH-1-1: amounts must be text; invoice and paid fields must have the shape they are drawn with', () => {
    const row = { position: 1, stage: 'S', amount: NGN('1.00') };
    expect(moneyViewOf({ money: [{ ...row, amount: { amount: 4250000, currency: 'NGN', unknown: false } }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, paid: { status: 'part_paid', owed: { amount: 5, currency: 'NGN', unknown: false } } }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, paid: { status: 'part_paid', owed: { currency: 'NGN' } } }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, paid: {} }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, invoice: { work_id: 'W-1' } }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, invoice_status: 3 }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, amount_note: {} }] })).toBeNull();
    expect(moneyViewOf({ money: [{ ...row, paid: { status: 'part_paid', owed: { currency: 'NGN', unknown: true } } }] })!.rows).toHaveLength(1);
  });

  it('TECH-1-1: a report figure needs a sources array of text and well-formed source details', () => {
    const figure = { id: 'F', label: 'x', value: NGN('1.00'), sources: ['a'] };
    expect(isReport({ figures: [figure] })).toBe(true);
    expect(isReport({ figures: [{ ...figure, sources: undefined }] })).toBe(false);
    expect(isReport({ figures: [{ ...figure, sources: [1] }] })).toBe(false);
    expect(isReport({ figures: [{ ...figure, value: { amount: 1, currency: 'NGN', unknown: false } }] })).toBe(false);
    expect(isReport({ figures: [{ ...figure, source_details: {} }] })).toBe(false);
    expect(isReport({ figures: [{ ...figure, source_details: [{ label: 'x' }] }] })).toBe(false);
    expect(isReport({ figures: [{ ...figure, source_details: [{ label: 'x', reference: 'R', kind: 'rule' }] }] })).toBe(true);
  });

  it('a report needs figures with a label and a value', () => {
    expect(isReport(fixture('reports/R-0101.json'))).toBe(true);
    expect(isReport({ report_id: 'R', title: 'T' })).toBe(false);
    expect(isReport({ figures: [{ label: 'x', value: { amount: '1.00' } }] })).toBe(false);
    expect(isReport({ figures: [null] })).toBe(false);
  });
});

describe('the drill-down joins by id and compares as sent', () => {
  const r0101 = fixture('reports/R-0101.json') as Report;
  it('figures by id; no id or an unmatched id finds nothing', () => {
    expect(figureOf(r0101, 'FIG-0101-S2')?.label).toBe('Stage 2 · UAT amount');
    expect(figureOf(r0101, 'FIG-0101-S9')).toBeUndefined();
    expect(figureOf(r0101, undefined)).toBeUndefined();
    expect(figureOf(undefined, 'FIG-0101-S2')).toBeUndefined();
  });

  it('the title uses the figure value', () => {
    expect(figureTitle(figureOf(r0101, 'FIG-0101-S2'))).toBe('Where ₦4,250,000.00 comes from');
    expect(figureTitle({ label: 'x', value: { currency: 'NGN', unknown: true }, sources: [] })).toBe('Where this figure comes from');
  });

  it('differ compares unknown, currency and the amount text exactly, with no number conversion', () => {
    expect(valuesDiffer(NGN('4250000.00'), NGN('4250000.00'))).toBe(false);
    expect(valuesDiffer(NGN('2500000.00'), NGN('2400000.00'))).toBe(true);
    // Same number, different text: shown as a difference rather than converted.
    expect(valuesDiffer(NGN('4250000.00'), NGN('4250000.0'))).toBe(true);
    expect(valuesDiffer(NGN('1200.00'), { amount: '1200.00', currency: 'USD', unknown: false })).toBe(true);
    expect(valuesDiffer({ currency: 'NGN', unknown: true }, { currency: 'NGN', unknown: true })).toBe(false);
    expect(valuesDiffer({ currency: 'NGN', unknown: true }, NGN('1.00'))).toBe(true);
  });
});
