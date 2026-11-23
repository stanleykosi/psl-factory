'use client';

// SCR-03 decision (/work/[id]/decide?task=<task id>) on the live task API. The only switches are the task's
// can_decide, can_claim and claimed_by_you; /me roles never decide what is offered (INV-ACCESS).
import { Button, Callout } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { DecidePanel } from './DecidePanel';
import { DecideHeader, DecisionRows, DecisionTrail } from './DecisionContent';
import { CannotActView, DoneView, NotOpenState, StaleView, UncertainNotice } from './DecideStates';
import { liveId } from './format';
import { queuePlace, queueText } from './presentation';
import { snapshotOf, useDecision } from './useDecision';

import '@/features/work-item/work-item.css';
import './decide.css';

/** The decide had an uncertain effect and the reload failed: say so plainly; Try again only reads the item. */
function UnconfirmedNotice({ checking, onRecheck }: { checking: boolean; onRecheck: () => void }) {
  return (
    <div role="alert">
      <Callout kind="warning" className="decide-retry">
        <strong>We couldn&rsquo;t confirm whether your decision was recorded.</strong> We also couldn&rsquo;t reload this item to check, so the
        decision buttons stay off. Try again reloads the item; it doesn&rsquo;t send your decision again.{' '}
        <Button kind="secondary" size="sm" busy={checking} busyLabel="Checking…" onClick={onRecheck}>
          Try again
        </Button>
      </Callout>
    </div>
  );
}

/**
 * The one layout map: which board a view follows, and the phone bar's way back for it. The actionable flow
 * (deciding, stale, done) goes back to the decisions; read-only and every other state to the queue. Both are
 * /my-work, the list that holds the decisions. Section order inside each board lives in decide.css.
 */
type Layout = 'decide' | 'stale' | 'done' | 'read-only' | 'other';
const BACK: Record<Layout, string> = { decide: 'Decisions', stale: 'Decisions', done: 'Decisions', 'read-only': 'Queue', other: 'Queue' };

export function DecideView({ id, taskId }: { id: string; taskId: string | undefined }) {
  const { view, claim, submit, uncertain, queue, commentState, comment, retry, retryClaim, decide, recheck, reviewCurrent } = useDecision(id, taskId);
  const pathname = `/work/${encodeURIComponent(id)}/decide${taskId ? `?task=${encodeURIComponent(taskId)}` : ''}`;
  const place = queuePlace(queue, liveId(id));
  const pager = queueText(place);

  const layout: Layout =
    view.kind === 'done'
      ? 'done'
      : view.kind === 'stale'
        ? 'stale'
        : view.kind === 'loading' || view.kind === 'error' || view.kind === 'notopen'
          ? 'other'
          : view.kind === 'forbidden' || !claim
            ? 'read-only'
            : 'decide';
  // The bar's mono note: the place in the decision list on the actionable boards, when the list holds this work.
  usePhoneBack({ label: BACK[layout], href: '/my-work', note: layout === 'decide' || layout === 'stale' ? pager?.toUpperCase() : undefined });

  if (view.kind === 'loading') return <LoadingState />;
  if (view.kind === 'error') {
    const { error } = view;
    if (error.kind === 'unauthenticated') {
      return (
        <>
          <h1 className="cmp-sr">Decision</h1>
          <SignedOutState pathname={pathname} />
        </>
      );
    }
    if (error.kind === 'forbidden' || error.kind === 'not_found') {
      // the decision page keeps the frame's title size on every state (F-16 criterion 6)
      return (
        <div className="decide-noaccess">
          <NoAccessState />
        </div>
      );
    }
    return (
      <>
        <h1 className="cmp-sr">Decision</h1>
        <WorkErrorCard
          message="We couldn’t load this decision. Your work is safe; nothing was changed."
          error={error}
          onRetry={() => void retry()}
        />
      </>
    );
  }
  if (view.kind === 'done') {
    return (
      <DoneView
        id={id}
        work={view.work}
        result={view.result}
        label={view.label}
        note={view.note}
        reloaded={view.reloaded}
        history={view.history}
        refreshFailed={view.refreshFailed}
        waiting={queue ? queue.filter((entry) => entry.id !== liveId(id)) : null}
      />
    );
  }
  if (view.kind === 'notopen') {
    return (
      <>
        <DecideHeader work={view.work} title={view.work?.title ?? 'Decision'} />
        <NotOpenState id={id} />
      </>
    );
  }

  const { work, read } = view;
  const trail = <DecisionTrail queue={pager} />;

  if (view.kind === 'stale') {
    return (
      <>
        <DecideHeader work={work} trail={trail} title={read.label} sub={work.title} quietOnPhone />
        {uncertain && <UncertainNotice />}
        <StaleView replaced={view.replaced} current={snapshotOf(read)} note={view.note} onReview={reviewCurrent} />
      </>
    );
  }

  const unconfirmed = view.kind === 'unconfirmed';
  if (layout === 'read-only' || !claim) {
    return (
      <>
        <DecideHeader work={work} trail={<>Decision</>} title={read.label} sub={work.title} />
        {uncertain && <UncertainNotice />}
        <CannotActView id={id} read={read} commentState={commentState} onComment={comment} />
      </>
    );
  }

  return (
    <>
      <DecideHeader work={work} trail={trail} title={read.label} sub={work.title} />
      {unconfirmed ? <UnconfirmedNotice checking={view.checking} onRecheck={recheck} /> : uncertain && <UncertainNotice />}
      <div className="decide-board">
        <div className="decide-main">
          <div className="decide-what">
            <DecisionRows read={read} />
          </div>
        </div>
        <aside className="decide-aside">
          <DecidePanel read={read} claim={claim} submit={submit} locked={unconfirmed} onDecide={(v, e, n) => void decide(v, e, n)} onRetryClaim={retryClaim} />
        </aside>
      </div>
    </>
  );
}
