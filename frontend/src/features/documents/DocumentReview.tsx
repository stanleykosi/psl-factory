'use client';

// SCR-08 document review (/projects/[caseId]/documents/[documentId]?v=<version>): read one drafted client document,
// see what changed and what was checked, approve it or return it with a note. The document comes from E-DOCUMENT
// (fields beyond the typed ones are mock proposals); the decision is the review task on the work item it names, with
// the same claim and decide writes as the decision page (useDecision). The controls exist only for a task whose
// you_can_act is true; /me roles never decide that (INV-ACCESS). Nothing here says the document was sent.
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';

import { Breadcrumb, Button, buttonClass, Callout, Loading, PageTitle, Tag, useIsPhone, useToast, type TagTone } from '@/components';
import { When } from '@/features/decide-v7/DecisionContent';
import { cannotActCopy, UncertainNotice } from '@/features/decide-v7/DecideStates';
import { findDecisionTask } from '@/features/decide-v7/format';
import { useDecision } from '@/features/decide-v7/useDecision';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { ProjectTabs, PANEL_ID } from '@/features/projects/ProjectTabs';
import { routeCaseId } from '@/features/projects/model';
import { useProject } from '@/features/projects/useProject';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import { amountsTag, draftedByText, firstFlag, parseVersion, sectionsOf, textOf, type DocumentView } from './documentModel';
import { AgentPanel, ChecksPanel, NoText, ReturnedBanner, Sections } from './DocumentParts';
import { ReviewControls } from './ReviewControls';
import { useDocument } from './useDocument';

import './document-review.css';

type Decision = ReturnType<typeof useDecision>;

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

/** The tab bar (and its counts when E-PROJECT answers). A failed project read leaves the bar without counts. */
function ProjectBar({ caseId }: { caseId: string }) {
  const { state } = useProject(caseId);
  return <ProjectTabs base={`/projects/${encodeURIComponent(caseId)}`} current="documents" counts={state.status === 'ready' ? state.journey.tab_counts : undefined} />;
}

/** The approval is told once, as a toast (D-151); the panel then has nothing more to say. */
function Approved({ doc, step }: { doc: DocumentView; step: { person?: unknown; decided_at?: string | null } }) {
  const toast = useToast();
  const told = useRef(false);
  useEffect(() => {
    if (told.current) return;
    told.current = true;
    toast.show(
      <>
        <strong>You approved v{doc.version}</strong>
        {textOf(step.person) && <> · {String(step.person)}</>}
        {step.decided_at && (
          <>
            {' · '}
            <When at={step.decided_at} />
          </>
        )}
        . Not sent to the client.
      </>,
    );
  }, [toast, doc.version, step.person, step.decided_at]);
  return null;
}

const READ_ONLY = 'This review isn’t open to you here.';

/** What sits where the controls would: the reason there are none, an unconfirmed write, or the approved notice. */
function ReviewNotice({ doc, review, taskId, reread }: { doc: DocumentView; review: Decision; taskId: string | undefined; reread: boolean }) {
  const { view } = review;
  if (view.kind === 'loading') {
    return (
      <Loading className="docrev__loading">
        Loading the review…
      </Loading>
    );
  }
  if (view.kind === 'error') {
    if (view.error.kind === 'forbidden' || view.error.kind === 'not_found') return <p className="docrev__plain">{READ_ONLY}</p>;
    return <WorkErrorCard message="We couldn’t load this review. Your work is safe; nothing was changed." error={view.error} onRetry={() => void review.retry()} />;
  }
  if (view.kind === 'done') {
    if (view.result.verdict === 'return') {
      if (doc.returned) return null;
      // The page shows what the backend returned: still recording until the re-read is back, then its own status.
      return reread ? (
        <div role="alert">
          <Callout kind="warning">
            We couldn&rsquo;t confirm the return was recorded. The document still reads &ldquo;{doc.status}&rdquo;.{' '}
            <Button kind="secondary" size="sm" onClick={() => void review.retry()}>
              Try again
            </Button>
          </Callout>
        </div>
      ) : (
        <p className="docrev__plain" role="status">
          Recording the return…
        </p>
      );
    }
    const step = view.reloaded && findDecisionTask(view.reloaded, taskId)?.decision.chain.steps.find((s) => s.status === 'approved');
    if (view.refreshFailed) {
      return (
        <div role="alert">
          <Callout kind="warning">
            We couldn&rsquo;t reload to confirm your approval was recorded.{' '}
            <Button kind="secondary" size="sm" onClick={() => void review.retry()}>
              Try again
            </Button>
          </Callout>
        </div>
      );
    }
    if (!view.reloaded) {
      return (
        <p className="docrev__plain" role="status">
          Checking that your approval was recorded…
        </p>
      );
    }
    if (!step) return <p className="docrev__plain">{READ_ONLY}</p>;
    return <Approved doc={doc} step={step} />;
  }
  if (view.kind === 'stale') {
    return (
      <div role="alert">
        <Callout kind="warning">
          This review changed while you were reading it, so nothing was recorded.{' '}
          <Button kind="secondary" size="sm" onClick={review.reviewCurrent}>
            Review the latest
          </Button>
        </Callout>
      </div>
    );
  }
  if (view.kind === 'unconfirmed') {
    return (
      <div role="alert">
        <Callout kind="warning">
          <strong>We couldn&rsquo;t confirm whether your decision was recorded.</strong> We also couldn&rsquo;t reload this item to check, so the decision buttons
          stay off. Try again reloads the item; it doesn&rsquo;t send your decision again.{' '}
          <Button kind="secondary" size="sm" busy={view.checking} busyLabel="Checking…" onClick={review.recheck}>
            Try again
          </Button>
        </Callout>
      </div>
    );
  }
  const task = findDecisionTask(view.item, taskId);
  if (!task) return <p className="docrev__plain">{READ_ONLY}</p>;
  const copy = cannotActCopy(task.cannot_act_reason, task);
  return (
    <p className="docrev__plain docrev__cannot">
      <strong>{copy.heading}</strong> {copy.text}
    </p>
  );
}

/** The status tag's colour: orange where a person must act (a returned document, or a review you can decide). */
function statusTone(doc: DocumentView, canAct: boolean): TagTone {
  if (doc.returned) return 'person';
  if (canAct) return 'person';
  return doc.review ? 'waiting' : 'neutral';
}

function DocumentBody({ doc, review, caseId, reread = false }: { doc: DocumentView; review: Decision | null; caseId: string | undefined; reread?: boolean }) {
  const phone = useIsPhone();
  const sections = sectionsOf(doc);
  const taskId = textOf(doc.review?.task_id);
  const base = caseId ? `/projects/${encodeURIComponent(caseId)}` : undefined;
  usePhoneBack({ label: textOf(doc.project_title) ?? 'Projects', href: base ?? '/projects', note: textOf(doc.reference) });

  const view = review?.view;
  const item = view && 'item' in view ? view.item : undefined;
  const task = item ? findDecisionTask(item, taskId) : undefined;
  const canAct = Boolean(task?.you_can_act) && (view?.kind === 'item' || view?.kind === 'unconfirmed' || view?.kind === 'stale');
  const returned = doc.returned;
  const version = doc.version;
  const claim = review?.claim ?? null;
  const showControls = !returned && view?.kind === 'item' && task?.you_can_act === true && claim !== null;
  const changes = task?.decision.changes;
  const changeItems = Array.isArray(changes?.items) ? changes.items.filter((t) => textOf(t)) : [];
  const flag = sections ? firstFlag(sections) : undefined;
  const amounts = amountsTag(doc);
  const note = item?.workspace?.agent_note;
  const drafted = draftedByText(doc);

  const crumb = [
    ...(textOf(doc.project_title) ? [{ label: textOf(doc.project_title)!, href: base }] : []),
    { label: 'Documents', href: undefined },
  ];

  if (view?.kind === 'error' && view.error.kind === 'unauthenticated') {
    return <SignedOutState pathname={`${base ?? '/projects'}/documents/${encodeURIComponent(doc.document_id)}?v=${encodeURIComponent(version)}`} />;
  }

  return (
    <div className="docrev">
      <header className="docrev__header">
        <div className="docrev__crumb">
          <Breadcrumb items={crumb} current={textOf(doc.reference)} />
        </div>
        <div className="docrev__titlerow">
          <PageTitle size={36} phoneSize={24}>
            {doc.title} · v{version}
          </PageTitle>
          {caseId && <ProjectBar caseId={caseId} />}
        </div>
        {textOf(doc.status) ? <Tag tone={statusTone(doc, canAct)} className="docrev__status">{doc.status}</Tag> : null}
      </header>
      <div role={caseId ? 'tabpanel' : undefined} id={caseId ? PANEL_ID : undefined} aria-label={caseId ? 'Documents' : undefined} className="docrev__panel">
        {phone && !returned && (
          <div className="docrev__phonetags">
            {doc.test_template === true && <Tag tone="waiting">TEST TEMPLATE</Tag>}
            {amounts && <Tag tone={amounts.tone}>{amounts.text.toUpperCase()}</Tag>}
          </div>
        )}
        {returned && (
          <>
            <ReturnedBanner returned={returned} version={version} />
            {note && note.lines.length > 0 && <AgentPanel agent={note.agent} lines={note.lines} next={Number(version) + 1} />}
            {!phone && (
              <div className="docrev__held">
                <Button disabled size="lg" reason="Not available yet">
                  Edit as v{Number(version) + 1}
                </Button>
              </div>
            )}
          </>
        )}
        {!returned && (drafted || changeItems.length > 0) && (
          <p className="docrev__drafted">
            {drafted}
            {changeItems.length > 0 && ` Changes since ${changes?.previous_label}: ${changeItems.join('; ')}.`}
          </p>
        )}
        <div className="docrev__board">
          {sections ? <Sections doc={doc} sections={sections} /> : <NoText doc={doc} />}
          {!returned && phone && flag && (
            <p className="docrev__flag">
              {flag.agent} flagged section {flag.number}: {flag.text}
            </p>
          )}
          <aside className="docrev__aside">
            {!returned && <ChecksPanel doc={doc} />}
            {!returned && review && !showControls && <ReviewNotice doc={doc} review={review} taskId={taskId} reread={reread} />}
            {!returned && !review && doc.review && <p className="docrev__plain">{READ_ONLY}</p>}
            {review && showControls && task && claim && (
              <ReviewControls
                version={version}
                roleLabel={textOf(doc.review?.role_label)}
                claim={claim}
                submit={review.submit}
                phone={phone}
                onDecide={(verdict, text) => void review.decide(verdict, text)}
                onRetryClaim={review.retryClaim}
              />
            )}
            {review?.uncertain && <UncertainNotice />}
          </aside>
        </div>
        {returned && phone && (
          <div className="psl-actionbar docrev__bar">
            <Button size="xl" block disabled reason="Not available yet">
              Edit as v{Number(version) + 1}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Reads the work item behind the review and re-reads the document after a decision. Rendered only with a work_id. */
function ReviewHost({ doc, workId, refresh, caseId }: { doc: DocumentView; workId: string; refresh: () => Promise<void>; caseId: string | undefined }) {
  // A returned document has nothing left to claim or decide on this version; the work item is read for the agent's note.
  const review = useDecision(workId, doc.returned ? undefined : textOf(doc.review?.task_id));
  const done = review.view.kind === 'done' ? review.view : null;
  const refreshed = useRef<unknown>(null);
  const [reread, setReread] = useState(false);
  useEffect(() => {
    if (!done || refreshed.current === done.result) return;
    refreshed.current = done.result;
    void refresh().then(() => setReread(true));
  }, [done, refresh]);
  return <DocumentBody doc={doc} review={review} caseId={caseId} reread={reread} />;
}

function DocumentLoaded({ routeCase, documentId, version }: { routeCase: string; documentId: string; version: string }) {
  const { state, retry, refresh } = useDocument(documentId, version);
  const pathname = `/projects/${encodeURIComponent(routeCase)}/documents/${encodeURIComponent(documentId)}?v=${encodeURIComponent(version)}`;

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <DocumentNoAccess />;
    return <WorkErrorCard message="We couldn’t load this document. Your work is safe; nothing was changed." error={error} onRetry={() => void retry()} />;
  }
  const { doc } = state;
  // A document of another project (or another version than the URL names) is never shown under this address.
  if ((textOf(doc.case_id) && doc.case_id !== routeCase) || doc.version !== version || doc.document_id !== documentId) return <DocumentNoAccess />;
  const caseId = textOf(doc.case_id);
  const workId = textOf(doc.review?.work_id);
  return (
    <>
      {state.refreshFailed && (
        <Callout kind="warning">
          We couldn&rsquo;t refresh this page, so it may be out of date.{' '}
          <Button kind="secondary" size="sm" onClick={() => void refresh()}>
            Try again
          </Button>
        </Callout>
      )}
      {workId ? <ReviewHost doc={doc} workId={workId} refresh={refresh} caseId={caseId} /> : <DocumentBody doc={doc} review={null} caseId={caseId} />}
    </>
  );
}

function DocumentRoute({ caseId, documentId }: { caseId: string; documentId: string }) {
  const params = useSearchParams();
  const me = useMe();
  usePhoneBack({ label: 'Projects', href: '/projects' });
  const version = parseVersion(params?.get('v'));
  if (!hasDestination(me, 'projects')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  // The latest version is never guessed: a missing or unreadable v is not found, and nothing is requested.
  if (!version) return <DocumentNoAccess />;
  return <DocumentLoaded key={`${documentId}:${version}`} routeCase={caseId} documentId={documentId} version={version} />;
}

/** /projects/<case_id>/documents/<document_id>?v=<version>. */
export function DocumentReviewPage({ caseId, documentId }: { caseId: string; documentId: string }) {
  return (
    <Suspense fallback={<LoadingState />}>
      <DocumentRoute caseId={routeCaseId(caseId)} documentId={routeCaseId(documentId)} />
    </Suspense>
  );
}
