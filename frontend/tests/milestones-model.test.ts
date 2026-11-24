import { describe, expect, it } from 'vitest';

import { changeText, completedText, completionFor, completionText, contractStages, dueText, hasChanges, isCompletion, isCompletions, recordedByText, type CompletionRow } from '@/features/projects/milestonesModel';
import type { MoneyItem } from '@/features/projects/moneyModel';

const item = (over: Partial<MoneyItem> = {}): MoneyItem => ({
  key: 'k', label: 'Stage', amount: '1.00', currency: 'NGN', due_date: null, milestone_id: null, stage_position: null, completed_at: null, contract_stage: true, missing_reason: null, invoices: [], sources: [], changes: [], ...over,
});
const row = (over: Partial<CompletionRow> = {}): CompletionRow => ({
  title: 'UAT sign-off', state: 'Completion recorded', state_code: 'recorded', detail: 'Tunde Bello', at: '2026-11-11T10:00:00Z', due: null, severity: null, owner: null, django_url: '/d', record_id: 7, api_url: null, reference: null, age_days: null, origin_meeting: null, ...over,
});
const section = (over: Record<string, unknown> = {}) => ({ key: 'completions', title: 'Recorded completions', items: [row()], page: 1, has_more: false, django_url: '/d', api_url: null, total: 1, counts: null, ...over });
const tab = (sections: unknown[] = [section()]) => ({ case_id: 'c', tab: 'milestones', sections, as_of: '2026-11-12T15:40:00Z' });

describe('completion, due and recorded-by text follow their own fields', () => {
  it('Done <date> from completed_at, Not completed when null, never from a due date or an invoice', () => {
    expect(completionText(item({ completed_at: '2026-10-27T10:00:00Z' }))).toBe('Done 27 Oct');
    expect(completionText(item({ completed_at: null, due_date: '2020-01-01', invoices: [{ id: 1, reference: 'I', version: 1, currency: 'NGN', paid: '1.00', owed: '0.00', status: 'Delivered', at: 'x', api_url: 'x' }] }))).toBe('Not completed');
  });

  it('Due <date> only with a due date, and it is never compared with today', () => {
    expect(dueText(item({ due_date: '2020-01-30' }))).toBe('Due 30 Jan');
    expect(dueText(item({ due_date: null }))).toBeUndefined();
  });

  it('Recorded by <detail>, nothing when the row does not say', () => {
    expect(recordedByText(row())).toBe('Recorded by Tunde Bello');
    expect(recordedByText(row({ detail: null }))).toBeUndefined();
    expect(completedText({ completed_at: '2026-11-11T10:00:00Z' })).toBe('Completed 11 Nov');
  });
});

describe('the join runs only through milestone_id', () => {
  it('a stage matches the completion with the same record_id', () => {
    expect(completionFor(item({ milestone_id: 7 }), [row({ record_id: 6 }), row({ record_id: 7 })])?.record_id).toBe(7);
  });

  it('a same-name completion with another id is not joined, and a null milestone_id joins nothing', () => {
    const same = row({ title: 'Stage', record_id: 9 });
    expect(completionFor(item({ label: 'Stage', milestone_id: 7 }), [same])).toBeUndefined();
    expect(completionFor(item({ label: 'Stage', milestone_id: null, completed_at: same.at }), [same, row({ record_id: 0 })])).toBeUndefined();
  });
});

describe('stages and changes', () => {
  it('keeps only contract stages, in order', () => {
    expect(contractStages([item({ key: 'b' }), item({ key: 'x', contract_stage: false }), item({ key: 'a' })]).map((i) => i.key)).toEqual(['b', 'a']);
  });

  it('the CHANGES column shows only when a stage has a change; the change is its reference and note', () => {
    const change = { link_id: 1, version_id: 2, reference: 'CHG-0007', number: 2, note: 'Extra scope', plan_id: 3, additional_amount: null, api_url: '/x' } as const;
    expect(hasChanges([item(), item({ changes: [] })])).toBe(false);
    expect(hasChanges([item(), item({ changes: [change] })])).toBe(true);
    expect(changeText(change)).toBe('CHG-0007 · Extra scope');
  });
});

describe('guards', () => {
  it('finds the completions as the only section, whatever its title or key', () => {
    expect(isCompletions(tab())).toBe(true);
    expect(isCompletions(tab([section({ title: 'Something else', key: 'other' })]))).toBe(true);
    expect(isCompletions(tab([]))).toBe(true);
    expect(isCompletions(tab([section(), section()]))).toBe(false);
  });

  it.each([
    ['null', null],
    ['no as_of', { ...tab(), as_of: undefined }],
    ['items not a list', tab([section({ items: {} })])],
    ['a row without a record_id', tab([section({ items: [{ ...row(), record_id: 'x' }] })])],
    ['has_more missing', tab([section({ has_more: undefined })])],
  ])('rejects %s', (_name, value) => {
    expect(isCompletions(value)).toBe(false);
  });

  it('the one-completion body needs id, name, date and proof version', () => {
    expect(isCompletion({ id: 1, name: 'n', completed_at: 'x', evidence_id: 2, proof_version: 3 })).toBe(true);
    expect(isCompletion({ id: 1, name: 'n', completed_at: 'x', evidence_id: 2 })).toBe(false);
    expect(isCompletion(null)).toBe(false);
  });
});
