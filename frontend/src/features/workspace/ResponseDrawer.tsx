'use client';

// F-31: "Record input" on a planning row opens F-18's team-input form in the shared Drawer (PROPOSAL, contract mock only).
// F-40: the same flow (ResponseFlow) also hosts the support-handover form in place on the work item, in a Panel.
// The form, its hook and every rule are F-18's, imported as they are: the Department picker lists the task's teams (minus
// any the response marks `disabled_reason`), one press claims only when the API asks and records once, and a 409, a
// network error or a 5xx re-reads before anything can be sent again. Nothing here decides which departments are waiting
// or who may record: the row's step, the task's `you_can_act` and its teams come from the response.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { ApiError } from '@/api/errors';
import { Button, Callout, Drawer, formatDayTime, Panel, useIsPhone } from '@/components';
import { asResponseItem, type TaskResponse } from '@/features/response';
import type { Recorded } from '@/features/response/contract';
import { SupportHandoverForm } from '@/features/response/SupportHandoverForm';
import { TeamInputForm } from '@/features/response/TeamInputForm';
import { handoverOpen, teamInputOpen, useResponse, type Entries } from '@/features/response/useResponse';
import type { WorkItem } from '@/features/work-item/labels';

import { teamDisabled } from './proposals';

import '@/features/response/response.css';

export const RESPONSE_TEXT = {
  loading: 'Loading…',
  notOpen: 'This input isn’t open here. Close this and check the item.',
  loadFailed: 'We couldn’t load this form. Nothing was recorded.',
  stale: 'This changed while you were recording. We’ve reloaded it. Check the details and record again.',
  uncertain: 'We couldn’t confirm your input was recorded. We’ve reloaded this item so you can see whether it was.',
  unconfirmed: 'We couldn’t confirm whether your input was recorded, and couldn’t reload to check. Record stays off. Try again reloads the item; it doesn’t send your input again.',
  teamGone: (name: string) => `${name} is no longer waiting. We’ve reloaded this item so you can see whether it was recorded.`,
  sentNoRefresh: 'Your input was sent, but we couldn’t refresh this page to confirm it. Reload to see where it stands.',
  claimFailed: 'We couldn’t get this ready. Try again.',
  tryAgain: 'Try again',
  checking: 'Checking…',
  close: 'Close',
  cancel: 'Cancel',
  done: (summary: string | undefined, at: string | undefined) =>
    `Recorded under your name${summary ? `: ${summary}` : ''}${at ? `, ${formatDayTime(at)}` : ''}`,
} as const;

/** F-40: a support-handover reply says "reply" where the team-input flow says "input". */
export const REPLY_TEXT = {
  ...RESPONSE_TEXT,
  notOpen: 'This reply isn’t open here. Check the item.',
  uncertain: 'We couldn’t confirm the reply was recorded. We’ve reloaded this item so you can see whether it was.',
  unconfirmed: 'We couldn’t confirm whether the reply was recorded, and couldn’t reload to check. Record stays off. Try again reloads the item; it doesn’t record the reply again.',
  sentNoRefresh: 'Your reply was submitted, but we couldn’t refresh this page to confirm it. Reload to see where it stands.',
} as const;

/** The task a step names, when it is a team-input or support-handover response in the same item; `open` is whether this person can record it now. */
export function responseTaskFor(item: WorkItem, taskId: string): { open: boolean; variant: 'team_input' | 'support_handover' } | undefined {
  const task = asResponseItem(item).tasks.find((t) => t.id === taskId);
  const response = task?.response;
  if (!task || !response) return undefined;
  if (response.variant === 'team_input') return { open: task.you_can_act === true && teamInputOpen(response), variant: 'team_input' };
  if (response.variant === 'support_handover') return { open: task.you_can_act === true && handoverOpen(response), variant: 'support_handover' };
  return undefined;
}

type FlowProps = {
  workId: string;
  taskId: string;
  /** Which form the task is; a handover reply is hosted in place, a team's input in the Drawer. */
  variant: 'team_input' | 'support_handover';
  /** The team of the pressed row, when the row names one. */
  teamKey?: string;
  /** The team the person chose is no longer waiting after a re-read: the page closes the Drawer and says so. */
  onTeamGone?: (name: string) => void;
  /** A handover reply: a 409 or an unclear result re-read an item that no longer offers the reply, so the page re-reads and says which. */
  onReplyMoved?: (why: 'stale' | 'uncertain') => void;
  /** Present for the Drawer only: the in-place panel has nothing to close. */
  onClose?: () => void;
  /** 200: the form is done; the page re-reads and tells the person. */
  onRecorded: (recorded: Recorded | undefined) => void;
  /** 401, 403 or 404: the page shows the signed-out or not-open view. */
  onAccessLost: (error: ApiError) => void;
  /** Where the flow is drawn: the Drawer or the Panel. `footer` is the Drawer's Cancel. */
  host: (body: ReactNode, footer: ReactNode) => ReactNode;
};

/** F-31's flow body (loading, error, form, the stale, uncertain and unconfirmed notices, recorded, access lost), hosted by the Drawer or, for a handover reply, the Panel. */
export function ResponseFlow({ workId, taskId, variant, teamKey, onClose, onRecorded, onAccessLost, onTeamGone, onReplyMoved, host }: FlowProps) {
  const flow = useResponse(workId, taskId);
  const phone = useIsPhone();
  const handover = variant === 'support_handover';
  const text = handover ? REPLY_TEXT : RESPONSE_TEXT;
  const { view, notice, task } = flow;
  // The row's team is chosen once, when the form first has its teams; after that the person's own choice stands.
  const preset = useRef(false);
  const [edited, setEdited] = useState(false);
  const finished = useRef(false);

  const flowResponse = flow.response;
  const response: TaskResponse | undefined = useMemo(
    () => flowResponse && (handover ? flowResponse : { ...flowResponse, teams: (flowResponse.teams ?? []).filter((t) => !teamDisabled(t)) }),
    [flowResponse, handover],
  );
  const open = Boolean(task?.you_can_act && response && (handover ? handoverOpen(response) : teamInputOpen(response)));

  const { setEntry } = flow;
  useEffect(() => {
    if (handover || preset.current || !teamKey || !open || !response?.teams?.some((t) => t.key === teamKey)) return;
    preset.current = true;
    setEntry('team', teamKey);
  }, [handover, open, response, teamKey, setEntry]);

  const errorKind = view.kind === 'error' ? view.error : undefined;
  useEffect(() => {
    if (errorKind && (errorKind.kind === 'unauthenticated' || errorKind.kind === 'forbidden' || errorKind.kind === 'not_found')) onAccessLost(errorKind);
  }, [errorKind, onAccessLost]);

  // UX-1-1: a re-read (after a lost reply or a 409) that no longer lists the team the person chose closes the Drawer, so a form for one team is never recorded for another
  const chosen = useRef<{ key: string; name: string } | null>(null);
  const teamKeyNow = flow.entries.team;
  useEffect(() => {
    if (handover) return;
    const teams = flow.response?.teams;
    if (!teams) return;
    if (teamKeyNow) {
      chosen.current = { key: teamKeyNow, name: teams.find((t) => t.key === teamKeyNow)?.name ?? teamKeyNow };
      return;
    }
    if (chosen.current && !finished.current) {
      const { name } = chosen.current;
      chosen.current = null;
      onTeamGone?.(name);
    }
  }, [handover, teamKeyNow, flow.response, onTeamGone]);

  // F-40: the re-read after a 409 or a lost reply no longer offers this reply (it was recorded, or the item moved on): the page re-reads too
  const moved = useRef(false);
  const noticeKind = notice?.kind;
  const gone = view.kind === 'form' && (!task || !open);
  useEffect(() => {
    if (!handover || moved.current || !gone || (noticeKind !== 'stale' && noticeKind !== 'uncertain')) return;
    moved.current = true;
    onReplyMoved?.(noticeKind);
  }, [handover, gone, noticeKind, onReplyMoved]);

  // a 403 on the write: the page shows the same not-open view as for any other refusal of access
  const refused = notice?.kind === 'problem' && notice.forbidden ? notice.message : undefined;
  useEffect(() => {
    if (refused !== undefined) onAccessLost(new ApiError(403, 'forbidden', 'forbidden', refused));
  }, [refused, onAccessLost]);

  const recorded = view.kind === 'done' ? view.recorded : undefined;
  const isDone = view.kind === 'done';
  useEffect(() => {
    if (!isDone || finished.current) return;
    finished.current = true;
    onRecorded(recorded);
  }, [isDone, recorded, onRecorded]);

  const edit = <K extends keyof Entries>(key: K, value: Entries[K]) => {
    setEdited(true);
    flow.setEntry(key, value);
  };

  const cancelButton = (
    <Button kind="secondary" onClick={onClose}>
      {text.cancel}
    </Button>
  );
  // the way out of a dead end: Close in the Drawer; the in-place panel can only read again
  const leave = onClose ? (
    <Button kind="secondary" onClick={onClose}>
      {text.close}
    </Button>
  ) : (
    <Button kind="secondary" onClick={() => void flow.retry()}>
      {text.tryAgain}
    </Button>
  );

  // on a phone the sheet has its own Close and F-18's Record bar is pinned at the bottom, so Cancel is the desktop footer's
  const showCancel = view.kind === 'form' && open && !phone && onClose !== undefined;

  let body;
  if (view.kind === 'loading' || view.kind === 'done') body = <p>{text.loading}</p>;
  else if (view.kind === 'error') {
    body = (
      <>
        <Callout kind="problem">{text.loadFailed}</Callout>
        {leave}
      </>
    );
  } else if (!task || !response || !open) {
    body = (
      <>
        <p>{text.notOpen}</p>
        {leave}
      </>
    );
  } else {
    const unconfirmed = notice?.kind === 'unconfirmed';
    const common = {
      task,
      response,
      entries: flow.entries,
      setEntry: edit,
      proof: flow.proof,
      busy: flow.busy,
      locked: unconfirmed,
      touched: edited || flow.proof.files.length > 0,
      onRecord: () => void flow.record(),
      notice: (
        <>
          {notice?.kind === 'problem' && <Callout kind="problem">{notice.message}</Callout>}
          {notice?.kind === 'claim_failed' && <Callout kind="warning">{text.claimFailed}</Callout>}
        </>
      ),
    };
    body = (
      <>
        {/* the handover's intro is the form's footnote, as the board draws it */}
        {!handover && response.intro && <Callout kind="info">{response.intro}</Callout>}
        {notice?.kind === 'stale' && <Callout kind="warning">{text.stale}</Callout>}
        {notice?.kind === 'uncertain' && <Callout kind="warning">{text.uncertain}</Callout>}
        {unconfirmed && (
          <Callout kind="warning">
            <span>{text.unconfirmed}</span>{' '}
            <Button kind="secondary" disabled={notice.checking} onClick={() => void flow.recheck()}>
              {notice.checking ? text.checking : text.tryAgain}
            </Button>
          </Callout>
        )}
        {handover ? (
          <SupportHandoverForm {...common} phone={phone} gapsProblem={notice?.kind === 'problem' && /\bgaps\b/.test(notice.message)} />
        ) : (
          // one column with a pinned Record bar, as the board's Drawer draws it, at either width
          <TeamInputForm {...common} phone heading={false} />
        )}
      </>
    );
  }

  return host(body, showCancel ? cancelButton : undefined);
}

type Props = {
  workId: string;
  taskId: string;
  title: string;
  /** The team of the pressed row, when the row names one. */
  teamKey?: string;
  /** The project's title from the response (the Drawer's eyebrow). */
  eyebrow?: string;
  onTeamGone: (name: string) => void;
  onClose: () => void;
  onRecorded: (recorded: Recorded | undefined) => void;
  onAccessLost: (error: ApiError) => void;
};

export function ResponseDrawer({ workId, taskId, title, teamKey, eyebrow, onClose, onRecorded, onAccessLost, onTeamGone }: Props) {
  return (
    <ResponseFlow
      workId={workId}
      taskId={taskId}
      variant="team_input"
      teamKey={teamKey}
      onClose={onClose}
      onRecorded={onRecorded}
      onAccessLost={onAccessLost}
      onTeamGone={onTeamGone}
      host={(body, footer) => (
        <Drawer title={title} eyebrow={eyebrow} onClose={onClose} footer={footer}>
          <div className="ws-respdrawer">{body}</div>
        </Drawer>
      )}
    />
  );
}

/** F-40: the support-handover reply, drawn in place on the work item (the boards have no button to open it). */
export function ResponsePanel(props: Omit<FlowProps, 'variant' | 'host' | 'onClose'> & { title: string }) {
  const { title, ...rest } = props;
  return (
    <ResponseFlow
      {...rest}
      variant="support_handover"
      host={(body) => (
        <Panel head={title} headingLevel={2} className="ws-respinline">
          <div className="ws-respdrawer">{body}</div>
        </Panel>
      )}
    />
  );
}
