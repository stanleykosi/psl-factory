// The invoice and paid cells and the Unknown-or-text value, as the Money and Milestones tabs both draw them.
import { Unknown, VisuallyHidden } from '@/components';

import { invoiceLines, type MoneyItem } from './moneyModel';

/** A value as text, or the amber Unknown when the backend does not know it (never 0, never blank). */
export function Value({ text }: { text: string | undefined }) {
  return text ? <>{text}</> : <Unknown />;
}

/** One line per invoice as sent: its reference and its own status text. No invoice reads a dash. */
export function InvoiceCell({ item }: { item: MoneyItem }) {
  const lines = invoiceLines(item);
  if (lines.length === 0) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <VisuallyHidden>No invoice</VisuallyHidden>
      </>
    );
  }
  return (
    <>
      {lines.map((line) => (
        <span key={line.id} className="money__block">
          {line.reference} · {line.status}
        </span>
      ))}
    </>
  );
}

/** "Paid ₦… · Owed …" per invoice, each Unknown when null. No paid word is made up, and nothing is compared or added. */
export function PaidCell({ item }: { item: MoneyItem }) {
  const lines = invoiceLines(item);
  if (lines.length === 0) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <VisuallyHidden>No payment</VisuallyHidden>
      </>
    );
  }
  return (
    <>
      {lines.map((line) => (
        <span key={line.id} className="money__block">
          <span className="money__fig">
            Paid <Value text={line.paid} /> ·
          </span>{' '}
          <span className="money__fig">
            Owed <Value text={line.owed} />
          </span>
        </span>
      ))}
    </>
  );
}
