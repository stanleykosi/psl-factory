'use client';

// SCR-16 RFP outcome (/work/[id]/outcome). What is offered comes only from rfp_outcome on E-WORK-ITEM (results,
// reasons, record_as, recorded); nothing from /me decides it (INV-ACCESS). Desktop pages sit inside the RFP
// frame drawn from `rfp`; phones show "← RFP" and the bar note instead. Times are WAT.
import { Button, useIsPhone, useToastWhen } from '@/components';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import type { ResponseWorkItem } from '@/features/response';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { InfoIcon } from '@/features/response/icons';

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

function Warning({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="psl-callout psl-callout--warning resp-retry" role="alert">
      <WarningIcon />
      <span>{children}</span>
      {action}
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
          <Button kind="secondary" size="sm" disabled={notice.checking} onClick={onRecheck}>
            {notice.checking ? 'Checking…' : 'Try again'}
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
  return (
    <div className="psl-callout psl-callout--problem" role="alert">
      <WarningIcon />
      <span>{message}</span>
    </div>
  );
}

function NotOpen({ id }: { id: string }) {
  return (
    <section className="psl-empty resp-notopen" aria-labelledby="rfp-notopen-title">
      <h2 id="rfp-notopen-title">This outcome isn&rsquo;t open here</h2>
      <p>It may have been recorded already, or you may not be able to record it. The work item shows where things stand.</p>
      <Link className="psl-btn psl-btn--secondary" href={work(id)}>
        Open the work item
      </Link>
    </section>
  );
}

/** The desktop header: the RFP frame, or without `rfp` the F-09 crumb and the section title. */
function Header({ id, item, title, phone }: { id: string; item: ResponseWorkItem; title: string; phone: boolean }) {
  if (phone) return null;
  if (item.rfp) return <RfpFrame id={id} item={item} rfp={item.rfp} fallback={title} />;
  return (
    <header className="resp-header">
      <p className="psl-crumb resp-crumb">
        <Link href="/my-work">QUEUE</Link> / {item.line.toUpperCase()} / {item.reference.toUpperCase()}
      </p>
      <h1 className="shell-title resp-title">{title}</h1>
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
  // The result of the submit is a toast; the page keeps the lasting record.
  useToastWhen(flow.justRecorded ? (RESULT_LABELS[flow.justRecorded as keyof typeof RESULT_LABELS] ?? '') : null, 'Outcome recorded.');

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
        {phone && <h1 className="shell-title">{recordedHeading(page.result)}</h1>}
        <div className="resp-next">
          <strong>What was recorded</strong>
          <span>Outcome: {RESULT_LABELS[page.result] ?? page.result}</span>
          <span>We couldn’t reload the work item, so only the result is shown. The work item shows where things stand now.</span>
        </div>
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
        {phone && <h1 className="shell-title">Record the outcome</h1>}
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
      {phone && <h1 className="shell-title">Record the outcome</h1>}
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
            <div className="psl-callout psl-callout--info">
              <InfoIcon />
              <span>
                The client doesn&rsquo;t log in. You record their decision with proof, such as the award or regret letter. Only roles PSL allows can
                record outcomes.
              </span>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
