'use client';

// SCR-35 Clients: the clients the person's access covers, from E-CLIENTS, in the order returned. Every cell comes from
// the returned field; the backend decides who sees which client (INV-ACCESS).
import Link from 'next/link';
import { useEffect, useRef } from 'react';

import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useIsPhone } from '@/features/alerts/useIsPhone';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import type { ClientRow, MoneyAmount } from './api';
import { amountText, clientPath, countLine, NOT_GIVEN, UNKNOWN } from './labels';
import { ClientNoAccess } from './ClientStates';
import { useClients } from './useClients';

import './clients.css';

/** A known amount, or the word "Unknown" (with a spoken explanation); nothing at all is "Not given". */
export function Money({ amount }: { amount?: MoneyAmount }) {
  if (!amount) return <>{NOT_GIVEN}</>;
  const text = amountText(amount);
  return text === UNKNOWN ? (
    <>
      {UNKNOWN}
      <span className="clients__sr"> amount not known</span>
    </>
  ) : (
    <>{text}</>
  );
}

const projectsText = (row: ClientRow) => (row.projects === undefined ? NOT_GIVEN : String(row.projects));

function ContactCell({ row }: { row: ClientRow }) {
  return row.billing_contact_set ? <span>Set</span> : <span className="clients__missing">Missing · invoices can’t start</span>;
}

function ContactTag({ row }: { row: ClientRow }) {
  return row.billing_contact_set ? (
    <span className="psl-tag psl-tag--done">Set</span>
  ) : (
    <span className="psl-tag psl-tag--person">Billing contact missing</span>
  );
}

function ClientTable({ items }: { items: ClientRow[] }) {
  return (
    <div className="psl-tablewrap">
      <table className="psl-table clients__table">
        <thead>
          <tr>
            <th scope="col">CLIENT</th>
            <th scope="col">PROJECTS</th>
            <th scope="col">OWED</th>
            <th scope="col">BILLING CONTACT</th>
            <th scope="col">STATE</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.client_id}>
              <td>
                <span className="clients__namecell">
                  <Link href={clientPath(row.client_id)} className="clients__name" data-client-link="">
                    {row.name}
                  </Link>
                  <SampleLabel show={row.sample} />
                </span>
              </td>
              <td>{projectsText(row)}</td>
              <td>
                <Money amount={row.owed} />
              </td>
              <td>
                <ContactCell row={row} />
              </td>
              <td>
                <ContactTag row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
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
  const rows = useRef<HTMLDivElement>(null);
  const focusRow = useRef<number | null>(null);

  useEffect(() => {
    if (focusRow.current !== null && state.status === 'ready') {
      rows.current?.querySelectorAll<HTMLElement>('[data-client-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [state]);

  const press = async () => {
    const before = await showMore();
    if (before !== undefined) focusRow.current = before;
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
      <div className="psl-empty">
        <p>No clients to show yet.</p>
      </div>
    );
  } else {
    body = (
      <>
        <div ref={rows}>{phone ? <ClientCards items={state.items} /> : <ClientTable items={state.items} />}</div>
        {state.nextCursor && (
          <div className="clients__more">
            <button type="button" className="psl-btn psl-btn--secondary clients__morebtn" disabled={more === 'loading'} aria-busy={more === 'loading'} onClick={() => void press()}>
              {more === 'loading' ? 'Loading…' : 'Show more'}
            </button>
            {more === 'error' && (
              <div role="alert" className="psl-callout psl-callout--problem clients__morefail">
                <span>We couldn’t load more clients. Nothing was changed.</span>
                <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => void press()}>
                  Try again
                </button>
              </div>
            )}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="clients__page">
      <p className="clients__eyebrow">PROJECTS</p>
      <h1 className="shell-title">Clients</h1>
      {state.status === 'ready' && <p className="clients__count">{countLine(state.items, !state.nextCursor, state.asOf)}</p>}
      {body}
    </div>
  );
}
