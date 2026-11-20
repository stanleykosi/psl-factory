'use client';

// SCR-35 Clients: the clients the person's access covers, from E-CLIENTS, in the order returned. Every cell comes from
// the returned field; the backend decides who sees which client (INV-ACCESS).
import Link from 'next/link';
import { useEffect, useRef } from 'react';

import { Button, Callout, EmptyState, groupDigits, Money as MoneyValue, PageTitle, ShowMore, Table, type ShowMoreProps, Tag, usePagedRows, Unknown, useIsPhone, VisuallyHidden, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import type { ClientRow, MoneyAmount } from './api';
import { clientPath, countLine, NOT_GIVEN } from './labels';
import { ClientNoAccess } from './ClientStates';
import { useClients } from './useClients';

import './clients.css';

/** A known amount, or the word "Unknown" (with a spoken explanation); nothing at all is "Not given". */
export function Money({ amount }: { amount?: MoneyAmount }) {
  if (!amount) return <>{NOT_GIVEN}</>;
  if (amount.unknown || !amount.amount) {
    return (
      <>
        <Unknown />
        <VisuallyHidden> amount not known</VisuallyHidden>
      </>
    );
  }
  // The amount is a decimal string; a currency other than naira is written with its code, as given.
  if (amount.currency === 'NGN') return <MoneyValue value={amount.amount} />;
  return <span className="psl-mono">{`${amount.currency} ${groupDigits(amount.amount)}`}</span>;
}

const projectsText = (row: ClientRow) => (row.projects === undefined ? NOT_GIVEN : String(row.projects));

function ContactCell({ row }: { row: ClientRow }) {
  return row.billing_contact_set ? <span>Set</span> : <span className="clients__missing">Missing · invoices can’t start</span>;
}

function ContactTag({ row }: { row: ClientRow }) {
  return row.billing_contact_set ? <Tag tone="neutral">Set</Tag> : <Tag tone="person">Billing contact missing</Tag>;
}

const COLUMNS: Column<ClientRow>[] = [
  {
    key: 'client',
    header: 'CLIENT',
    cell: (row) => (
      <span className="clients__namecell">
        <Link href={clientPath(row.client_id)} className="clients__name" data-client-link="">
          {row.name}
        </Link>
        <SampleLabel show={row.sample} />
      </span>
    ),
  },
  { key: 'projects', header: 'PROJECTS', cell: projectsText },
  { key: 'owed', header: 'OWED', cell: (row) => <Money amount={row.owed} /> },
  { key: 'contact', header: 'BILLING CONTACT', cell: (row) => <ContactCell row={row} /> },
  { key: 'state', header: 'STATE', cell: (row) => <ContactTag row={row} /> },
];

function ClientTable({ items, paging }: { items: ClientRow[]; paging: ShowMoreProps }) {
  return <Table className="clients__table" caption="Clients" columns={COLUMNS} rows={items} rowKey={(row) => row.client_id} empty="No clients to show yet." paging={paging} />;
}

function ClientCards({ items }: { items: ClientRow[] }) {
  return (
    <ul className="clients__cards">
      {items.map((row) => (
        <li key={row.client_id} className="clients__card">
          <span className="clients__cardhead">
            <Link href={clientPath(row.client_id)} className="clients__name" data-client-link="">
              {row.name}
            </Link>
            <ContactTag row={row} />
          </span>
          <span className="clients__meta">
            Projects: {projectsText(row)} · Owed: <Money amount={row.owed} />
          </span>
          <SampleLabel show={row.sample} />
        </li>
      ))}
    </ul>
  );
}

/** /clients: heading, the "as of" line, the clients, and Show more while the backend returns a cursor. */
export function ClientsList() {
  usePhoneBack({ label: 'Projects', href: '/projects' });
  const phone = useIsPhone();
  const { state, more, retry, showMore } = useClients();
  const ready = state.status === 'ready' ? state : undefined;
  const { rows: shownRows, paging } = usePagedRows({
    items: ready?.items ?? [],
    next: Boolean(ready?.nextCursor),
    busy: more === 'loading',
    failed: more === 'error',
    loadMore: (limit) => void showMore(limit),
  });
  const rows = useRef<HTMLDivElement>(null);
  const focusRow = useRef<number | null>(null);

  useEffect(() => {
    if (focusRow.current !== null && shownRows.length > focusRow.current) {
      rows.current?.querySelectorAll<HTMLElement>('[data-client-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [shownRows.length]);

  // Show more: the keyboard moves to the first row it added.
  const footer: ShowMoreProps = {
    ...paging,
    onMore: () => {
      if (more !== 'error') focusRow.current = shownRows.length;
      paging.onMore();
    },
  };

  if (state.status === 'error' && state.error.kind === 'unauthenticated') return <SignedOutState pathname="/clients" />;
  if (state.status === 'error' && (state.error.kind === 'forbidden' || state.error.kind === 'not_found')) return <ClientNoAccess list />;

  let body;
  if (state.status === 'loading') {
    body = <LoadingState />;
  } else if (state.status === 'error') {
    body = <WorkErrorCard message="We couldn’t load the clients. Your work is safe; nothing was changed." error={state.error} onRetry={() => void retry()} />;
  } else if (state.items.length === 0 && !state.nextCursor) {
    body = (
      <EmptyState title="No clients">No clients to show yet.</EmptyState>
    );
  } else {
    body = (
      <>
        <div ref={rows}>
          {phone ? (
            <>
              <ClientCards items={shownRows} />
              <ShowMore solo {...footer} />
            </>
          ) : (
            <ClientTable items={shownRows} paging={footer} />
          )}
        </div>
        {more === 'error' && (
          <div className="clients__more">
            <Callout kind="problem">
              We couldn’t load more clients. Nothing was changed.{' '}
              <Button kind="secondary" size="sm" onClick={() => paging.onMore()}>
                Try again
              </Button>
            </Callout>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="clients__page">
      <p className="clients__eyebrow">PROJECTS</p>
      <PageTitle size={34} phoneSize={24}>Clients</PageTitle>
      {state.status === 'ready' && <p className="clients__count">{countLine(state.items, !state.nextCursor, state.asOf)}</p>}
      {body}
    </div>
  );
}
