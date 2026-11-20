// Drives the shared Select and DateField from component tests (they replaced native select and datetime-local).
import { fireEvent, screen } from '@testing-library/react';

type Scope = Pick<typeof screen, 'getByRole' | 'getByLabelText'>;

/** Opens the Select named `label` and chooses the option with this value. */
export function pick(label: string | RegExp, value: string, scope: Scope = screen) {
  const box = scope.getByRole('combobox', { name: label });
  fireEvent.click(box);
  const option = document.querySelector(`[role="listbox"] [data-value="${value}"]`);
  if (!option) throw new Error(`No option ${value} in ${String(label)}`);
  fireEvent.click(option);
}

/** The options of the Select named `label`, as { value, text }, then closes it. */
export function optionsOf(label: string | RegExp, scope: Scope = screen) {
  const box = scope.getByRole('combobox', { name: label });
  fireEvent.click(box);
  const options = [...document.querySelectorAll('[role="listbox"] [role="option"]')].map((o) => ({ value: o.getAttribute('data-value')!, text: o.firstChild?.textContent ?? '' }));
  fireEvent.click(box);
  return options;
}

const dayText = (iso: string) => {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
};

/** Types a date (2026-12-12) into a DateField and leaves it, as a person does. */
export function setDate(label: string | RegExp, iso: string, scope: Scope = screen) {
  const input = scope.getByLabelText(label);
  fireEvent.change(input, { target: { value: dayText(iso) } });
  fireEvent.blur(input);
}

/** Fills a DateField with a time: the date and the time ("2026-11-11T16:20"). */
export function setWhen(label: string, value: string, scope: Scope = screen) {
  const [day, time] = value.split('T');
  setDate(label, day, scope);
  fireEvent.change(scope.getByLabelText(`${label}, time`), { target: { value: time } });
}
