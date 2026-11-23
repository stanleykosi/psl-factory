// @vitest-environment jsdom
// F-103: the cash forecast read mapping (periods, items, matches, disclosure, delivery, month actuals) and its error words.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ApiError } from '@/api/errors';
import type { LiveForecast, LiveForecastMonth } from '@/api/types';
import { forecastAdapter, forecastReadSections } from '@/features/forecast/forecastAdapter';
import { entryText, errorWords, forecastSections, isUncertain, monthIsCut, monthSections, moneyCell, periodSections } from '@/features/forecast/labels';
import { adapterFor } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';

// @ts-expect-error plain ESM module without type declarations
import { forecastLive } from '../mock/forecast-live.mjs';

const get = (path: string) => forecastLive({ method: 'get', url: new URL(path, 'http://m.local'), persona: 'finance_lead' }) as [number, never];
const forecast = (id: number) => get(`/api/v1/work/${id}/forecast`)[1] as LiveForecast;
const month = (id: number, m: string) => get(`/api/v1/work/${id}/forecast/actuals/${m}`)[1] as LiveForecastMonth;
const draw = (sections: Section[]) => render(<>{sections.map((s) => <SectionView key={s.key} section={s} level={2} />)}</>);
const base = forecast(4301);
const withPeriods = (periods: unknown[]) => ({ ...base.result!, periods } as NonNullable<LiveForecast['result']>);

describe('periods (AC3)', () => {
  it('a missing, null and "0.00" amount read Unknown, Unknown and the zero amount', () => {
    expect(moneyCell('c', undefined, 'NGN').money).toEqual({ currency: 'NGN', unknown: true });
    expect(moneyCell('c', null, 'NGN').money).toEqual({ currency: 'NGN', unknown: true });
    expect(moneyCell('c', '0.00', 'NGN').money).toEqual({ amount: '0.00', currency: 'NGN', unknown: false });
    draw(periodSections(withPeriods([{ month: '2026-07', opening: '1.00', inflow: undefined, outflow: '0.00', closing: null }]), false));
    expect(screen.getAllByText('Unknown')).toHaveLength(2);
    expect(screen.getByText('₦0.00')).toBeTruthy();
  });

  it('draws the six months of 4301 with the first closing Unknown and sums nothing', () => {
    draw(periodSections(base.result!, false));
    expect(screen.getAllByRole('row')).toHaveLength(7);
    expect(screen.getAllByText('Unknown')).toHaveLength(1);
  });

  it('a column only where a period carries the field; an unrecognised period is listed by its keys', () => {
    const [table, other] = periodSections(withPeriods([{ month: '2026-07', closing: '5.00' }, { weird: 1, shape: 2 }]), false);
    expect(table.columns!.map((c) => c.key)).toEqual(['month', 'closing']);
    expect(other.items[0].text).toBe('Period data: weird, shape');
    expect(periodSections(withPeriods([{ staff_name: 'x' }]), true)[0].items[0].text).toBe('A period is not shown here.');
  });
});

describe('sections (AC4, AC7, AC8-AC11)', () => {
  it('result null: stage, finding, no figures, no table, no delivery, one "No actuals matched yet."', () => {
    const sections = forecastSections(forecast(4303));
    expect(sections.some((s) => s.kind === 'table')).toBe(false);
    expect(sections.some((s) => s.key === 'delivery')).toBe(false);
    draw(sections);
    expect(screen.getByText('Stage: Investigating')).toBeTruthy();
    expect(screen.getByText('Chidi is reading the opening balances.')).toBeTruthy();
    expect(screen.getByText('No forecast figures yet.')).toBeTruthy();
    expect(screen.getAllByText('No actuals matched yet.')).toHaveLength(1);
  });

  it('a job with no receipt reads "No receipt yet", never received; a receipt reads "Receipt n"', () => {
    draw(forecastSections(forecast(4305)));
    expect(screen.getByText(/No receipt yet/)).toBeTruthy();
    expect(screen.queryByText(/received|✓/i)).toBeNull();
    expect(screen.getByText('Outcome not known')).toBeTruthy();
    expect(screen.getByText('Restart allowed under rule 12')).toBeTruthy();
    expect(screen.getByText(/Nothing has been resent from this page\./)).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('delivered with a receipt is not uncertain', () => {
    expect(isUncertain(forecast(4301))).toBe(false);
    expect(isUncertain({ ...forecast(4301), observation: { id: 1, outcome: 'unknown', has_proof: false } })).toBe(true);
    draw(forecastSections(forecast(4301)));
    expect(screen.getByText(/Receipt 9/)).toBeTruthy();
  });

  it('the review board has "Reviewed by Finance" and no reviewer-not-set text or short money', () => {
    const { container } = draw(forecastSections(forecast(4302)));
    expect(screen.getByText('Reviewed by Finance')).toBeTruthy();
    expect(container.textContent).not.toMatch(/not set|\d[MK]\b/i);
  });
});

describe('group disclosure (AC9, AC10, AC11)', () => {
  it('shows the selected rows, fields, details and recipients as sent, read only', () => {
    const { container } = draw(forecastSections(forecast(4304)));
    for (const t of ['rent', 'loan', 'kind', 'amount', 'expected_on', 'entity', 'Recipient 3', 'Recipient 4']) expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Available' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Choices on file' })).toBeTruthy();
    expect(container.querySelectorAll('input, select, [role=checkbox], button')).toHaveLength(0);
  });

  it('the poisoned read draws the payroll key text only: no staff name, no pay, no items or actuals section', () => {
    const poisoned = forecast(4308);
    const sections = forecastSections(poisoned);
    const { container } = draw(sections);
    expect(screen.getAllByText('payroll-run-nov').length).toBeGreaterThan(0);
    expect(container.textContent).not.toMatch(/Ngozi|Nwosu|850,?000/);
    expect(JSON.stringify(sections)).not.toMatch(/Ngozi|Nwosu|\b850000\.00/);
    expect(sections.map((s) => s.key)).not.toContain('expected-items');
    expect(sections.map((s) => s.key)).not.toContain('matches');
  });

  it('an object entry keeps only its label or key; other fields never reach a section', () => {
    expect(entryText({ key: 'rent', staff_name: 'Ngozi', pay: '1.00' }, 'Row 1')).toBe('rent');
    expect(entryText({ staff_name: 'Ngozi', pay: '1.00' }, 'Row 1')).toBe('Row 1');
    const f = { ...forecast(4304), disclosure: { ...forecast(4304).disclosure!, selected_rows: [{ staff_name: 'Ngozi', pay: '9.00' }, { label: 'loan', pay: '9.00' }] as never } };
    const json = JSON.stringify(forecastSections(f));
    expect(json).not.toMatch(/Ngozi|9\.00/);
    expect(json).toContain('loan');
  });

  it('a group read with no disclosure draws no payroll or disclosure text', () => {
    const f = { ...forecast(4308), disclosure: null };
    const json = JSON.stringify(forecastSections(f));
    expect(json).not.toMatch(/payroll|Ngozi/);
    expect(forecastSections(f).some((s) => s.key.startsWith('disclosure'))).toBe(false);
  });
});

describe('month actuals (AC12-AC14)', () => {
  it('rows, actuals with direction and Verified, history; a null amount reads Unknown; a cut list says so', () => {
    const m = month(4301, '2026-11');
    draw(monthSections(m, 'NGN'));
    expect(screen.getByText('Actual 5 · In')).toBeTruthy();
    expect(screen.getByText('Actual 6 · Out')).toBeTruthy();
    expect(screen.getByText('Not verified')).toBeTruthy();
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
    expect(monthIsCut(m)).toBe(true);
    expect(monthIsCut(month(4301, '2026-09'))).toBe(false);
  });

  it('marks a reversed match; an empty month says so', () => {
    draw(monthSections(month(4301, '2026-09'), 'NGN'));
    expect(screen.getByText('Reversed')).toBeTruthy();
    draw(monthSections(month(4301, '2026-10'), 'NGN'));
    expect(screen.getByText('No actuals recorded for 2026-10.')).toBeTruthy();
    expect(get('/api/v1/work/4301/forecast/actuals/2026-12')[0]).toBe(404);
  });
});

describe('errors and the adapter (AC5, AC17, AC18)', () => {
  const err = (status: number, kind: ApiError['kind'], fields: { name: string; message: string }[] = []) => new ApiError(status, kind, 'x', 'server words', fields);
  it('maps each failure to its own words; the rest are left to the panel frame', () => {
    expect(errorWords(err(404, 'not_found'))).toBe('This record is unavailable.');
    expect(errorWords(err(403, 'csrf'))).toBe('Refresh your session and try again.');
    expect(errorWords(err(403, 'forbidden'))).not.toBe(errorWords(err(403, 'csrf')));
    expect(errorWords(err(409, 'stale'))).toBe('This changed while you were reading it. Reload.');
    expect(errorWords(err(422, 'invalid', [{ name: 'month', message: 'Bad month' }]))).toBe('Bad month');
    expect(errorWords(err(401, 'unauthenticated'))).toMatch(/Sign in/);
    expect(errorWords(err(503, 'server'))).toBeNull();
    expect(errorWords(err(0, 'network'))).toBeNull();
  });

  it('an error readback draws one note, not the forecast', () => {
    expect(forecastReadSections({ error: { words: 'This record is unavailable.', signIn: false } })).toEqual([{ key: 'error', kind: 'text', note: 'This record is unavailable.', items: [] }]);
  });

  it('registers under the live panel key, sends no command, and never renders a revision', () => {
    expect(adapterFor('forecast')).toBe(forecastAdapter);
    expect(forecastAdapter.commands).toBeUndefined();
    const { container } = draw(forecastSections({ ...forecast(4301), expected_revision: null as never, case_revision: null as never }));
    expect(container.textContent).not.toMatch(/revision/i);
  });
});
