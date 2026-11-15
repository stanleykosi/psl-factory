'use client';

// SCR-35 client detail: the banner lines the backend returns, the billing contact (a form only when the backend says
// can_change), the client's projects and its money. Nothing here decides whether an invoice may start.
import Link from 'next/link';
import { useState } from 'react';

import { Breadcrumb, Callout, PageTitle, Panel } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
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
    <Panel head="Projects" className="clients__panel" bodyClassName="clients__panelbody">
      {projects.length === 0 && <p className="clients__plain">No projects yet.</p>}
      {projects.map((project) => (
        <div key={project.case_id} className="clients__project">
          <Link href={`/projects/${encodeURIComponent(project.case_id)}`} className="clients__name">
            {project.title}
          </Link>
          {project.stage && <span className="clients__meta">{project.stage}</span>}
        </div>
      ))}
    </Panel>
  );
}

function MoneyPanel({ money }: { money: NonNullable<Client['money']> }) {
  const rows = MONEY_ROWS.filter(([key]) => money[key]);
  if (rows.length === 0) return null;
  return (
    <Panel head="Money" className="clients__panel" bodyClassName="clients__panelbody">
      <dl className="clients__money">
        {rows.map(([key, label]) => (
          <div key={key} className="clients__moneyrow">
            <dt>{label}</dt>
            <dd>
              <Money amount={money[key]} />
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function ClientView({ client, refresh, onSignedOut, onNoAccess }: { client: Client } & Pick<React.ComponentProps<typeof BillingContactForm>, 'refresh' | 'onSignedOut' | 'onNoAccess'>) {
  return (
    <div className="clients__page">
      <div className="clients__crumb">
        <Breadcrumb items={[{ label: 'Clients', href: '/clients' }]} current={client.name} />
      </div>
      <div className="clients__titlerow">
        <PageTitle>{client.name}</PageTitle>
        <SampleLabel show={client.sample} />
      </div>
      <div className="clients__body">
        <div className="clients__main">
          {(client.blocked ?? []).map((line, i) => (
            <Callout key={i} kind="problem" announce={false}>
              {line}
            </Callout>
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
