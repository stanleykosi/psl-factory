'use client';

// Table (design/system/project/components/Table): records people compare across columns. Header in mono caps; a
// sorted column is ink with an arrow and aria-sort. Amounts right-aligned in mono (use Money from Values.tsx with `sign` off, so
// Unknown is the amber tag, never 0). Rows: selected (action-tint) and current or needs attention (orange left
// edge). Select-all in the header is mixed when some rows are chosen; bulk actions appear above once anything is
// chosen. Totals row in bold over a 2px rule. Empty is a sentence in the body, never a blank grid. A row can open
// a full-width row under it (`expanded`, e.g. the upload panel under a template). The frame scrolls sideways on
// phones and can take focus so keyboards can scroll it.
import { Fragment, type ReactNode } from 'react';

import { Checkbox } from './Checkbox';
import { Icon } from './Icon';
import { cx } from './internal';
import { ShowMore, type ShowMoreProps } from './ShowMore';

export type Column<R> = {
  key: string;
  header: string;
  cell: (row: R) => ReactNode;
  /** Right-aligned mono (amounts, counts). */
  num?: boolean;
  /** Mono (references). */
  mono?: boolean;
  sortable?: boolean;
  /** The header is read but not drawn (a column of row actions). */
  hideHeader?: boolean;
  /** A class on this column's cells. */
  className?: string;
};

export type Sort = { key: string; dir: 'ascending' | 'descending' };

export function Table<R>({ caption, columns, rows, rowKey, empty, sort, onSort, selected, onSelect, rowLabel, rowState, expanded, bulkActions, footer, paging, leading, fullRow, className, tableClassName, wrapClassName }: {
  /** Names the table for screen readers (visually hidden). */
  caption: string;
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R) => string;
  /** The sentence shown when there are no rows ("No invoices yet for this project"). */
  empty: string;
  sort?: Sort;
  onSort?: (key: string) => void;
  /** Keys of chosen rows; with onSelect, adds the checkbox column. */
  selected?: Set<string>;
  onSelect?: (keys: Set<string>) => void;
  /** Names a row's checkbox ("Select INV-0412"). */
  rowLabel?: (row: R) => string;
  rowState?: (row: R) => 'current' | undefined;
  /** A full-width row drawn under the row (an inline panel), or null. */
  expanded?: (row: R) => ReactNode;
  /** Shown above the table once a row is chosen. */
  bulkActions?: ReactNode;
  /** Totals row cells, one per column. */
  footer?: ReactNode[];
  /** The paging footer (count, rows per page, Show more), drawn inside the table's frame under the last row. */
  paging?: ShowMoreProps;
  /** A first column the screen fills itself (its own checkboxes), where `selected` and `onSelect` do not fit. */
  leading?: { header: ReactNode; headerClassName?: string; cell: (row: R) => ReactNode };
  /** A row shown as one full-width cell instead of its columns (a record the person may not open), or undefined. */
  fullRow?: (row: R) => ReactNode;
  className?: string;
  tableClassName?: string;
  /** A class on the scrolling frame. */
  wrapClassName?: string;
}) {
  const selectable = selected !== undefined && onSelect !== undefined;
  const chosen = selectable ? rows.filter((r) => selected.has(rowKey(r))).length : 0;
  const span = columns.length + (selectable || leading ? 1 : 0);

  function toggleAll() {
    if (!onSelect) return;
    onSelect(chosen === rows.length ? new Set() : new Set(rows.map(rowKey)));
  }

  function toggle(key: string) {
    if (!selectable) return;
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onSelect(next);
  }

  // The frame scrolls sideways on narrow screens; it takes focus so a keyboard can scroll it.
  const wrap = (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      <div className={cx('psl-tablewrap', wrapClassName)} role="region" aria-label={caption} tabIndex={0}>
        <table className={cx('psl-table', tableClassName)}>
          <caption className="cmp-sr">{caption}</caption>
          <thead>
            <tr>
              {selectable && (
                <th className="psl-check-cell" scope="col">
                  <Checkbox label={<span className="cmp-sr">Select all</span>} checked={rows.length > 0 && chosen === rows.length} mixed={chosen > 0 && chosen < rows.length} disabled={rows.length === 0} onChange={toggleAll} />
                </th>
              )}
              {leading && (
                <th className={cx('psl-check-cell', leading.headerClassName)}>{leading.header}</th>
              )}
              {columns.map((col) => {
                const sorted = sort?.key === col.key ? sort.dir : undefined;
                return (
                  <th key={col.key} scope="col" aria-sort={sorted} className={col.num ? 'num' : undefined}>
                    {col.sortable && onSort ? (
                      <button type="button" onClick={() => onSort(col.key)}>
                        {col.header}
                        {sorted && <Icon name={sorted === 'ascending' ? 'sort' : 'down'} />}
                      </button>
                    ) : col.hideHeader ? (
                      <span className="cmp-sr">{col.header}</span>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={span}>{empty}</td>
              </tr>
            ) : (
              rows.map((row) => {
                const key = rowKey(row);
                const isSelected = selectable && selected.has(key);
                const more = expanded?.(row);
                const whole = fullRow?.(row);
                if (whole !== undefined) {
                  return (
                    <tr key={key}>
                      <td colSpan={span}>{whole}</td>
                    </tr>
                  );
                }
                return (
                  <Fragment key={key}>
                    <tr className={cx(isSelected && 'is-selected', rowState?.(row) === 'current' && 'is-current') || undefined}>
                      {selectable && (
                        <td className="psl-check-cell">
                          <Checkbox label={<span className="cmp-sr">{rowLabel ? rowLabel(row) : `Select ${key}`}</span>} checked={isSelected} onChange={() => toggle(key)} />
                        </td>
                      )}
                      {leading && <td className="psl-check-cell">{leading.cell(row)}</td>}
                      {columns.map((col) => (
                        <td key={col.key} data-label={col.header} className={cx(col.num && 'num', col.mono && 'psl-mono', col.className) || undefined}>
                          {col.cell(row)}
                        </td>
                      ))}
                    </tr>
                    {more && (
                      <tr className="cmp-expanded">
                        <td colSpan={span}>{more}</td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
          {footer && rows.length > 0 && (
            <tfoot>
              <tr>
                {selectable && <td />}
                {footer.map((cell, i) => (
                  <td key={i} className={columns[i]?.num ? 'num' : undefined}>
                    {cell}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
  );

  return (
    <div className={className}>
      {selectable && chosen > 0 && (
        <div className="cmp-bulk">
          <strong>{chosen} selected</strong>
          {bulkActions}
          <button type="button" className="psl-link cmp-linkbutton cmp-linkbutton--small" onClick={() => onSelect(new Set())}>
            Clear selection
          </button>
        </div>
      )}
      {paging ? <div className="psl-tableframe">{wrap}<ShowMore {...paging} /></div> : wrap}
    </div>
  );
}
