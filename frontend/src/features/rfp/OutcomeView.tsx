'use client';

// SCR-16 RFP outcome (/work/[id]/outcome). What is offered comes only from rfp_outcome on E-WORK-ITEM (results,
// reasons, record_as, recorded); nothing from /me decides it (INV-ACCESS). Desktop pages sit inside the RFP
// frame drawn from `rfp`; phones show "← RFP" and the bar note instead. Times are WAT.
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Breadcrumb, Button, buttonClass, Callout, EmptyState, PageTitle, useIsPhone } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import type { ResponseWorkItem } from '@/features/response';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { frameHeading, RESULT_LABELS, recordedHeading, resultNote } from './labels';
import { FollowupCard } from './FollowupCard';
import { OutcomeForm } from './OutcomeForm';
import { RecordedView } from './RecordedView';
import { RfpFrame } from './RfpFrame';
import { outcomeOpen, useOutcome, type OutcomeNotice } from './useOutcome';

import '@/features/work-item/work-item.css';
import '@/features/response/response.css';
import './rfp.css';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

/** A warning that answers an action: announced when it appears. */
function Warning({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div role="alert">
      <Callout kind="warning">
        {children} {action}
      </Callout>
    </div>
  );
}

function PageNotice({ notice, onRecheck }: { notice: OutcomeNotice | null; onRecheck: () => void }) {
  if (notice?.kind === 'stale') {
    return <Warning>This changed while you were recording. We&rsquo;ve reloaded it. Check the details and record again.</Warning>;
  }
  if (notice?.kind === 'uncertain') {
    return <Warning>We couldn&rsquo;t confirm the outcome was recorded. We&rsquo;ve reloaded this item so you can see whether it was.</Warning>;
  }
  if (notice?.kind === 'unconfirmed') {
    return (
      <Warning
        action={
          <Button kind="secondary" size="sm" busy={notice.checking} busyLabel="Checking…" onClick={onRecheck}>
            Try again
          </Button>
        }
      >
        We couldn&rsquo;t confirm whether the outcome was recorded, and couldn&rsquo;t reload to check. Record stays off. Try again reloads the item;
        it doesn&rsquo;t record the outcome again.
      </Warning>
    );
  }
  return null;
}

function Problem({ message }: { message: string }) {
  return <Callout kind="problem">{message}</Callout>;
}

function NotOpen({ id }: { id: string }) {
  return (
    <EmptyState
      title="This outcome isn’t open here"
      className="resp-notopen"
      action={
        <Link className={buttonClass('secondary')} href={work(id)}>
          Open the work item
        </Link>
      }
    >
      It may have been recorded already, or you may not be able to record it. The work item shows where things stand.
    </EmptyState>
  );
}

/** The desktop header: the RFP frame, or without `rfp` the F-09 crumb and the section title. */
function Header({ id, item, title, phone }: { id: string; item: ResponseWorkItem; title: string; phone: boolean }) {
  if (phone) return null;
  if (item.rfp) return <RfpFrame id={id} item={item} rfp={item.rfp} fallback={title} />;
  return (
    <header className="resp-header">
      <Breadcrumb items={[{ label: 'Queue', href: '/my-work' }]} current={`${item.line} / ${item.reference}`} />
      <PageTitle className="resp-title">{title}</PageTitle>
    </header>
  );
}

export function OutcomeView({ id }: { id: string }) {
  const flow = useOutcome(id);
  const phone = useIsPhone();
  const { page, notice } = flow;
  const item = page.kind === 'item' || page.kind === 'refused' ? page.item : page.kind === 'recorded' ? page.before : undefined;
  const recorded = page.kind === 'item' ? item?.rfp_outcome?.recorded : undefined;
  const showRecorded = recorded !== undefined && !flow.reopened;
  const formOpen = page.kind === 'item' && !showRecorded && outcomeOpen(item?.rfp_outcome);
  const note = page.kind === 'recorded' ? resultNote(page.result) : showRecorded ? resultNote(recorded.result) : formOpen ? 'OUTCOME' : undefined;
  usePhoneBack({ label: item?.rfp ? 'RFP' : 'Work item', href: work(id), note });

  if (page.kind === 'loading') return <LoadingState />;
  if (page.kind === 'error') {
    const { error } = page;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={`${work(id)}/outcome`} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccessState />;
    return <WorkErrorCard message="We couldn’t load this outcome. Your work is safe; nothing was changed." error={error} onRetry={() => void flow.retry()} />;
  }
  const recheck = () => void flow.recheck();
  const current = item!;

  if (page.kind === 'recorded') {
    return (
      <div className="resp-page rfp-page">
        <Header id={id} item={current} title={recordedHeading(page.result)} phone={phone} />
        {phone && <PageTitle>{recordedHeading(page.result)}</PageTitle>}
        <Callout kind="success">
          <strong>Outcome recorded.</strong> {RESULT_LABELS[page.result] ?? ''}
        </Callout>
      </div>
    );
  }

  if (showRecorded) {
    return (
      <div className={phone ? 'resp-page resp-page--phone rfp-page' : 'resp-page rfp-page'}>
        <Header id={id} item={current} title={recordedHeading(recorded.result)} phone={phone} />
        <PageNotice notice={notice} onRecheck={recheck} />
        <RecordedView
          outcome={current.rfp_outcome!}
          recorded={recorded}
          title={phone ? 'h1' : current.rfp && frameHeading(current.rfp) ? 'h2' : 'none'}
          onReopen={flow.reopen}
          followup={
            recorded.result === 'unknown' && current.rfp_outcome!.followup ? (
              <FollowupCard item={current} followup={current.rfp_outcome!.followup} reload={flow.refresh} />
            ) : undefined
          }
        />
      </div>
    );
  }

  if (!formOpen || page.kind !== 'item') {
    return (
      <div className="resp-page rfp-page">
        <Header id={id} item={current} title="Record the outcome" phone={phone} />
        {phone && <PageTitle>Record the outcome</PageTitle>}
        <PageNotice notice={notice} onRecheck={recheck} />
        {page.kind === 'refused' && <Problem message={page.message} />}
        <NotOpen id={id} />
      </div>
    );
  }

  const outcome = current.rfp_outcome!;
  return (
    <div className={phone ? 'resp-page resp-page--phone rfp-page' : 'resp-page rfp-page'}>
      <Header id={id} item={current} title="Record the outcome" phone={phone} />
      {phone && <PageTitle>Record the outcome</PageTitle>}
      <PageNotice notice={notice} onRecheck={recheck} />
      <div className="resp-board">
        <div className="resp-main rfp-main">
          <OutcomeForm
            outcome={outcome}
            client={current.rfp?.client}
            entries={flow.entries}
            setEntry={flow.setEntry}
            proof={flow.proof}
            busy={flow.busy}
            locked={notice?.kind === 'unconfirmed'}
            phone={phone}
            touched={flow.touched}
            onRecord={() => void flow.record()}
            notice={notice?.kind === 'problem' ? <Problem message={notice.message} /> : undefined}
          />
        </div>
        {!phone && (
          <aside className="resp-aside" aria-label="About recording the outcome">
            <Callout kind="info">
              The client doesn&rsquo;t log in. You record their decision with proof, such as the award or regret letter. Only roles PSL allows can
              record outcomes.
            </Callout>
          </aside>
        )}
      </div>
    </div>
  );
}
