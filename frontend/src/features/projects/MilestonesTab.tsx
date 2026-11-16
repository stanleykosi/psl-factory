'use client';

// SCR-38 Milestones: contract amount, completion, invoice and paid as separate facts, read from E-PROJECT-TAB. A change
// sits beside the milestone it changes; its amount is shown next to the contract amount and never added to it.
import Link from 'next/link';
import { useRef } from 'react';

import { EmptyState, Table, Tag, Unknown, useIsPhone, type Column } from '@/components';

import { AmountValue, AsOf, NONE, RowLink, RowsFooter, tabStateView } from './TabParts';
import {
  completionText,
  hasChanges,
  invoiceWord,
  paidWord,
  workHref,
  type Change,
  type MilestoneRow,
  type Paid,
} from './tabsModel';
import { useFocusAfterMore } from './useFocusAfterMore';
import { useProjectTab } from './useProjectTab';

const VIEW = { register: 'issues' } as const;

/** "₦4,250,000.00 + the change · change amount Unknown": both values as sent, never a sum. */
function AmountCell({ row }: { row: MilestoneRow }) {
  return (
    <>
      <AmountValue value={row.contract_amount} />
      {(row.changes ?? []).map((change, i) => (
        <span key={`${change.reference}-${i}`}>
          {' + the change · change amount '}
          <AmountValue value={change.amount} />
        </span>
      ))}
    </>
  );
}

function InvoiceCell({ invoice }: { invoice: MilestoneRow['invoice'] }) {
  if (!invoice) return NONE;
  const word = invoiceWord(invoice.state);
  return (
    <>
      <RowLink workId={invoice.work_id}>{invoice.reference}</RowLink>
      {word && ` · ${word}`}
    </>
  );
}

/** Paid is Finance's own fact: absent is "—", unknown is the Unknown tag, and the invoice is never read for it. */
function PaidCell({ paid }: { paid: Paid | undefined }) {
  if (!paid) return NONE;
  const word = paidWord(paid);
  return (
    <>
      {word ?? <Unknown />}
      {paid.owed && (
        <>
          {' · '}
          <AmountValue value={paid.owed} /> owed
        </>
      )}
    </>
  );
}

function ChangeLink({ change }: { change: Change }) {
  return <RowLink workId={change.work_id}>{[change.reference, change.title].filter(Boolean).join(' · ')}</RowLink>;
}

function ChangesCell({ changes }: { changes: Change[] | undefined }) {
  if (!changes?.length) return NONE;
  return (
    <>
      {changes.map((change, i) => (
        <span key={`${change.reference}-${i}`} className="ptabs__block">
          <ChangeLink change={change} />
        </span>
      ))}
    </>
  );
}

const rowKey = (row: MilestoneRow) => `${row.position}-${row.name}`;

function columns(withChanges: boolean): Column<MilestoneRow>[] {
  const base: Column<MilestoneRow>[] = [
    { key: 'name', header: 'MILESTONE', cell: (row) => `${row.position} · ${row.name}` },
    { key: 'amount', header: 'CONTRACT AMOUNT', cell: (row) => <AmountCell row={row} /> },
    { key: 'completion', header: 'COMPLETION', cell: (row) => completionText(row) },
    { key: 'invoice', header: 'INVOICE', cell: (row) => <InvoiceCell invoice={row.invoice} /> },
    { key: 'paid', header: 'PAID', cell: (row) => <PaidCell paid={row.paid} /> },
  ];
  return withChanges ? [...base, { key: 'changes', header: 'CHANGES', cell: (row) => <ChangesCell changes={row.changes} /> }] : base;
}

/** SCR-38 phone: one card per milestone in the order returned. */
function MilestoneCards({ rows }: { rows: MilestoneRow[] }) {
  return (
    <ul className="ptabs__cards">
      {rows.map((row) => (
        <li key={rowKey(row)} className="ptabs__card">
          <strong>
            {row.position} · {row.name}
          </strong>
          <span className="ptabs__cardmain">
            <AmountCell row={row} /> · {completionText(row)}
          </span>
          <span className="ptabs__cardhint">
            <InvoiceCell invoice={row.invoice} />
          </span>
          <span className="ptabs__cardhint">
            Paid: <PaidCell paid={row.paid} />
          </span>
          {(row.changes ?? []).map((change, i) => {
            const href = workHref(change.work_id);
            const tag = (
              <Tag tone="waiting" className="ptabs__changed">
                CHANGED · {change.reference}
              </Tag>
            );
            return href ? (
              <Link key={`${change.reference}-${i}`} href={href} className="ptabs__changelink">
                {tag}
              </Link>
            ) : (
              <span key={`${change.reference}-${i}`}>{tag}</span>
            );
          })}
        </li>
      ))}
    </ul>
  );
}

export function MilestonesTab({ caseId, pathname }: { caseId: string; pathname: string }) {
  const phone = useIsPhone();
  const { state, more, showMore, retry } = useProjectTab(caseId, 'milestones', VIEW);
  const rowsRef = useRef<HTMLDivElement>(null);
  useFocusAfterMore(rowsRef, state.status === 'ready' ? state.rows.length : 0);
  const shown = tabStateView(state, { retry, signInPath: pathname });
  if (state.status !== 'ready') return <>{shown}</>;

  const { rows } = state;
  return (
    <>
      <div ref={rowsRef} className="ptabs__rows">
        {rows.length === 0 ? (
          <EmptyState title="No milestones yet">No milestones on this project yet.</EmptyState>
        ) : phone ? (
          <MilestoneCards rows={rows} />
        ) : (
          <Table className="ptabs__table" caption="Milestones" columns={columns(hasChanges(rows))} rows={rows} rowKey={rowKey} empty="No milestones on this project yet." />
        )}
      </div>
      <RowsFooter shown={rows.length} hasMore={Boolean(state.nextCursor)} more={more} onMore={() => void showMore()} />
      {rows.length > 0 && <AsOf value={state.asOf} />}
      <p className="ptabs__note">
        Milestones and amounts come from the signed SOW. Completing a milestone is the PM&rsquo;s fact; invoicing and payment are Finance&rsquo;s, and each is shown separately.
      </p>
    </>
  );
}
