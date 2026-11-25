'use client';

// SCR-35 Clients: the client groups and the projects without a group that the person's access covers, from
// clients_directory, groups first, in the order returned. The server decides who sees what; nothing is filtered here.
// There is no owed column: the list has no source for it (the group page shows what the group owes).
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef } from 'react';

import { EmptyState, PageTitle, ShowMore, Table, type ShowMoreProps, Tag, usePagedRows, useIsPhone, type Column } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import type { GroupRow, ProjectRow } from './api';
import { clientPath, countLine, directoryQuery, groupBilling, projectBilling, projectName } from './labels';
import { ClientNoAccess } from './ClientStates';
import { useClients } from './useClients';

import './clients.css';

type Row = { kind: 'group'; row: GroupRow } | { kind: 'project'; row: ProjectRow };
const rowKey = (r: Row) => (r.kind === 'group' ? r.row.key : r.row.case_id);
const rowHref = (r: Row) => clientPath(r.kind === 'group' ? r.row.key : r.row.case_id);
const rowName = (r: Row) => (r.kind === 'group' ? r.row.label : projectName(r.row));
const rowCount = (r: Row) => (r.kind === 'group' ? String(r.row.project_count) : '1');

function billingOf(r: Row) {
  if (r.kind === 'group') {
    const b = groupBilling(r.row);
    return { text: b.text, tag: b.tag, tone: b.needed ? ('person' as const) : ('neutral' as const), needed: b.needed };
  }
  const b = projectBilling(r.row.billing);
  return { text: b.text, tag: b.tag, tone: b.state === 'needed' ? ('person' as const) : ('neutral' as const), needed: b.state === 'needed' };
}

/** The client name, and under a project row its title when the client is given. */
function NameCell({ r }: { r: Row }) {
  return (
    <span className="clients__namecell">
      <Link href={rowHref(r)} className="clients__name" data-client-link="">
        {rowName(r)}
      </Link>
      {r.kind === 'project' && r.row.client && <span className="clients__meta">{r.row.title}</span>}
    </span>
  );
}

function BillingTag({ r }: { r: Row }) {
  const b = billingOf(r);
  return <Tag tone={b.tone}>{b.tag}</Tag>;
}

const COLUMNS: Column<Row>[] = [
  { key: 'client', header: 'CLIENT', cell: (r) => <NameCell r={r} /> },
  { key: 'projects', header: 'PROJECTS', cell: rowCount },
  { key: 'contact', header: 'BILLING CONTACT', cell: (r) => <span className={billingOf(r).needed ? 'clients__missing' : undefined}>{billingOf(r).text}</span> },
  { key: 'state', header: 'STATE', cell: (r) => <BillingTag r={r} /> },
];

function ClientTable({ items, paging }: { items: Row[]; paging: ShowMoreProps }) {
  return <Table className="clients__table" caption="Clients" columns={COLUMNS} rows={items} rowKey={rowKey} empty="No clients to show yet." paging={paging} />;
}

function ClientCards({ items }: { items: Row[] }) {
  return (
    <ul className="clients__cards">
      {items.map((r) => (
        <li key={rowKey(r)} className="clients__card">
          <span className="clients__cardhead">
            <NameCell r={r} />
            <BillingTag r={r} />
          </span>
          <span className="clients__meta">
            Projects: {rowCount(r)} · {billingOf(r).text}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** /clients: heading, the "loaded as of" line, the rows, and Show more while another page of groups or projects exists. `q` and `billing` come from the address. */
export function ClientsList() {
  usePhoneBack({ label: 'Projects', href: '/projects' });
  const phone = useIsPhone();
  const params = useSearchParams();
  const q = params.get('q');
  const billing = params.get('billing');
  const query = useMemo(() => directoryQuery(q, billing), [q, billing]);
  const { state, more, retry, showMore } = useClients(query);
  const ready = state.status === 'ready' ? state : undefined;
  const items = useMemo<Row[]>(() => (ready ? [...ready.groups.map((row) => ({ kind: 'group' as const, row })), ...ready.projects.map((row) => ({ kind: 'project' as const, row }))] : []), [ready]);
  const next = Boolean(ready && (ready.groupNext !== null || ready.projectNext !== null));
  const { rows: shownRows, paging } = usePagedRows({
    items,
    next,
    busy: more === 'loading',
    failed: more === 'error',
    loadMore: () => void showMore(),
    resetKey: `${query.q ?? ''}|${query.billing ?? ''}`,
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
  } else if (items.length === 0 && !next) {
    body = <EmptyState title="No clients">No clients to show yet.</EmptyState>;
  } else {
    body = (
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
    );
  }

  return (
    <div className="clients__page">
      <p className="clients__eyebrow">PROJECTS</p>
      <PageTitle size={34} phoneSize={24}>Clients</PageTitle>
      {ready && <p className="clients__count">{countLine(ready.groups, ready.projects, !next, ready.readAt)}</p>}
      {body}
    </div>
  );
}
