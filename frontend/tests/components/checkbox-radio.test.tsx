// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Checkbox, RadioGroup } from '@/components';

import { violations } from './a11y';

describe('Checkbox', () => {
  it('the label is the target; mixed, error and disabled states', async () => {
    render(
      <>
        <Checkbox label="Invoice preparation" defaultChecked />
        <Checkbox label="Select all · 3 of 8" mixed />
        <Checkbox label="I confirm this proof is genuine" error="Confirm before recording." />
        <Checkbox label="Payroll" detail="Restricted to HR" disabled />
      </>,
    );
    const mixed = screen.getByRole('checkbox', { name: 'Select all · 3 of 8' }) as HTMLInputElement;
    expect(mixed.indeterminate).toBe(true);
    const confirm = screen.getByRole('checkbox', { name: 'I confirm this proof is genuine' });
    expect(confirm.closest('label')?.className).toBe('psl-check cmp-check is-error');
    expect(document.getElementById(confirm.getAttribute('aria-describedby') ?? '')?.textContent).toBe('Confirm before recording.');
    expect(screen.getByRole('checkbox', { name: /Payroll/ }).closest('label')?.className).toBe('psl-check cmp-check is-disabled');
    expect(screen.getByText('Restricted to HR').tagName).toBe('SMALL');
    fireEvent.click(screen.getByText('Invoice preparation'));
    expect((screen.getByRole('checkbox', { name: 'Invoice preparation' }) as HTMLInputElement).checked).toBe(false);
    expect(await violations()).toEqual([]);
  });
});

function Outcome({ cards = false }) {
  const [value, setValue] = useState<string | undefined>(undefined);
  return (
    <RadioGroup
      legend="What happens to the balance"
      cards={cards}
      value={value}
      onChange={setValue}
      error={value ? undefined : 'Choose one option to continue.'}
      options={[
        { value: 'keep', label: 'Keep it owed', detail: 'The ₦500,000.00 stays on INV-0398.' },
        { value: 'exception', label: 'Approve an exception', detail: 'It doesn’t erase the debt.' },
        { value: 'writeoff', label: 'Write off', disabledReason: 'Not set up: needs a write-off rule from PSL.' },
      ]}
    />
  );
}

describe('RadioGroup', () => {
  it('nothing is preselected; choosing works; a disabled option says why', async () => {
    render(<Outcome />);
    const radios = screen.getAllByRole('radio') as HTMLInputElement[];
    expect(radios.some((r) => r.checked)).toBe(false);
    expect(radios[2].disabled).toBe(true);
    expect(screen.getByText('Not set up: needs a write-off rule from PSL.')).toBeTruthy();
    expect(screen.getByRole('group', { name: 'What happens to the balance' }).getAttribute('aria-describedby')).toBeTruthy();
    expect(radios[0].closest('label')?.className).toBe('psl-radio cmp-check is-error');
    expect(await violations()).toEqual([]);
    fireEvent.click(radios[1]);
    expect(radios[1].checked).toBe(true);
    expect(screen.queryByText('Choose one option to continue.')).toBeNull();
  });

  it('choice cards mark the chosen card', async () => {
    render(<Outcome cards />);
    fireEvent.click(screen.getByRole('radio', { name: /Keep it owed/ }));
    expect(screen.getByRole('radio', { name: /Keep it owed/ }).closest('label')?.className).toBe('psl-choice is-selected');
    expect(screen.getByText('Write off').tagName).toBe('STRONG');
    expect(await violations()).toEqual([]);
  });
});
