# Table

For records people compare across columns: invoices, receipts, registers, ledger lines.

- 2px `ink` frame and header rule; 1px `rule-soft` row lines. Header in mono caps, `ink-muted`; a sorted column is `ink` with an arrow.
- Amounts right-aligned in mono with two decimals; Unknown shown as the amber Unknown tag, never 0.
- Row states: default, hover (`surface-subtle`), selected (`action-tint`), current or needs attention (orange left edge on `signal-tint`).
- Select-all checkbox in the header: mixed when some rows are chosen. Bulk actions appear above the table once anything is selected.
- Totals row in bold with a 2px rule above. On phones the table scrolls sideways inside its frame, or becomes a stacked list.
- Empty: a sentence in the body ("No invoices yet for this project"), never a blank grid.
