'use client';

// SCR-35 client detail. A group key opens the group (its projects, each with its billing tag, and what the group owes);
// a case id opens one project's billing and project contacts. Everything is read only: recording a billing contact is
// held until a proof can be recorded from here. Nothing on this page decides whether an invoice may start.
import Link from 'next/link';

import type { ApiError } from '@/api/errors';
import { Breadcrumb, Button, formatDate, groupDigits, Money as MoneyValue, PageTitle, Panel, Tag, VisuallyHidden } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import type { Contact, Debt, ProjectRow, Workspace } from './api';
import { ClientNoAccess } from './ClientStates';
import { clientPath, isCaseId, projectBilling, unknownProjectsText } from './labels';
import { useGroup, useHistory, useWorkspace } from './useClient';

import './clients.css';

const projectPath = (caseId: string) => `/projects/${encodeURIComponent(caseId)}`;

/** A known amount in its own currency; naira with its sign, any other currency by its code. Never added across currencies. */
function Amount({ currency, value }: { currency: string; value: string }) {
  if (currency === 'NGN') return <MoneyValue value={value} />;
  return <span className="psl-mono">{`${currency} ${groupDigits(value)}`}</span>;
}

/** What the group owes, from debt: one line per currency, a missing amount is "Not known" (never 0), and the coverage is said. */
function OwedPanel({ debt }: { debt: Debt | null }) {
  return (
    <Panel head="Owed" className="clients__panel" bodyClassName="clients__panelbody">
      {debt === null ? (
        <p className="clients__plain">Owed amount is not available for this group.</p>
      ) : (
        <>
          {debt.totals.length === 0 && <p className="clients__plain">Nothing owed is recorded for the projects you can see.</p>}
          {debt.totals.length > 0 && (
            <ul className="clients__owed">
              {debt.totals.map((t) => (
                <li key={t.currency} className="clients__owedrow">
                  <span className="clients__owedline">
                    <span className="clients__meta">Owed · {t.currency}</span>
                    {t.known_owed === null ? <span>Not known</span> : <Amount currency={t.currency} value={t.known_owed} />}
                  </span>
                  {t.unknown_owed_count > 0 && <span>{unknownProjectsText(t.unknown_owed_count)}</span>}
                  <span className="clients__meta">{t.basis}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="clients__meta">
            As of {formatDate(debt.as_of)} · {debt.workspace_count === 1 ? '1 project' : `${debt.workspace_count} projects`} you can see
          </p>
          {debt.limited && <p className="clients__help">May be incomplete: only part of this group is in your view or could be read.</p>}
        </>
      )}
    </Panel>
  );
}

function ProjectBilling({ row }: { row: ProjectRow }) {
  const b = projectBilling(row.billing);
  return <Tag tone={b.state === 'needed' ? 'person' : 'neutral'}>{b.tag}</Tag>;
}

function GroupView({ groupKey }: { groupKey: string }) {
  usePhoneBack({ label: 'Clients', href: '/clients' });
  const { state, more, retry, showMore } = useGroup(groupKey);
  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') return <Failed error={state.error} retry={retry} path={clientPath(groupKey)} />;
  const { group } = state;
  return (
    <div className="clients__page">
      <div className="clients__crumb">
        <Breadcrumb items={[{ label: 'Clients', href: '/clients' }]} current={group.label} />
      </div>
      <div className="clients__titlerow">
        <PageTitle size={34} phoneSize={22}>
          {group.label}
        </PageTitle>
      </div>
      <div className="clients__body">
        <div className="clients__main">
          <Panel head="Billing contact" className="clients__panel" bodyClassName="clients__panelbody">
            <p className="clients__plain">Billing contacts are recorded for each project. Open a project’s billing contacts from the list.</p>
          </Panel>
        </div>
        <aside className="clients__aside">
          <Panel head="Projects" className="clients__panel" bodyClassName="clients__panelbody">
            {group.projects.map((project) => (
              <div key={project.case_id} className="clients__project">
                <Link href={projectPath(project.case_id)} className="clients__name">
                  {project.title}
                </Link>
                <span className="clients__projectrow">
                  <ProjectBilling row={project} />
                  <Link href={clientPath(project.case_id)} className="clients__crumblink">
                    Billing contacts<VisuallyHidden> for {project.title}</VisuallyHidden>
                  </Link>
                </span>
              </div>
            ))}
            {more === 'error' && (
              <p className="clients__help" role="alert">
                We couldn’t load more. Choose Show more to try again.
              </p>
            )}
            {group.next_page !== null && (
              <Button kind="secondary" size="sm" className="clients__more" busy={more === 'loading'} busyLabel="Loading…" onClick={() => void showMore()}>
                Show more
              </Button>
            )}
          </Panel>
          <OwedPanel debt={group.debt} />
        </aside>
      </div>
    </div>
  );
}

function ContactBlock({ contact }: { contact: Contact }) {
  return (
    <div className="clients__contact">
      <span className="clients__name">{contact.name}</span>
      <dl className="clients__facts">
        {contact.customer && (
          <div>
            <dt>Customer</dt>
            <dd>{contact.customer}</dd>
          </div>
        )}
        <div>
          <dt>Email</dt>
          <dd>{contact.email || NOT_GIVEN}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{contact.role || NOT_GIVEN}</dd>
        </div>
      </dl>
      <span className="clients__meta">version {contact.version}</span>
    </div>
  );
}
const NOT_GIVEN = 'Not given';

function HistoryBlock({ caseId, customer }: { caseId: string; customer?: string }) {
  const { state, open, showMore } = useHistory(caseId, customer);
  return (
    <div className="clients__history">
      {state.status === 'closed' && (
        <Button kind="link" onClick={() => void open()}>
          Show history
        </Button>
      )}
      {state.status === 'loading' && <p className="clients__meta">Loading…</p>}
      {state.status === 'error' && (
        <p className="clients__help" role="alert">
          We couldn’t load the history. <Button kind="link" onClick={() => void open()}>Try again</Button>
        </p>
      )}
      {state.status === 'ready' && (
        <>
          <ul className="clients__versions" aria-label="Billing contact history, newest first">
            {state.items.map((c) => (
              <li key={c.contact_id}>
                <ContactBlock contact={c} />
              </li>
            ))}
            {state.items.length === 0 && <li className="clients__plain">No earlier versions.</li>}
          </ul>
          {state.more === 'error' && (
            <p className="clients__help" role="alert">
              We couldn’t load more. Choose Show more to try again.
            </p>
          )}
          {state.next !== null && (
            <Button kind="secondary" size="sm" className="clients__more" busy={state.more === 'loading'} busyLabel="Loading…" onClick={() => void showMore()}>
              Show more
            </Button>
          )}
        </>
      )}
    </div>
  );
}

function WorkspaceView({ workspace }: { workspace: Workspace }) {
  usePhoneBack({ label: 'Clients', href: '/clients' });
  const billing = workspace.contacts.filter((c) => c.purpose === 'billing');
  const project = workspace.contacts.filter((c) => c.purpose === 'project');
  return (
    <div className="clients__page">
      <div className="clients__crumb">
        <Breadcrumb items={[{ label: 'Clients', href: '/clients' }]} current={workspace.title} />
      </div>
      <div className="clients__titlerow">
        <PageTitle size={34} phoneSize={22}>
          {workspace.title}
        </PageTitle>
        <SampleLabel show={workspace.sample} />
      </div>
      <div className="clients__body">
        <div className="clients__main">
          <Panel head="Billing contact" className="clients__panel" bodyClassName="clients__panelbody">
            {billing.length === 0 && <p className="clients__plain">Not set</p>}
            {billing.map((c) => (
              <ContactBlock key={c.contact_id} contact={c} />
            ))}
            <Button disabled reason="Recording a billing contact from this page is not available yet. It waits for a way to record the proof of the instruction.">
              Add billing contact
            </Button>
            {billing.length > 0 && <HistoryBlock caseId={workspace.case_id} customer={billing[0].customer || undefined} />}
          </Panel>
          {project.length > 0 && (
            <Panel head="Project contacts" className="clients__panel" bodyClassName="clients__panelbody">
              {project.map((c) => (
                <ContactBlock key={c.contact_id} contact={c} />
              ))}
            </Panel>
          )}
        </div>
        <aside className="clients__aside">
          <Panel head="Projects" className="clients__panel" bodyClassName="clients__panelbody">
            <div className="clients__project">
              <Link href={projectPath(workspace.case_id)} className="clients__name">
                {workspace.title}
              </Link>
              <Link href={`${projectPath(workspace.case_id)}/money`} className="clients__crumblink">
                Money for this project
              </Link>
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function Failed({ error, retry, path }: { error: ApiError; retry: () => Promise<void>; path: string }) {
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={path} />;
  if (error.kind === 'forbidden' || error.kind === 'not_found') return <ClientNoAccess />;
  return <WorkErrorCard message="We couldn’t load this client. Your work is safe; nothing was changed." error={error} onRetry={() => void retry()} />;
}

function WorkspacePage({ caseId }: { caseId: string }) {
  usePhoneBack({ label: 'Clients', href: '/clients' });
  const { state, retry } = useWorkspace(caseId);
  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') return <Failed error={state.error} retry={retry} path={clientPath(caseId)} />;
  return <WorkspaceView workspace={state.workspace} />;
}

/** /clients/<id>: a UUID is a project's workspace, anything else a client group key (a key can change if grouping changes; a stale one is "no access"). */
export function ClientDetailPage({ clientId }: { clientId: string }) {
  return isCaseId(clientId) ? <WorkspacePage caseId={clientId} /> : <GroupView groupKey={clientId} />;
}
