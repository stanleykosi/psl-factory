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

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** Picks a date and time ("2026-11-11T16:20") in a DateField with a time (D-158): open it, move to the month, choose
 *  the day, the hour and the minute, then Done. */
export function setWhen(label: string, value: string, scope: Scope = screen) {
  const [day, clock] = value.split('T');
  const [hour, minute] = clock.split(':');
  const [y, m] = day.split('-').map(Number);
  const box = scope.getByLabelText(label);
  if (box.getAttribute('aria-expanded') !== 'true') fireEvent.click(box);
  const panel = box.closest('.cmp-anchor')!.querySelector<HTMLElement>('.cmp-dtpop')!;
  const want = y * 12 + (m - 1);
  for (let step = 0; step < 240; step += 1) {
    const [name, year] = panel.querySelector('[role="grid"]')!.getAttribute('aria-label')!.split(' ');
    const shown = Number(year) * 12 + MONTHS.indexOf(name);
    if (shown === want) break;
    fireEvent.click(panel.querySelector(`[aria-label="${shown > want ? 'Previous month' : 'Next month'}"]`)!);
  }
  fireEvent.click(panel.querySelector(`[data-iso="${day}"]`)!);
  fireEvent.click(panel.querySelector(`[aria-label="Hour"] [data-value="${hour}"]`)!);
  fireEvent.click(panel.querySelector(`[aria-label="Minute"] [data-value="${minute}"]`)!);
  fireEvent.click([...panel.querySelectorAll('button')].find((b) => b.textContent === 'Done')!);
}
