'use client';

// SCR-16 record a response (/work/[id]/respond?task=<task id>). The only switches are the task's you_can_act,
// the presence of its response block and its variant, all from E-WORK-ITEM; nothing from /me decides what is
// offered (INV-ACCESS). Times are WAT. No SAMPLE DATA tag: the boards draw none.
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Breadcrumb, buttonClass, Button, Callout, EmptyState, formatDate, formatTime, PageTitle, useIsPhone } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { RfpFrame } from '@/features/rfp/RfpFrame';
import { currentStationIndex } from '@/features/work-item/labels';
import { NoAccessState, WorkErrorCard } from '@/features/work-item/WorkItemStates';

import type { Recorded, ResponseTask, ResponseWorkItem, TaskResponse } from './contract';
import { plural, RECORDABLE } from './labels';
import { AgentAside, ClientResponseForm, SowSignatureForm } from './ResponseForm';
import { TeamInputForm } from './TeamInputForm';
import { findTask, teamInputOpen, useResponse, type Notice } from './useResponse';

import '@/features/work-item/work-item.css';
import './response.css';
import '@/features/rfp/rfp.css';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

/** Whether this page records the task's response: you can act, its variant is one this page records, and team input has teams and an action. */
function recordable(task: ResponseTask | undefined, response: TaskResponse | undefined): response is TaskResponse {
  if (!task?.you_can_act || !response || !RECORDABLE.has(response.variant)) return false;
  return response.variant !== 'team_input' || teamInputOpen(response);
}

function Crumb({ item, response }: { item: ResponseWorkItem; response: TaskResponse }) {
  const project = response.context?.project;
  const document = response.context?.document;
  if (project) {
    const rest = document ? `${project.title} / Documents / ${document.reference}` : project.title;
    return <Breadcrumb items={[{ label: 'Projects', href: '/projects' }]} current={rest} />;
  }
  const current = currentStationIndex(item.stations);
  const station = current >= 0 ? ` · Station ${current + 1} of ${item.stations.length}` : '';
  return <Breadcrumb items={[{ label: 'Queue', href: '/my-work' }]} current={`${item.line} / ${item.reference}${station}`} />;
}

/** A warning that answers an action (stale, uncertain, unconfirmed): announced when it appears. */
function Warning({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div role="alert">
      <Callout kind="warning">
        {children} {action}
      </Callout>
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
          <Button kind="secondary" size="sm" busy={notice.checking} busyLabel="Checking…" onClick={onRecheck}>
            Try again
          </Button>
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
  if (notice?.kind === 'problem') return <Callout kind="problem">{notice.message}</Callout>;
  if (notice?.kind === 'claim_failed') {
    return (
      <div role="alert">
        <Callout kind="warning">We couldn&rsquo;t get this ready. Try again.</Callout>
      </div>
    );
  }
  return null;
}

function NotOpen({ id }: { id: string }) {
  return (
    <EmptyState
      title="This response isn’t open here"
      className="resp-notopen"
      action={
        <Link className={buttonClass('secondary')} href={work(id)}>
          Open the work item
        </Link>
      }
    >
      It may have been recorded already or moved. The work item shows where things stand.
    </EmptyState>
  );
}

/** "Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at 15:04 with 1 proof file." */
function recordedSentence(recorded: Recorded, response: TaskResponse | undefined): string {
  const channel = recorded.received_via
    ? (response?.channels?.find((c) => c.value === recorded.received_via)?.label ?? recorded.received_via).toLowerCase()
    : undefined;
  const day = recorded.responded_at ? formatDate(recorded.responded_at) : undefined;
  const received = channel ? `received by ${channel}${day ? ` on ${day}` : ''}` : day ? `received on ${day}` : '';
  const by = `recorded by ${recorded.by.name} at ${formatTime(recorded.at)}`;
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
      <PageTitle className="resp-title">{heading}</PageTitle>
      <div className="resp-success">
        <Callout kind="success">
          <strong>Response recorded.</strong>
          {recorded && ` ${recordedSentence(recorded, response)}`}
        </Callout>
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
            <Link className={buttonClass('dark', 'lg', true)} href="/my-work">
              Back to my queue
            </Link>
          </div>
        ) : (
          <p className="resp-back">
            <Link className={buttonClass('dark', 'lg', true)} href={work(id)}>
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
  const open = view.kind === 'form' && recordable(flow.task, flow.response);
  // Team input on an RFP (F-18): the phone bar goes back to the RFP, as the SCR-16 team input board draws it.
  const rfpBack = open && flow.response?.variant === 'team_input' && view.item.rfp !== undefined;
  // The phone bar's way back, as the SCR-16 phone boards draw it: the form goes back to the queue, the SOW form
  // to its document and the success view (and anything else) to the work item. The reference sits at the bar's
  // right on the SOW form (the document's) and on success (the item's).
  const note =
    view.kind === 'done' ? view.before.reference : open && flow.response?.variant === 'sow_signature' ? flow.response.context?.document?.reference : undefined;
  usePhoneBack(
    open && flow.response?.variant === 'client_response'
      ? { label: 'Queue', href: '/my-work' }
      : rfpBack
        ? { label: 'RFP', href: work(id) }
        : { label: (open && flow.response?.context?.document?.label) || 'Work item', href: work(id), note },
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
  if (!task || !recordable(task, response)) {
    return (
      <div className="resp-page">
        <PageTitle className="resp-title">{task?.title ?? 'Record a response'}</PageTitle>
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
    touched: flow.touched,
    onRecord: () => void flow.record(),
    notice: <FormNotice notice={notice} />,
  };
  const current = currentStationIndex(item.stations);

  if (response.variant === 'team_input') {
    const rfp = item.rfp;
    return (
      <div className={phone ? 'resp-page resp-page--phone' : 'resp-page'}>
        {phone ? (
          <PageTitle>Record team input</PageTitle>
        ) : rfp ? (
          <RfpFrame id={id} item={item} rfp={rfp} fallback={task.title} />
        ) : (
          <header className="resp-header">
            <Crumb item={item} response={response} />
            <PageTitle className="resp-title">{task.title}</PageTitle>
          </header>
        )}
        <PageNotice notice={notice} onRecheck={recheck} />
        <div className="resp-board">
          <div className="resp-main resp-main--team">
            <TeamInputForm {...formProps} heading={!phone} />
          </div>
          {!phone && response.intro && (
            <aside className="resp-aside resp-aside--team" aria-label="About team input">
              <Callout kind="info">{response.intro}</Callout>
            </aside>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={phone ? 'resp-page resp-page--phone' : 'resp-page'}>
      <header className="resp-header">
        {!phone && <Crumb item={item} response={response} />}
        <PageTitle className="resp-title">{phone && sow && current >= 0 ? item.stations[current].name : task.title}</PageTitle>
        {!phone && !sow && response.intro && <p className="resp-intro">{response.intro}</p>}
      </header>
      <PageNotice notice={notice} onRecheck={recheck} />
      <div className="resp-board">
        <div className="resp-main">{sow ? <SowSignatureForm {...formProps} /> : <ClientResponseForm {...formProps} />}</div>
        {!phone && !sow && <AgentAside response={response} />}
        {!phone && sow && response.intro && (
          <aside className="resp-aside" aria-label="About this signature">
            <Callout kind="info">{response.intro}</Callout>
          </aside>
        )}
      </div>
    </div>
  );
}
