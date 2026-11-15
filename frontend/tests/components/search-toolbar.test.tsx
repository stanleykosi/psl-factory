// @vitest-environment jsdom
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Checkbox, FilterPanel, ListToolbar, SearchField } from '@/components';

import { violations } from './a11y';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function Search({ onSearch }: { onSearch: (q: string) => void }) {
  const [q, setQ] = useState('');
  return <SearchField label="Search work" placeholder="Search work, projects or references" value={q} onChange={setQ} onSearch={onSearch} />;
}

describe('SearchField', () => {
  it('searches after 2 characters and a 200ms pause; clear button returns focus', async () => {
    const onSearch = vi.fn();
    render(<Search onSearch={onSearch} />);
    const box = screen.getByRole('searchbox', { name: 'Search work' });
    expect(box.className).toBe('psl-input cmp-search');
    expect(screen.queryByRole('button', { name: 'Clear search' })).toBeNull();
    fireEvent.change(box, { target: { value: 'I' } });
    act(() => vi.advanceTimersByTime(500));
    expect(onSearch).not.toHaveBeenCalled();
    fireEvent.change(box, { target: { value: 'IN' } });
    act(() => vi.advanceTimersByTime(199));
    expect(onSearch).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onSearch).toHaveBeenCalledWith('IN');
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    act(() => vi.advanceTimersByTime(0));
    expect(onSearch).toHaveBeenLastCalledWith('');
    expect(document.activeElement).toBe(box);
    vi.useRealTimers();
    expect(await violations()).toEqual([]);
  });
});

function Toolbar() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [line, setLine] = useState(true);
  return (
    <ListToolbar
      search={{ label: 'Search work', placeholder: 'Search work, projects or references', value: q, onChange: setQ }}
      filterCount={line ? 1 : 0}
      filterOpen={open}
      onFilterToggle={() => setOpen((o) => !o)}
      resultText={line ? '4 of 32' : '32 items'}
      chips={line ? [{ key: 'line', name: 'Line', value: 'Invoice preparation', onRemove: () => setLine(false) }] : []}
      onClearAll={() => setLine(false)}
      filterPanel={
        <FilterPanel applyLabel="Show 4 results" onApply={() => setOpen(false)} onClear={() => setLine(false)} onClose={() => setOpen(false)}>
          <Checkbox label="Invoice preparation and delivery" checked={line} onChange={() => setLine(!line)} />
        </FilterPanel>
      }
    />
  );
}

describe('ListToolbar and FilterPanel', () => {
  it('filter button shows how many are on; chips remove; the panel opens, applies and closes on Esc', async () => {
    vi.useRealTimers();
    render(<Toolbar />);
    const filter = screen.getByRole('button', { name: /^Filter/ });
    expect(filter.querySelector('.psl-badge--signal')?.textContent).toBe('1');
    // the count is a polite live region without the status role (it reads as the page's text, as the boards draw it)
    const count = document.querySelector('.psl-resultcount') as HTMLElement;
    expect(count.getAttribute('aria-live')).toBe('polite');
    expect(count.textContent).toBe('4 of 32');
    expect(screen.getByRole('button', { name: 'Remove Line filter' })).toBeTruthy();
    fireEvent.click(filter);
    const panel = screen.getByRole('dialog', { name: 'Filter' });
    // focus moves to the panel's first field (the board's filter panel, D-93)
    expect(document.activeElement).toBe(within(panel).getByRole('checkbox', { name: 'Invoice preparation and delivery' }));
    // the board's foot: Clear beside the dark "Show N results"
    expect(within(panel).getByRole('button', { name: 'Clear' }).className).toBe('psl-btn psl-btn--secondary psl-btn--lg psl-btn--block');
    expect(within(panel).getByRole('button', { name: 'Show 4 results' }).className).toBe('psl-btn psl-btn--dark psl-btn--lg psl-btn--block');
    expect(await violations()).toEqual([]);
    fireEvent.keyDown(panel, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(filter);
    fireEvent.click(filter);
    fireEvent.click(screen.getByRole('button', { name: 'Show 4 results' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Remove Line filter' }));
    expect(count.textContent).toBe('32 items');
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull();
  });
});
