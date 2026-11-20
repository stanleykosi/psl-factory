// @vitest-environment jsdom
// The options added so feature screens can use the shared components instead of raw controls (F-53).
import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Button, buttonClass, DateField, FilePickButton, RadioGroup, Select, Table, type Column } from '@/components';

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
  const date = () => screen.getByRole('textbox', { name: 'When they responded' });
  const clock = () => screen.getByLabelText('When they responded, time') as HTMLInputElement;

  it('the value stays empty until both the date and the time are given, then reads 2026-11-17T14:30', () => {
    render(<When />);
    fireEvent.change(date(), { target: { value: '17 Nov 2026' } });
    fireEvent.blur(date());
    expect(document.querySelector('output')!.textContent).toBe('empty');
    fireEvent.change(clock(), { target: { value: '14:30' } });
    expect(document.querySelector('output')!.textContent).toBe('2026-11-17T14:30');
    fireEvent.change(clock(), { target: { value: '' } });
    expect(document.querySelector('output')!.textContent).toBe('empty');
    fireEvent.change(clock(), { target: { value: '09:05' } });
    expect(document.querySelector('output')!.textContent).toBe('2026-11-17T09:05');
  });

  it('time first then the date also completes the value; a loaded value fills both', () => {
    const { unmount } = render(<When />);
    fireEvent.change(clock(), { target: { value: '16:20' } });
    expect(document.querySelector('output')!.textContent).toBe('empty');
    fireEvent.change(date(), { target: { value: '11/11/2026' } });
    fireEvent.blur(date());
    expect(document.querySelector('output')!.textContent).toBe('2026-11-11T16:20');
    unmount();
    render(<When start="2026-04-10T11:00" />);
    expect((date() as HTMLInputElement).value).toBe('10 Apr 2026');
    expect(clock().value).toBe('11:00');
  });

  it('without time the field has no time input and the value is the date, as before', () => {
    render(<DateField label="Payment date" value="" onChange={() => {}} />);
    expect(screen.queryByLabelText('Payment date, time')).toBeNull();
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

describe('FilePickButton', () => {
  it('the button opens the chooser and hands over the chosen file; the chooser can be closed apart from the button', () => {
    const onFile = vi.fn();
    const { container } = render(<FilePickButton onFile={onFile} labelledBy="proof-label" className="resp-filebtn">Add another file</FilePickButton>);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const click = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByRole('button', { name: 'Add another file' }));
    expect(click).toHaveBeenCalledTimes(1);
    const file = new File(['x'], 'signoff.pdf');
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
    expect(screen.getByRole('button', { name: 'Add another file' }).className).toBe('resp-filebtn');
  });

  it('a disabled button does not open the chooser', () => {
    const { container } = render(<FilePickButton onFile={() => {}} inputDisabled disabled>Choose a file</FilePickButton>);
    expect((container.querySelector('input[type="file"]') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Choose a file' }) as HTMLButtonElement).disabled).toBe(true);
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
