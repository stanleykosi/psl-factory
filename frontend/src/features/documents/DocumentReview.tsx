'use client';

// SCR-08 document review (/projects/[caseId]/documents/[documentId]): read one drafted client document by its live
// version id, approve it or return it with a note. The reads are the document-review preview and (for the status word
// and blockers) the publication read; the write is the document-review decision, with the revision the preview gave.
// The controls exist only for the verdicts the preview offers (INV-ACCESS). Nothing here says the document was sent.
import Link from 'next/link';
import { useCallback } from 'react';

import { Breadcrumb, Button, buttonClass, Callout, PageTitle, Tag, useIsPhone, useToast } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { ProjectTabs, PANEL_ID } from '@/features/projects/ProjectTabs';
import { routeCaseId } from '@/features/projects/model';
import { useProject } from '@/features/projects/useProject';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import { isVersionId, textOf, verdictsOf, type LiveDocument, type Publication, type Verdict } from './documentModel';
import { AudiencePanel, Blockers, Sections } from './DocumentParts';
import { ReviewControls } from './ReviewControls';
import { useDocument } from './useDocument';
import { useReview } from './useReview';

import './document-review.css';

/** 403 and 404 look the same (INV-ACCESS): nothing about the document is shown, not even its title or id. */
function DocumentNoAccess() {
  return (
    <section className="psl-panel docrev__noaccess" aria-label="No access">
      <div className="psl-panel__body">
        <Tag tone="neutral">NOT OPEN TO YOU</Tag>
        <PageTitle>You can&rsquo;t open this document</PageTitle>
        <p className="docrev__plain">It belongs to a project you don&rsquo;t have access to, or it isn&rsquo;t there. Nothing about it is shown here.</p>
        <p className="docrev__plain">
          <Link className={buttonClass('dark', 'lg')} href="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    </section>
  );
}

const NOTICE_ID = 'docrev-notice';

/** The notices that outlive the controls: why a decision was not recorded, or that it may not have been. */
function ReviewNotice({ submit, recheck }: { submit: ReturnType<typeof useReview>['submit']; recheck: () => void }) {
  if (submit.status === 'refused') {
    return (
      <div role="alert">
        <Callout kind="warning" id={NOTICE_ID}>
          {submit.message}
        </Callout>
      </div>
    );
  }
  if (submit.status !== 'uncertain' && submit.status !== 'unconfirmed') return null;
  return (
    <div role="alert">
      <Callout kind="warning" id={NOTICE_ID}>
        <strong>
          {submit.status === 'uncertain' ? 'We couldn’t confirm whether your decision was recorded.' : 'We couldn’t reload to confirm it was recorded.'}
        </strong>{' '}
        The decision buttons stay off. Try again reloads the document; it doesn&rsquo;t send your decision again.{' '}
        <Button kind="secondary" size="sm" busy={submit.checking} busyLabel="Checking…" onClick={recheck}>
          Try again
        </Button>
      </Callout>
    </div>
  );
}

function DocumentBody({ caseId, versionId, doc, publication, refreshFailed, refresh }: { caseId: string; versionId: string; doc: LiveDocument; publication: Publication | null; refreshFailed: boolean; refresh: () => Promise<boolean> }) {
  const phone = useIsPhone();
  const toast = useToast();
  const project = useProject(caseId);
  const base = `/projects/${encodeURIComponent(caseId)}`;
  const title = project.state.status === 'ready' ? textOf(project.state.journey.title) : undefined;
  usePhoneBack({ label: title ?? 'Projects', href: base });

  const version = doc.version;
  const onRecorded = useCallback(
    (verdict: Verdict) =>
      toast.show(verdict === 'approve' ? <><strong>You approved v{version}</strong>. Not sent to the client.</> : <strong>You returned v{version}.</strong>),
    [toast, version],
  );
  const { submit, decide, recheck } = useReview({ caseId, versionId, revision: doc.revision, refresh, onRecorded });

  const verdicts = verdictsOf(doc);
  const status = textOf(publication?.review_status);
  const findings = publication?.findings ?? [];
  const held = submit.status === 'uncertain' || submit.status === 'unconfirmed';
  const crumb = [...(title ? [{ label: title, href: base }] : []), { label: 'Documents', href: undefined }];

  if (submit.status === 'signed_out') return <SignedOutState pathname={`${base}/documents/${versionId}`} />;

  return (
    <div className="docrev">
      {refreshFailed && !held && (
        <Callout kind="warning">
          We couldn&rsquo;t refresh this page, so it may be out of date.{' '}
          <Button kind="secondary" size="sm" onClick={() => void refresh()}>
            Try again
          </Button>
        </Callout>
      )}
      <header className="docrev__header">
        <div className="docrev__crumb">
          <Breadcrumb items={crumb} />
        </div>
        <div className="docrev__titlerow">
          <PageTitle size={36} phoneSize={24}>
            {doc.title} · v{version}
          </PageTitle>
          <ProjectTabs base={base} current="documents" tabs={project.state.status === 'ready' ? project.state.journey.tabs : undefined} />
        </div>
        <div className="docrev__tags">
          {status && (
            <Tag tone={verdicts.length > 0 ? 'person' : 'neutral'} className="docrev__status">
              {status}
            </Tag>
          )}
          {!doc.current && <Tag tone="neutral">Not the current version</Tag>}
        </div>
      </header>
      <div role="tabpanel" id={PANEL_ID} aria-label="Documents" className="docrev__panel">
        <div className="docrev__board">
          <Sections doc={doc} />
          <aside className="docrev__aside">
            <AudiencePanel audience={doc.audience} />
            {findings.length > 0 && <Blockers findings={findings} />}
            <ReviewNotice submit={submit} recheck={() => void recheck()} />
            {verdicts.length > 0 ? (
              <ReviewControls version={version} verdicts={verdicts} submit={submit} heldBy={held || submit.status === 'refused' ? NOTICE_ID : undefined} phone={phone} onDecide={(verdict, note) => void decide(verdict, note)} />
            ) : (
              <p className="docrev__plain docrev__cannot">No decision is open to you on this version.</p>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

function DocumentLoaded({ caseId, versionId }: { caseId: string; versionId: string }) {
  const { state, retry, refresh } = useDocument(caseId, versionId);
  const pathname = `/projects/${encodeURIComponent(caseId)}/documents/${versionId}`;

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <DocumentNoAccess />;
    return <WorkErrorCard message="We couldn’t load this document. Your work is safe; nothing was changed." error={error} onRetry={() => void retry()} />;
  }
  return <DocumentBody caseId={caseId} versionId={versionId} doc={state.doc} publication={state.publication} refreshFailed={state.refreshFailed} refresh={refresh} />;
}

function DocumentRoute({ caseId, documentId }: { caseId: string; documentId: string }) {
  const me = useMe();
  usePhoneBack({ label: 'Projects', href: '/projects' });
  if (!hasDestination(me, 'projects')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  // The latest version is never guessed: an id that is not a whole version number is not found, and nothing is requested.
  if (!isVersionId(documentId)) return <DocumentNoAccess />;
  return <DocumentLoaded key={`${caseId}:${documentId}`} caseId={caseId} versionId={documentId} />;
}

/** /projects/<case_id>/documents/<version_id>. */
export function DocumentReviewPage({ caseId, documentId }: { caseId: string; documentId: string }) {
  return <DocumentRoute caseId={routeCaseId(caseId)} documentId={routeCaseId(documentId)} />;
}
