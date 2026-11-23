// @vitest-environment jsdom
// The options added so feature screens can use the shared components instead of raw controls (F-53).
import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Button, buttonClass, DateField, RadioGroup, Select, Table, type Column } from '@/components';

import { violations } from './a11y';

describe('Button link and bare kinds', () => {
  it('link reads as a link and bare has no look of its own; both press, disable and keep their name', async () => {
    const onClick = vi.fn();
    render(
      <>
        <Button kind="link" onClick={onClick}>Clear filters</Button>
        <Button kind="bare" className="as-chip" aria-pressed="true">Tola</Button>
        <Button kind="link" disabled>Show source</Button>
      </>,
    );
    expect(buttonClass('link')).toBe('psl-link cmp-linkbutton');
    expect(buttonClass('bare')).toBe('');
    const link = screen.getByRole('button', { name: 'Clear filters' });
    expect(link.className).toBe('psl-link cmp-linkbutton');
    expect(link.getAttribute('type')).toBe('button');
    fireEvent.click(link);
    expect(onClick).toHaveBeenCalledTimes(1);
    const chip = screen.getByRole('button', { name: 'Tola' });
    expect(chip.className).toBe('as-chip');
    expect(chip.getAttribute('aria-pressed')).toBe('true');
    expect((screen.getByRole('button', { name: 'Show source' }) as HTMLButtonElement).disabled).toBe(true);
    expect(await violations()).toEqual([]);
  });

  it('a bare button ignores presses while busy', () => {
    const onClick = vi.fn();
    render(<Button kind="bare" busy onClick={onClick}>Save</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('DateField with a time', () => {
  function When({ start = '' }: { start?: string }) {
    const [value, setValue] = useState(start);
    return (
      <>
        <DateField time label="When they responded" value={value} onChange={setValue} today="2026-11-13" />
        <output>{value || 'empty'}</output>
      </>
    );
  }
  const box = () => screen.getByLabelText('When they responded');
  const out = () => document.querySelector('output')!.textContent;
  const cell = (selector: string) => document.querySelector<HTMLElement>(`.cmp-dtpop ${selector}`)!;
  const done = () => fireEvent.click(screen.getByRole('button', { name: 'Done' }));

  it('D-158: one dropdown; the value stays empty until the date, hour and minute are all picked, then reads 2026-11-17T14:30', () => {
    render(<When />);
    expect(box().textContent).toBe('Choose date and time');
    fireEvent.click(box());
    expect(screen.getByRole('dialog', { name: 'Choose a date and time' })).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
    fireEvent.click(cell('[data-iso="2026-11-17"]'));
    expect(out()).toBe('empty');
    fireEvent.click(cell('[aria-label="Hour"] [data-value="14"]'));
    expect(out()).toBe('empty');
    fireEvent.click(cell('[aria-label="Minute"] [data-value="30"]'));
    expect(out()).toBe('2026-11-17T14:30');
    expect(cell('[aria-label="Hour"] [data-value="14"]').getAttribute('aria-selected')).toBe('true');
    fireEvent.click(cell('[aria-label="Hour"] [data-value="09"]'));
    expect(out()).toBe('2026-11-17T09:30');
    done();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(box().textContent).toBe('17 Nov 2026, 09:30');
    expect(document.activeElement).toBe(box());
  });

  it('a loaded value shows in the box and the panel opens on it; Done with only a date asks for the time', () => {
    const { unmount } = render(<When start="2026-04-10T11:00" />);
    expect(box().textContent).toBe('10 Apr 2026, 11:00');
    fireEvent.click(box());
    expect(screen.getByRole('grid').getAttribute('aria-label')).toBe('April 2026');
    expect(cell('[data-iso="2026-04-10"]').getAttribute('aria-selected')).toBe('true');
    expect(cell('[aria-label="Minute"] [data-value="00"]').getAttribute('aria-selected')).toBe('true');
    unmount();
    render(<When />);
    fireEvent.click(box());
    fireEvent.click(cell('[data-iso="2026-11-12"]'));
    done();
    expect(box().textContent).toBe('12 Nov 2026, --:--');
    expect(screen.getByText('Choose the time too.')).toBeTruthy();
    expect(box().getAttribute('aria-invalid')).toBe('true');
  });

  it('Use now fills the date and the time and closes; Esc closes without changing anything', () => {
    render(<When />);
    fireEvent.click(box());
    fireEvent.keyDown(cell('[aria-label="Hour"] [data-value="09"]'), { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(out()).toBe('empty');
    fireEvent.click(box());
    fireEvent.click(screen.getByRole('button', { name: 'Use now' }));
    expect(out()).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d$/);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('the hour and minute lists move with the arrow keys and choose with Enter', () => {
    render(<When start="2026-11-17T14:30" />);
    fireEvent.click(box());
    const fourteen = cell('[aria-label="Hour"] [data-value="14"]');
    fourteen.focus();
    fireEvent.keyDown(fourteen, { key: 'ArrowDown' });
    expect(document.activeElement?.textContent).toBe('15');
    fireEvent.keyDown(document.activeElement!, { key: 'Enter' });
    expect(out()).toBe('2026-11-17T15:30');
  });

  it('the open panel passes the accessibility check', async () => {
    render(<When start="2026-11-17T14:30" />);
    fireEvent.click(box());
    expect(await violations()).toEqual([]);
  });

  it('without time the field is the typed date field, as before', () => {
    render(<DateField label="Payment date" value="" onChange={() => {}} />);
    expect(screen.getByRole('textbox', { name: 'Payment date' })).toBeTruthy();
    expect(screen.queryByRole('listbox', { name: 'Hour' })).toBeNull();
  });

  it('hideLabel keeps the label for assistive technology but does not draw it', async () => {
    render(<DateField time hideLabel label="When they replied" value="" onChange={() => {}} />);
    expect(screen.getByText('When they replied').className).toBe('psl-label cmp-sr');
    expect(await violations()).toEqual([]);
  });
});

describe('Select hideLabel', () => {
  it('names the combobox without drawing the label', () => {
    render(<Select label="Who replied" hideLabel placeholder="Choose…" options={[{ value: 'a', label: 'Ada' }]} value={undefined} onChange={() => {}} />);
    expect(screen.getByText('Who replied').className).toBe('psl-label cmp-sr');
    expect(screen.getByRole('combobox', { name: 'Who replied' })).toBeTruthy();
  });
});

describe('RadioGroup hideLegend and disabled', () => {
  it('the legend is read but not drawn, and a disabled group cannot be chosen', () => {
    const onChange = vi.fn();
    render(<RadioGroup legend="Confirm what happened" hideLegend disabled options={[{ value: 'a', label: 'It arrived' }, { value: 'b', label: 'It did not' }]} value="a" onChange={onChange} />);
    expect(screen.getByText('Confirm what happened').className).toBe('psl-label cmp-sr');
    const radios = screen.getAllByRole('radio') as HTMLInputElement[];
    expect(radios.every((r) => r.disabled)).toBe(true);
    expect(radios[0].checked).toBe(true);
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe('Table leading column, full-width rows, hidden headers and frame class', () => {
  type Row = { id: string; name: string; locked?: boolean };
  const rows: Row[] = [
    { id: 'a', name: 'First' },
    { id: 'b', name: 'Hidden', locked: true },
  ];
  const columns: Column<Row>[] = [
    { key: 'name', header: 'NAME', cell: (r) => r.name },
    { key: 'steps', header: 'Steps', hideHeader: true, className: 'steps', cell: () => <button type="button">Do it</button> },
  ];

  it('draws the screen-filled first column, a full-width row, the data-label on cells and the frame class', async () => {
    render(
      <Table
        caption="Requirements"
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        empty="None"
        wrapClassName="ws-tablewrap"
        tableClassName="ws-table"
        leading={{ header: <span className="cmp-sr">Select</span>, headerClassName: 'ws-selectall', cell: (r) => <input type="checkbox" aria-label={`Select ${r.name}`} /> }}
        fullRow={(r) => (r.locked ? 'You cannot see this one.' : undefined)}
      />,
    );
    const frame = screen.getByRole('region', { name: 'Requirements' });
    expect(frame.className).toBe('psl-tablewrap ws-tablewrap');
    const table = within(frame).getByRole('table');
    expect(table.className).toBe('psl-table ws-table');
    const heads = within(table).getAllByRole('columnheader');
    expect(heads.map((h) => h.textContent)).toEqual(['Select', 'NAME', 'Steps']);
    expect(heads[0].className).toBe('psl-check-cell ws-selectall');
    expect(heads[2].querySelector('.cmp-sr')?.textContent).toBe('Steps');
    expect(within(table).getByRole('checkbox', { name: 'Select First' })).toBeTruthy();
    expect(within(table).getByText('First').getAttribute('data-label')).toBe('NAME');
    expect(within(table).getByText('First').closest('td')!.nextElementSibling!.className).toBe('steps');
    const full = within(table).getByText('You cannot see this one.').closest('td')!;
    expect(full.getAttribute('colspan')).toBe('3');
    expect(within(table).queryByText('Hidden')).toBeNull();
    expect(await violations()).toEqual([]);
  });
});
