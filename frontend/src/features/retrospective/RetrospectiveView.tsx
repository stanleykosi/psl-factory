'use client';

// SCR-33 project retrospective (/projects/[caseId]/retrospective?dossier=&meeting=&version=): record the retrospective
// as a saved version through the live project meetings, and see where it stands in the closure checklist. Every save is
// a recorded version (no draft); "saved" is drawn only from the re-read that follows a write.
import type { ApiError } from '@/api/errors';
import { usePathname, useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { Breadcrumb, Button, Callout, EmptyState, formatClock, Loading, PageTitle, Panel, SampleLabel, useToastWhen } from '@/components';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { ActionForm } from './ActionForm';
import { ChecklistStrip } from './ChecklistStrip';
import { defaultReference, positiveInt } from './model';
import { initialDraft, RetroForm } from './RetroForm';
import { SavedVersion } from './SavedVersion';
import { parseSummary } from './summary';
import { useRetrospective } from './useRetrospective';
import './retrospective.css';

const UNAVAILABLE = 'This record is unavailable.';

function Problem({ error, onRetry, path }: { error: ApiError; onRetry: () => void; path: string }) {
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={path} />;
  if (error.kind === 'not_found' || error.kind === 'forbidden') return <Callout kind="warning">{UNAVAILABLE}</Callout>;
  return (
    <div className="retro__stack">
      <Callout kind="problem">Try again shortly.</Callout>
      <span>
        <Button kind="secondary" onClick={onRetry}>
          Try again
        </Button>
      </span>
    </div>
  );
}

export function RetrospectivePage({ caseId }: { caseId: string }) {
  const params = useSearchParams();
  const pathname = usePathname();
  const query = { dossier: positiveInt(params.get('dossier')), meeting: positiveInt(params.get('meeting')), version: positiveInt(params.get('version')) };
  const path = `${pathname}${params.toString() ? `?${params.toString()}` : ''}`;
  const r = useRetrospective(caseId, query);
  const [editing, setEditing] = useState(false);
  const [now] = useState(() => new Date());
  // Saved is drawn from the re-read that follows the write (savedNote is set only then); the result of the press is a toast.
  useToastWhen(r.savedNote ? `Saved ${formatClock(r.savedNote.at)} WAT, version ${r.savedNote.version}.` : null);

  const title = r.project.status === 'ready' ? r.project.data.title : null;
  const header = (
    <>
      <div className="retro__crumb">
        <Breadcrumb items={[{ label: 'PROJECTS', href: '/projects' }, { label: (title ?? 'PROJECT').toUpperCase() }]} current="CLOSURE" />
      </div>
      <PageTitle size={34} phoneSize={22}>Project retrospective</PageTitle>
      {title && (
        <p className="retro__sub">
          {title} · needed before closure {r.project.status === 'ready' && r.project.data.sample && <SampleLabel />}
        </p>
      )}
    </>
  );

  // The first failing read decides: the project and the meeting list are both needed to draw anything.
  const failed = r.project.status === 'error' ? r.project.error : r.list.status === 'error' ? r.list.error : null;
  if (failed) {
    return (
      <div className="retro__page">
        {r.project.status !== 'error' && header}
        <Problem error={failed} onRetry={() => window.location.reload()} path={path} />
      </div>
    );
  }
  if (r.project.status !== 'ready' || r.list.status !== 'ready') {
    return (
      <div className="retro__page">
        {header}
        <LoadingState />
      </div>
    );
  }

  const list = r.list.data;
  const rows = list.items;
  const options = r.options.status === 'ready' ? r.options.data : null;
  const optionsProblem = r.options.status === 'error' ? "We couldn't load the people and files you can pick." : r.options.status === 'loading' ? 'Loading the people and files you can pick…' : null;
  const canRecord = list.can_record && r.options.status !== 'forbidden';
  const empty = rows.length === 0;
  const detail = r.detail.status === 'ready' ? r.detail.data : null;
  const form = canRecord && (empty || (editing && detail?.current === true));
  const revision = list.revision;

  async function save(body: Parameters<typeof r.save>[0]) {
    if (await r.save(body)) setEditing(false);
  }

  return (
    <div className="retro__page">
      {header}
      <div className="retro__body">
        <div className="retro__main">
          {!empty && (
            <Panel head="Saved retrospectives" headingLevel={2} bodyClassName="retro__stack">
              <ul className="retro__versions">
                {rows.map((row) => (
                  <li key={row.id}>
                    <Button
                      kind="bare"
                      className="retro__version"
                      aria-current={r.selected?.meeting === row.id}
                      onClick={() => {
                        setEditing(false);
                        r.setSelected({ meeting: row.id, version: null });
                      }}
                    >
                      <strong>{row.reference}</strong>
                      <span>Version {row.version}</span>
                      <span>{new Date(row.occurred_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Africa/Lagos' })}</span>
                    </Button>
                  </li>
                ))}
              </ul>
              {list.next_page !== null && (
                <span>
                  <Button kind="secondary" busy={r.moreBusy} busyLabel="Loading…" onClick={() => void r.showMore()}>
                    More
                  </Button>
                  {r.moreFailed && <span className="retro__muted"> Try again shortly.</span>}
                </span>
              )}
            </Panel>
          )}

          {empty && !canRecord && (
            <EmptyState title="Nothing saved yet" level={2}>
              No retrospective has been saved for this project yet.
            </EmptyState>
          )}

          {form && (
            <Panel aria-label={empty ? 'Record the retrospective' : 'Save a new version'} bodyClassName="retro__stack">
              {editing && detail && (
                <p className="retro__muted">This starts from version {detail.version}. Saving adds a new version; the earlier one stays as it is.</p>
              )}
              <RetroForm
                key={editing ? `edit-${detail?.version_id}` : 'new'}
                options={options}
                optionsProblem={optionsProblem}
                revision={revision}
                initial={initialDraft(editing ? detail : null, defaultReference(now), now)}
                busy={r.saveBusy}
                failure={r.saveFailure}
                onSave={(body) => void save(body)}
                onCheckAgain={() => void r.checkAgain()}
                onReloadNotice={() => void r.reload()}
              />
              {editing && (
                <span>
                  <Button kind="secondary" disabled={r.saveBusy} onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                </span>
              )}
            </Panel>
          )}

          {!empty && !(form && editing) && (
            <Panel head={detail ? `Version ${detail.version}` : 'Saved version'} headingLevel={2} bodyClassName="retro__stack">
              {r.detail.status === 'loading' && <Loading>Loading…</Loading>}
              {r.detail.status === 'error' && <Problem error={r.detail.error} onRetry={() => void r.reload()} path={path} />}
              {detail && (
                <SavedVersion
                  detail={detail}
                  actionsLead={
                    list.can_manage_actions && options && detail.current ? (
                      <ActionForm
                        options={options}
                        lessons={parseSummary(detail.summary).boxes.lessons}
                        count={detail.actions.length}
                        taken={detail.actions.map((a) => a.reference)}
                        busy={r.actionBusy}
                        failure={r.actionFailure}
                        revision={revision}
                        meetingId={detail.id}
                        onCreate={r.createAction}
                      />
                    ) : undefined
                  }
                />
              )}
              {detail && detail.current && canRecord && (
                <div className="retro__actions">
                  <Button kind="primary" size="lg" onClick={() => setEditing(true)}>
                    Save new version
                  </Button>
                </div>
              )}
            </Panel>
          )}
        </div>

        <aside className="retro__aside" aria-label="Closure">
          <Callout kind="info" announce={false}>
            Closure can&rsquo;t start until a retrospective is saved. It goes into the closure report the PMO Lead decides on.
          </Callout>
          <ChecklistStrip checklist={r.checklist} used={r.used} />
        </aside>
      </div>
    </div>
  );
}
