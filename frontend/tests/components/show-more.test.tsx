// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { ShowMore, Table, usePagedRows, type Column, type PageSize } from '@/components';

import { violations } from './a11y';

const noop = () => undefined;
const radio = (name: string) => screen.getByRole('radio', { name });

describe('ShowMore footer', () => {
  it('says "20 of 74 showing", "All 74 showing", or "20 showing" where the total is unknown', async () => {
    const { rerender } = render(<ShowMore shown={20} total={74} onMore={noop} size={20} onSize={noop} />);
    expect(screen.getByText('20 of 74 showing')).toBeTruthy();
    expect(await violations()).toEqual([]);
    rerender(<ShowMore shown={74} total={74} onMore={noop} size={50} onSize={noop} />);
    expect(screen.getByText('All 74 showing')).toBeTruthy();
    rerender(<ShowMore shown={20} hasMore onMore={noop} size={20} onSize={noop} />);
    expect(screen.getByText('20 showing')).toBeTruthy();
  });

  it('offers 10 / 20 / 50 as a segmented group (not a select), with the given size chosen', () => {
    render(<ShowMore shown={10} hasMore onMore={noop} size={10} onSize={noop} />);
    expect(screen.getByRole('radiogroup', { name: 'Rows per page' })).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(radio('10').getAttribute('aria-checked')).toBe('true');
    expect(radio('20').getAttribute('aria-checked')).toBe('false');
    expect(radio('50')).toBeTruthy();
  });

  it('choosing a rows-per-page option reports it; arrow keys move and choose', () => {
    const onSize = vi.fn();
    render(<ShowMore shown={10} hasMore onMore={noop} size={10} onSize={onSize} />);
    fireEvent.click(radio('20'));
    expect(onSize).toHaveBeenLastCalledWith(20);
    fireEvent.keyDown(radio('10'), { key: 'ArrowRight' });
    expect(onSize).toHaveBeenLastCalledWith(20);
  });

  it('Show more: a labelled button that goes busy, and is absent when every row shows', () => {
    const onMore = vi.fn();
    const { rerender } = render(<ShowMore shown={10} total={74} onMore={onMore} size={10} onSize={noop} />);
    fireEvent.click(screen.getByRole('button', { name: 'Show 10 more' }));
    expect(onMore).toHaveBeenCalled();
    rerender(<ShowMore shown={10} total={74} busy onMore={onMore} size={10} onSize={noop} />);
    expect(screen.getByRole('button', { name: /Loading/ }).getAttribute('aria-busy') ?? 'true').toBe('true');
    rerender(<ShowMore shown={74} total={74} onMore={onMore} size={50} onSize={noop} />);
    expect(screen.queryByRole('button', { name: /more/i })).toBeNull();
  });

  it('disables (does not hide) an option that would show nothing more', () => {
    const { rerender } = render(<ShowMore shown={3} total={3} onMore={noop} size={10} onSize={noop} />);
    expect(radio('20').getAttribute('aria-disabled')).toBe('true');
    expect(radio('50').getAttribute('aria-disabled')).toBe('true');
    expect(radio('10').getAttribute('aria-disabled')).toBeNull();
    rerender(<ShowMore shown={10} total={15} onMore={noop} size={10} onSize={noop} />);
    expect(radio('20').getAttribute('aria-disabled')).toBeNull();
    expect(radio('50').getAttribute('aria-disabled')).toBe('true');
    rerender(<ShowMore shown={10} hasMore onMore={noop} size={10} onSize={noop} />);
    expect(radio('50').getAttribute('aria-disabled')).toBeNull();
  });

  it('a disabled option cannot be chosen', () => {
    const onSize = vi.fn();
    render(<ShowMore shown={3} total={3} onMore={noop} size={10} onSize={onSize} />);
    fireEvent.click(radio('50'));
    expect(onSize).not.toHaveBeenCalled();
  });

  it('is drawn inside the table frame: the frame encloses the table and the footer', () => {
    const columns: Column<{ id: string }>[] = [{ key: 'id', header: 'ID', cell: (r) => r.id }];
    const { container } = render(<Table caption="Rows" columns={columns} rows={[{ id: 'a' }]} rowKey={(r) => r.id} empty="" paging={{ shown: 1, total: 1, onMore: noop, size: 10, onSize: noop }} />);
    const frame = container.querySelector('.psl-tableframe')!;
    expect(frame.querySelector('table')).toBeTruthy();
    expect(frame.querySelector('.psl-showmore')).toBeTruthy();
  });
});

type Item = { id: number };
const makeItems = (n: number): Item[] => Array.from({ length: n }, (_, i) => ({ id: i }));

/** A cursor list of `total` rows: the first fetch is 10, later ones append by cursor. `fetch` records each limit asked for. */
function Harness({ total, fetch }: { total: number; fetch: (limit: number) => void }) {
  const [loaded, setLoaded] = useState(10);
  const [busy, setBusy] = useState(false);
  const items = makeItems(Math.min(loaded, total));
  const { rows, paging } = usePagedRows<Item>({
    items,
    next: loaded < total,
    busy,
    loadMore: (limit: PageSize) => {
      fetch(limit);
      setBusy(true);
      setTimeout(() => {
        setLoaded((n) => n + limit);
        setBusy(false);
      }, 0);
    },
  });
  return (
    <>
      <ul>{rows.map((r) => <li key={r.id} data-row={r.id}>row {r.id}</li>)}</ul>
      <ShowMore {...paging} />
    </>
  );
}

describe('usePagedRows (rows per page grows the table in place)', () => {
  it('starts at 10 rows', () => {
    render(<Harness total={74} fetch={noop} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(10);
    expect(radio('10').getAttribute('aria-checked')).toBe('true');
  });

  it('a larger choice appends rows: the first rows keep the same DOM nodes, only the missing rows are fetched', async () => {
    const fetch = vi.fn();
    render(<Harness total={74} fetch={fetch} />);
    const before = screen.getAllByRole('listitem').slice(0, 10);
    await act(async () => {
      fireEvent.click(radio('20'));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const after = screen.getAllByRole('listitem');
    expect(after).toHaveLength(20);
    before.forEach((node, i) => expect(after[i]).toBe(node));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(10);
    expect(screen.queryByText(/Loading/)).toBeNull();
  });

  it('a smaller choice trims the shown rows without a fetch', async () => {
    const fetch = vi.fn();
    render(<Harness total={74} fetch={fetch} />);
    await act(async () => {
      fireEvent.click(radio('50'));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(50);
    const calls = fetch.mock.calls.length;
    fireEvent.click(radio('10'));
    expect(screen.getAllByRole('listitem')).toHaveLength(10);
    expect(fetch.mock.calls.length).toBe(calls);
  });

  it('keeps keyboard focus on the chosen option', async () => {
    render(<Harness total={74} fetch={noop} />);
    radio('10').focus();
    await act(async () => {
      fireEvent.click(radio('20'));
    });
    expect(document.activeElement).toBe(radio('20'));
  });

  it('with 3 rows the 20 and 50 options are disabled; with 15 only 50 (once the 15 are known)', async () => {
    const { unmount } = render(<Harness total={3} fetch={noop} />);
    expect(radio('20').getAttribute('aria-disabled')).toBe('true');
    expect(radio('50').getAttribute('aria-disabled')).toBe('true');
    unmount();
    render(<Harness total={15} fetch={noop} />);
    // more is still to load, so the total is unknown and every option is active
    expect(radio('50').getAttribute('aria-disabled')).toBeNull();
    await act(async () => {
      fireEvent.click(radio('20'));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(radio('20').getAttribute('aria-disabled')).toBeNull();
    expect(radio('50').getAttribute('aria-disabled')).toBe('true');
  });
});
