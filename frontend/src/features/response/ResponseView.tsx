'use client';

// SCR-16 record a response (/work/[id]/respond?task=<task id>). The only switches are the task's you_can_act,
// the presence of its response block and its variant, all from E-WORK-ITEM; nothing from /me decides what is
// offered (INV-ACCESS). Times are WAT. No SAMPLE DATA tag: the boards draw none.
import Link from 'next/link';
import type { ReactNode } from 'react';

import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { currentStationIndex } from '@/features/work-item/labels';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import type { Recorded, ResponseTask, ResponseWorkItem, TaskResponse } from './contract';
import { CheckIcon, InfoIcon } from './icons';
import { formatClock, formatDay, plural, RECORDABLE } from './labels';
import { AgentAside, ClientResponseForm, SowSignatureForm } from './ResponseForm';
import { findTask, useResponse, type Notice } from './useResponse';
import { useIsPhone } from './usePhone';

import '@/features/work-item/work-item.css';
import './response.css';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

/** On the phone the boards draw the reference at the right of the bar; the frame's bar holds only the back link. */
function PhoneReference({ reference }: { reference?: string }) {
  return reference ? <span className="psl-mono resp-phoneref">{reference}</span> : null;
}

function Crumb({ item, response }: { item: ResponseWorkItem; response: TaskResponse }) {
  const project = response.context?.project;
  const document = response.context?.document;
  if (project) {
    return (
      <p className="psl-crumb resp-crumb">
        <Link href="/projects">PROJECTS</Link> / {project.title.toUpperCase()}
        {document && ` / DOCUMENTS / ${document.reference.toUpperCase()}`}
      </p>
    );
  }
  const current = currentStationIndex(item.stations);
  const station = current >= 0 ? ` · STATION ${current + 1} OF ${item.stations.length}` : '';
  return (
    <p className="psl-crumb resp-crumb">
      <Link href="/my-work">QUEUE</Link> / {item.line.toUpperCase()} / {item.reference.toUpperCase()}
      {station}
    </p>
  );
}

function Warning({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="psl-callout psl-callout--warning resp-retry" role="alert">
      <WarningIcon />
      <span>{children}</span>
      {action}
    </div>
  );
}

/** Notices that belong at the top of the page (stale, uncertain, unconfirmed). */
function PageNotice({ notice, onRecheck }: { notice: Notice | null; onRecheck: () => void }) {
  if (notice?.kind === 'stale') {
    return <Warning>This changed while you were recording. We&rsquo;ve reloaded it. Check the details and record again.</Warning>;
  }
  if (notice?.kind === 'uncertain') {
    return <Warning>We couldn&rsquo;t confirm your response was recorded. We&rsquo;ve reloaded this item so you can see whether it was.</Warning>;
  }
  if (notice?.kind === 'unconfirmed') {
    return (
      <Warning
        action={
          <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" disabled={notice.checking} onClick={onRecheck}>
            {notice.checking ? 'Checking…' : 'Try again'}
          </button>
        }
      >
        We couldn&rsquo;t confirm whether your response was recorded, and couldn&rsquo;t reload to check. Record stays off. Try again reloads the item;
        it doesn&rsquo;t send your response again.
      </Warning>
    );
  }
  return null;
}

/** Notices that sit just above Record (the server's 422 or 403 message, a failed claim). */
function FormNotice({ notice }: { notice: Notice | null }) {
  if (notice?.kind === 'problem') {
    return (
      <div className="psl-callout psl-callout--problem" role="alert">
        <WarningIcon />
        <span>{notice.message}</span>
      </div>
    );
  }
  if (notice?.kind === 'claim_failed') {
    return (
      <div className="psl-callout psl-callout--warning" role="alert">
        <WarningIcon />
        <span>We couldn&rsquo;t get this ready. Try again.</span>
      </div>
    );
  }
  return null;
}

function NotOpen({ id }: { id: string }) {
  return (
    <section className="psl-empty resp-notopen" aria-labelledby="resp-notopen-title">
      <h2 id="resp-notopen-title">This response isn&rsquo;t open here</h2>
      <p>It may have been recorded already or moved. The work item shows where things stand.</p>
      <Link className="psl-btn psl-btn--secondary" href={work(id)}>
        Open the work item
      </Link>
    </section>
  );
}

/** "Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at 15:04 with 1 proof file." */
function recordedSentence(recorded: Recorded, response: TaskResponse | undefined): string {
  const channel = recorded.received_via
    ? (response?.channels?.find((c) => c.value === recorded.received_via)?.label ?? recorded.received_via).toLowerCase()
    : undefined;
  const day = recorded.responded_at ? formatDay(recorded.responded_at) : undefined;
  const received = channel ? `received by ${channel}${day ? ` on ${day}` : ''}` : day ? `received on ${day}` : '';
  const by = `recorded by ${recorded.by.name} at ${formatClock(recorded.at)}`;
  const proof = recorded.proof_count !== undefined ? ` with ${plural(recorded.proof_count, 'proof file')}` : '';
  if (recorded.summary) return `${[recorded.summary, received, by].filter(Boolean).join(', ')}${proof}.`;
  const tail = [received, by].filter(Boolean).join(', ');
  return `${tail.charAt(0).toUpperCase()}${tail.slice(1)}${proof}.`;
}

function SuccessView({ id, before, task, recorded, next, responderId, station, phone }: {
  id: string;
  before: ResponseWorkItem;
  task: ResponseTask | undefined;
  recorded: Recorded | undefined;
  next: string[] | undefined;
  responderId: string | undefined;
  station: string | undefined;
  phone: boolean;
}) {
  const response = task?.response;
  const organisation = response?.responders.find((r) => r.id === responderId)?.organisation;
  const current = currentStationIndex(before.stations);
  const heading = station ?? (current >= 0 ? before.stations[current].name : (task?.title ?? before.title));
  return (
    <>
      {!phone && <p className="resp-eyebrow">{[before.reference, organisation].filter(Boolean).join(' · ').toUpperCase()}</p>}
      <div className="resp-titlerow">
        <h1 className="shell-title resp-title resp-title--tight">{heading}</h1>
        {phone && <PhoneReference reference={before.reference} />}
      </div>
      <div className="resp-success">
        <div className="psl-callout psl-callout--success" role="status">
          <CheckIcon />
          <span>
            <strong>Response recorded.</strong>
            {recorded && ` ${recordedSentence(recorded, response)}`}
          </span>
        </div>
        {next && next.length > 0 && (
          <div className="resp-next">
            <strong>What happens next</strong>
            {next.map((line, i) => (
              <span key={i}>{line}</span>
            ))}
          </div>
        )}
        <p className="resp-footnote">Recorded responses can&rsquo;t be edited. If something is wrong, record a correction; both stay in the history.</p>
        {phone ? (
          <div className="psl-actionbar resp-phonebar">
            <Link className="psl-btn psl-btn--dark psl-btn--lg psl-btn--block" href="/my-work">
              Back to my queue
            </Link>
          </div>
        ) : (
          <p className="resp-back">
            <Link className="psl-btn psl-btn--dark psl-btn--lg psl-btn--block" href={work(id)}>
              Back to the work item
            </Link>
          </p>
        )}
      </div>
    </>
  );
}

export function ResponseView({ id, taskId }: { id: string; taskId: string | undefined }) {
  const flow = useResponse(id, taskId);
  const phone = useIsPhone();
  const { view, notice } = flow;
  const pathname = `${work(id)}/respond${taskId ? `?task=${encodeURIComponent(taskId)}` : ''}`;
  const open = view.kind === 'form' && flow.task?.you_can_act === true && !!flow.response && RECORDABLE.has(flow.response.variant);
  // The phone bar's way back, as the SCR-16 phone boards draw it: the form goes back to the queue, the SOW form
  // to its document and the success view (and anything else) to the work item.
  usePhoneBack(
    open && flow.response?.variant === 'client_response'
      ? { label: 'Queue', href: '/my-work' }
      : { label: (open && flow.response?.context?.document?.label) || 'Work item', href: work(id) },
  );

  if (view.kind === 'loading') return <LoadingState />;
  if (view.kind === 'error') {
    const { error } = view;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccessState />;
    return (
      <WorkErrorCard
        message="We couldn’t load this response form. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void flow.retry()}
      />
    );
  }
  const recheck = () => void flow.recheck();

  if (view.kind === 'done') {
    return (
      <div className="resp-page">
        <PageNotice notice={notice} onRecheck={recheck} />
        <SuccessView
          id={id}
          before={view.before}
          task={findTask(view.before, taskId)}
          recorded={view.recorded}
          next={view.next}
          responderId={view.responderId}
          station={view.station}
          phone={phone}
        />
      </div>
    );
  }

  const item = view.item;
  const task = flow.task;
  const response = flow.response;
  if (!task || !response || !task.you_can_act || !RECORDABLE.has(response.variant)) {
    return (
      <div className="resp-page">
        <PageNotice notice={notice} onRecheck={recheck} />
        <NotOpen id={id} />
      </div>
    );
  }

  const sow = response.variant === 'sow_signature';
  const formProps = {
    task,
    response,
    entries: flow.entries,
    setEntry: flow.setEntry,
    proof: flow.proof,
    busy: flow.busy,
    locked: notice?.kind === 'unconfirmed',
    phone,
    onRecord: () => void flow.record(),
    notice: <FormNotice notice={notice} />,
  };
  const current = currentStationIndex(item.stations);
  const document = response.context?.document;

  return (
    <div className={phone ? 'resp-page resp-page--phone' : 'resp-page'}>
      <header className="resp-header">
        {!phone && <Crumb item={item} response={response} />}
        <div className="resp-titlerow">
          <h1 className={sow ? 'shell-title resp-title resp-title--tight' : 'shell-title resp-title'}>{phone && sow && current >= 0 ? item.stations[current].name : task.title}</h1>
          {phone && sow && <PhoneReference reference={document?.reference} />}
        </div>
        {!phone && !sow && response.intro && <p className="resp-intro">{response.intro}</p>}
      </header>
      <PageNotice notice={notice} onRecheck={recheck} />
      <div className="resp-board">
        <div className="resp-main">{sow ? <SowSignatureForm {...formProps} /> : <ClientResponseForm {...formProps} />}</div>
        {!phone && !sow && <AgentAside response={response} />}
        {!phone && sow && response.intro && (
          <aside className="resp-aside" aria-label="About this signature">
            <div className="psl-callout psl-callout--info">
              <InfoIcon />
              <span>{response.intro}</span>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
