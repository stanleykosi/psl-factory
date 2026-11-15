'use client';

// SCR-35 client detail: the banner lines the backend returns, the billing contact (a form only when the backend says
// can_change), the client's projects and its money. Nothing here decides whether an invoice may start.
import Link from 'next/link';
import { useState } from 'react';

import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
import { WarningIcon } from '@/shell/icons';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import type { ClientDetail as Client } from './api';
import { BillingContactForm } from './BillingContactForm';
import { ClientNoAccess } from './ClientStates';
import { Money } from './ClientsList';
import { useClient } from './useClient';

import './clients.css';

const MONEY_ROWS = [
  ['invoiced', 'Invoiced'],
  ['received', 'Received'],
  ['owed', 'Owed'],
] as const;

function ProjectsPanel({ projects }: { projects: Client['projects'] }) {
  return (
    <section className="psl-panel clients__panel" aria-labelledby="client-projects-title">
      <h2 id="client-projects-title" className="psl-panel__head clients__h2">
        Projects
      </h2>
      <div className="clients__panelbody">
        {projects.length === 0 && <p className="clients__plain">No projects yet.</p>}
        {projects.map((project) => (
          <div key={project.case_id} className="clients__project">
            <Link href={`/projects/${encodeURIComponent(project.case_id)}`} className="clients__name">
              {project.title}
            </Link>
            {project.stage && <span className="clients__meta">{project.stage}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}

function MoneyPanel({ money }: { money: NonNullable<Client['money']> }) {
  const rows = MONEY_ROWS.filter(([key]) => money[key]);
  if (rows.length === 0) return null;
  return (
    <section className="psl-panel clients__panel" aria-labelledby="client-money-title">
      <h2 id="client-money-title" className="psl-panel__head clients__h2">
        Money
      </h2>
      <dl className="clients__panelbody clients__money">
        {rows.map(([key, label]) => (
          <div key={key} className="clients__moneyrow">
            <dt>{label}</dt>
            <dd>
              <Money amount={money[key]} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ClientView({ client, refresh, onSignedOut, onNoAccess }: { client: Client } & Pick<React.ComponentProps<typeof BillingContactForm>, 'refresh' | 'onSignedOut' | 'onNoAccess'>) {
  return (
    <div className="clients__page">
      <p className="psl-crumb clients__crumb">
        <Link href="/clients">Clients</Link> / <span aria-current="page">{client.name}</span>
      </p>
      <div className="clients__titlerow">
        <h1 className="shell-title">{client.name}</h1>
        <SampleLabel show={client.sample} />
      </div>
      <div className="clients__body">
        <div className="clients__main">
          {(client.blocked ?? []).map((line, i) => (
            <div key={i} className="psl-callout psl-callout--problem">
              <WarningIcon />
              <span>{line}</span>
            </div>
          ))}
          <BillingContactForm client={client} refresh={refresh} onSignedOut={onSignedOut} onNoAccess={onNoAccess} />
        </div>
        <aside className="clients__aside">
          <ProjectsPanel projects={client.projects} />
          {client.money && <MoneyPanel money={client.money} />}
        </aside>
      </div>
    </div>
  );
}

/** /clients/<client_id>. The backend hides a client the person may not see (404): then nothing about it is shown. */
export function ClientDetailPage({ clientId }: { clientId: string }) {
  usePhoneBack({ label: 'Clients', href: '/clients' });
  const { state, retry, refresh } = useClient(clientId);
  const [ended, setEnded] = useState<'signed_out' | 'no_access' | null>(null);

  if (ended === 'signed_out') return <SignedOutState pathname={`/clients/${encodeURIComponent(clientId)}`} />;
  if (ended === 'no_access') return <ClientNoAccess />;
  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={`/clients/${encodeURIComponent(clientId)}`} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <ClientNoAccess />;
    return <WorkErrorCard message="We couldn’t load this client. Your work is safe; nothing was changed." error={error} onRetry={() => void retry()} />;
  }
  return <ClientView client={state.client} refresh={refresh} onSignedOut={() => setEnded('signed_out')} onNoAccess={() => setEnded('no_access')} />;
}
