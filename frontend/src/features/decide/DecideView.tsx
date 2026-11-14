'use client';

// SCR-03 decision (/work/[id]/decide?task=<task id>). The only switches are the task's you_can_act and
// cannot_act_reason from E-WORK-ITEM; /me roles never decide what is offered (INV-ACCESS).
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { FactsStrip } from '@/features/work-item/WorkItemOverview';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import type { WorkItem } from '@/api/types';

import { DecidePanel } from './DecidePanel';
import { AgentNote, ApprovalChain, DecideHeader, DecisionRows, MiniLine, stationEyebrow } from './DecisionContent';
import { CannotActView, DoneView, NotOpenState, StaleView } from './DecideStates';
import { findDecisionTask } from './format';
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

export function DecideView({ id, taskId }: { id: string; taskId: string | undefined }) {
  const { view, claim, submit, uncertain, retry, retryClaim, decide, reviewCurrent } = useDecision(id, taskId);
  const pathname = `/work/${encodeURIComponent(id)}/decide${taskId ? `?task=${encodeURIComponent(taskId)}` : ''}`;

  if (view.kind === 'loading') return <LoadingState />;
  if (view.kind === 'error') {
    const { error } = view;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccessState />;
    return (
      <WorkErrorCard
        message="We couldn’t load this decision. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }
  if (view.kind === 'done') {
    return <DoneView id={id} item={view.item} result={view.result} label={view.label} reloaded={view.reloaded} refreshFailed={view.refreshFailed} />;
  }

  const item: WorkItem = view.item;
  const task = findDecisionTask(item, taskId);
  if (!task) {
    return (
      <>
        <DecideHeader item={item} title={item.title} />
        <NotOpenState id={id} />
      </>
    );
  }
  const header = <DecideHeader item={item} eyebrow={stationEyebrow(item)} title={task.title} sub={item.title} />;

  if (view.kind === 'stale') {
    return (
      <>
        {header}
        {uncertain && <UncertainNotice />}
        <StaleView replaced={view.replaced} current={task.decision} onReview={reviewCurrent} />
      </>
    );
  }

  if (view.kind === 'forbidden' || !task.you_can_act || !claim) {
    return (
      <>
        {header}
        {uncertain && <UncertainNotice />}
        {/* After a 403 the reloaded task's reason wins; without one the generic copy shows. */}
        <CannotActView id={id} task={task} />
      </>
    );
  }

  return (
    <>
      {header}
      {uncertain && <UncertainNotice />}
      <div className="decide-board">
        <div className="decide-main">
          <MiniLine item={item} requiredRole={task.required_role} />
          <DecisionRows decision={task.decision} />
          <ApprovalChain chain={task.decision.chain} />
          <div className="decide-desktop-only">
            <FactsStrip facts={item.facts} />
          </div>
          <AgentNote id={id} agent={item.agent} />
        </div>
        <div className="decide-aside">
          <DecidePanel item={item} task={task} claim={claim} submit={submit} onDecide={(v, n) => void decide(v, n)} onRetryClaim={retryClaim} />
        </div>
      </div>
    </>
  );
}
