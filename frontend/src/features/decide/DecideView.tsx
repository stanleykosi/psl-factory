'use client';

// SCR-03 decision (/work/[id]/decide?task=<task id>). The only switches are the task's you_can_act and
// cannot_act_reason from E-WORK-ITEM; /me roles never decide what is offered (INV-ACCESS).
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { FactsStrip } from '@/features/work-item/WorkItemOverview';
import { presentationOf } from '@/features/work-item/presentation';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import type { WorkItem } from '@/api/types';

import { DecidePanel } from './DecidePanel';
import { AgentNote, ApprovalChain, DecideHeader, DecisionRows, DecisionTrail, MiniLine, stationEyebrow } from './DecisionContent';
import { CannotActView, cannotActCopy, DoneView, NotOpenState, StaleView } from './DecideStates';
import { findDecisionTask } from './format';
import { decidePresentationOf, queueText } from './presentation';
import { useDecision } from './useDecision';

import '@/features/work-item/work-item.css';
import './decide.css';

function UncertainNotice() {
  return (
    <div className="psl-callout psl-callout--warning" role="alert">
      <WarningIcon />
      <span>We couldn&rsquo;t confirm your decision. We&rsquo;ve reloaded this item so you can see whether it was recorded.</span>
    </div>
  );
}

/** The decide had an uncertain effect and the reload failed: say so plainly; Try again only reads the item. */
function UnconfirmedNotice({ checking, onRecheck }: { checking: boolean; onRecheck: () => void }) {
  return (
    <div className="psl-callout psl-callout--warning decide-retry" role="alert">
      <WarningIcon />
      <span>
        <strong>We couldn&rsquo;t confirm whether your decision was recorded.</strong> We also couldn&rsquo;t reload this item to
        check, so the decision buttons stay off. Try again reloads the item; it doesn&rsquo;t send your decision again.
      </span>
      <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" disabled={checking} onClick={onRecheck}>
        {checking ? 'Checking…' : 'Try again'}
      </button>
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
  const { view, claim, submit, uncertain, retry, retryClaim, decide, recheck, reviewCurrent } = useDecision(id, taskId);
  const pathname = `/work/${encodeURIComponent(id)}/decide${taskId ? `?task=${encodeURIComponent(taskId)}` : ''}`;

  const item: WorkItem | undefined = 'item' in view ? view.item : undefined;
  const task = item && view.kind !== 'done' ? findDecisionTask(item, taskId) : undefined;
  const deco = decidePresentationOf(item);
  const queue = queueText(deco);
  const layout: Layout =
    view.kind === 'done'
      ? 'done'
      : view.kind === 'stale' && task
        ? 'stale'
        : !task || view.kind === 'loading' || view.kind === 'error'
          ? 'other'
          : view.kind === 'forbidden' || !task.you_can_act || !claim
            ? 'read-only'
            : 'decide';
  // The bar's mono note: the queue position on the actionable boards, the reference on the read-only ones.
  const note = layout === 'decide' || layout === 'stale' ? queue?.toUpperCase() : layout === 'read-only' && item ? item.reference : undefined;
  usePhoneBack({ label: BACK[layout], href: '/my-work', note });

  if (view.kind === 'loading') return <LoadingState />;
  if (view.kind === 'error') {
    const { error } = view;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') {
      // the decision page keeps the frame's title size on every state (F-16 criterion 6)
      return (
        <div className="decide-noaccess">
          <NoAccessState />
        </div>
      );
    }
    return (
      <WorkErrorCard
        message="We couldn’t load this decision. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }
  if (view.kind === 'done') {
    return (
      <DoneView
        id={id}
        item={view.item}
        result={view.result}
        label={view.label}
        reloaded={view.reloaded}
        refreshFailed={view.refreshFailed}
        view={deco}
      />
    );
  }

  const current: WorkItem = view.item;
  if (!task) {
    return (
      <>
        <DecideHeader item={current} title={current.title} />
        <NotOpenState id={id} />
      </>
    );
  }
  const title = deco?.subject ? `${task.title} · ${deco.subject}` : task.title;
  const sub = deco?.subject ? undefined : current.title;
  const trail = <DecisionTrail item={current} queue={queue} />;

  if (view.kind === 'stale') {
    const agent = deco?.agent?.note || deco?.agent?.phone_note ? <AgentNote id={id} agent={current.agent} view={deco.agent} mode="note" /> : undefined;
    return (
      <>
        <DecideHeader item={current} trail={trail} phoneEyebrow={stationEyebrow(current)} title={title} sub={sub} quietOnPhone />
        {uncertain && <UncertainNotice />}
        <StaleView replaced={view.replaced} current={task.decision} agent={agent} onReview={reviewCurrent} />
      </>
    );
  }

  const unconfirmed = view.kind === 'unconfirmed';
  if (layout === 'read-only' || !claim) {
    // the own board sets its tag at the end of the title line; the others inside the card
    const tag =
      task.cannot_act_reason === 'prepared_by_you' ? (
        <span className="psl-tag psl-tag--waiting decide-owntag">{cannotActCopy(task.cannot_act_reason, task).eyebrow}</span>
      ) : undefined;
    return (
      <>
        <DecideHeader item={current} trail={<>Decision · {current.reference}</>} title={title} sub={sub} tag={tag} />
        {uncertain && <UncertainNotice />}
        {/* After a 403 the reloaded task's reason wins; without one the generic copy shows. */}
        <CannotActView id={id} task={task} facts={current.facts} view={deco} />
      </>
    );
  }

  return (
    <>
      <DecideHeader item={current} trail={trail} phoneEyebrow={stationEyebrow(current)} title={title} sub={sub} />
      {unconfirmed ? <UnconfirmedNotice checking={view.checking} onRecheck={recheck} /> : uncertain && <UncertainNotice />}
      <div className="decide-board">
        <div className="decide-main">
          <MiniLine item={current} requiredRole={task.required_role} waiting={deco?.waiting} />
          <div className="decide-desktop-only">
            <FactsStrip facts={current.facts} details={presentationOf(current)?.facts} tones={presentationOf(current)?.fact_tones} paidNote={false} />
          </div>
          <div className="decide-what">
            <DecisionRows decision={task.decision} />
            <AgentNote id={id} agent={current.agent} view={deco?.agent} />
          </div>
          <ApprovalChain chain={task.decision.chain} />
        </div>
        <aside className="decide-aside">
          <DecidePanel
            item={current}
            task={task}
            claim={claim}
            submit={submit}
            locked={unconfirmed}
            onDecide={(v, n) => void decide(v, n)}
            onRetryClaim={retryClaim}
          />
        </aside>
      </div>
    </>
  );
}
