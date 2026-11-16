'use client';

// DraftCard (design/system/project/components/DraftCard): a draft an agent made, never a reviewed or sent
// document. Header in action-tint with the title and DRAFTED · NOT REVIEWED; label and value rows; the start
// button and "Next:" the station that follows; once started, the green line with the new reference and a link.
// There is no Approve, Send or Pay here, and no way to add one: `action` is the line's own start button.
import type { ReactNode, Ref } from 'react';

import { cx, usePhone } from './internal';

export type DraftRow = { label: string; value: ReactNode };

export function DraftCard({ title, status, rows, next, action, started, startedRef, className }: {
  title: string;
  /** The status words in the header ("DRAFTED · NOT REVIEWED"). */
  status?: string;
  rows: DraftRow[];
  /** The station after the start ("Finance review by a Finance Lead"): "Next: …" beside the buttons, a row on phones. */
  next?: string;
  /** The start button; absent when the draft has no start or has been started. */
  action?: ReactNode;
  /** The started line ("Started INV-0415." and the link); shown below a rule when present. */
  started?: ReactNode;
  /** The started line takes focus here after the start. */
  startedRef?: Ref<HTMLParagraphElement>;
  className?: string;
}) {
  const phone = usePhone();
  return (
    <section className={cx('cmp-draft', className)} aria-label="Draft">
      <div className="cmp-draft__head">
        <span className="cmp-draft__title">{title}</span>
        {status && <span className="cmp-draft__status">{status}</span>}
      </div>
      <dl className="cmp-draft__rows">
        {rows.map((row, at) => (
          <div key={at} className="cmp-draft__row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
        {next && phone && (
          <div className="cmp-draft__row">
            <dt>Next</dt>
            <dd>{next}</dd>
          </div>
        )}
      </dl>
      {(action || (next && !phone)) && (
        <div className="cmp-draft__foot">
          {action}
          {next && !phone && <span className="cmp-draft__next">Next: {next}</span>}
        </div>
      )}
      {started && (
        <p className="cmp-draft__started" role="status" tabIndex={-1} ref={startedRef}>
          {started}
        </p>
      )}
    </section>
  );
}
