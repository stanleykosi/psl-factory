// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Button, Money, StateTag, Table, type Column, type Sort } from '@/components';

import { violations } from './a11y';

type Row = { ref: string; milestone: string; amount: string | null; current?: boolean };
const ROWS: Row[] = [
  { ref: 'INV-0412', milestone: 'Lagoon Health · stage 2', amount: '4250000' },
  { ref: 'INV-0391', milestone: 'Lagoon Health · stage 1', amount: null, current: true },
];
const COLUMNS: Column<Row>[] = [
  { key: 'ref', header: 'REFERENCE', cell: (r) => r.ref, mono: true },
  { key: 'milestone', header: 'MILESTONE', cell: (r) => r.milestone, sortable: true },
  { key: 'amount', header: 'AMOUNT ₦', cell: (r) => <Money value={r.amount} sign={false} />, num: true },
  { key: 'state', header: 'STATE', cell: () => <StateTag state="action_needed" /> },
];

function Invoices({ rows = ROWS }: { rows?: Row[] }) {
  const [selected, setSelected] = useState(new Set<string>());
  const [sort, setSort] = useState<Sort>({ key: 'milestone', dir: 'ascending' });
  return (
    <Table
      caption="Invoices"
      columns={COLUMNS}
      rows={rows}
      rowKey={(r) => r.ref}
      rowLabel={(r) => `Select ${r.ref}`}
      rowState={(r) => (r.current ? 'current' : undefined)}
      empty="No invoices yet for this project"
      sort={sort}
      onSort={() => setSort((s) => ({ key: s.key, dir: s.dir === 'ascending' ? 'descending' : 'ascending' }))}
      selected={selected}
      onSelect={setSelected}
      bulkActions={<Button kind="secondary" size="sm">Assign reviewer</Button>}
      footer={['Total of known amounts', '', <Money key="t" value="4250000" sign={false} />, '1 Unknown']}
    />
  );
}

describe('Table', () => {
  it('amounts right-aligned in mono, Unknown never 0; sorted column; current row; totals', async () => {
    render(<Invoices />);
    const table = screen.getByRole('table', { name: 'Invoices' });
    expect(table.className).toBe('psl-table');
    expect(table.parentElement?.className).toBe('psl-tablewrap');
    const unknownRow = screen.getByText('INV-0391').closest('tr') as HTMLElement;
    expect(unknownRow.className).toBe('is-current');
    expect(within(unknownRow).getByText('Unknown').className).toBe('psl-unknown');
    expect(screen.getAllByText('4,250,000.00')[0].closest('td')?.className).toBe('num');
    const sorted = screen.getByRole('columnheader', { name: /MILESTONE/ });
    expect(sorted.getAttribute('aria-sort')).toBe('ascending');
    fireEvent.click(within(sorted).getByRole('button'));
    expect(sorted.getAttribute('aria-sort')).toBe('descending');
    expect(table.querySelector('tfoot')?.textContent).toContain('Total of known amounts');
    expect(await violations()).toEqual([]);
  });

  it('select-all is mixed with some rows; bulk actions show once a row is chosen', async () => {
    render(<Invoices />);
    const all = screen.getByRole('checkbox', { name: 'Select all' }) as HTMLInputElement;
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select INV-0412' }));
    expect(all.indeterminate).toBe(true);
    expect(screen.getByText('INV-0412').closest('tr')?.className).toBe('is-selected');
    expect(screen.getByText('1 selected')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Assign reviewer' })).toBeTruthy();
    expect(await violations()).toEqual([]);
    fireEvent.click(all);
    expect(all.checked).toBe(true);
    expect(all.indeterminate).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Clear selection' }));
    expect(screen.queryByText(/selected/)).toBeNull();
  });

  it('empty is a sentence, never a blank grid', () => {
    render(<Invoices rows={[]} />);
    expect(screen.getByRole('cell', { name: 'No invoices yet for this project' })).toBeTruthy();
    expect(document.querySelector('tfoot')).toBeNull();
  });
});
