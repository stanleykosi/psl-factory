'use client';

// F-31: "Record input" on a planning row opens F-18's team-input form in the shared Drawer (PROPOSAL, contract mock only).
// The form, its hook and every rule are F-18's, imported as they are: the Department picker lists the task's teams (minus
// any the response marks `disabled_reason`), one press claims only when the API asks and records once, and a 409, a
// network error or a 5xx re-reads before anything can be sent again. Nothing here decides which departments are waiting
// or who may record: the row's step, the task's `you_can_act` and its teams come from the response.
import { useEffect, useMemo, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { Button, Callout, Drawer, formatDayTime, useIsPhone } from '@/components';
import { asResponseItem, type TaskResponse } from '@/features/response';
import type { Recorded } from '@/features/response/contract';
import { TeamInputForm } from '@/features/response/TeamInputForm';
import { teamInputOpen, useResponse, type Entries } from '@/features/response/useResponse';
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

/** The task a step names, when it is a team-input response in the same item; `open` is whether this person can record it now. */
export function responseTaskFor(item: WorkItem, taskId: string): { open: boolean } | undefined {
  const task = asResponseItem(item).tasks.find((t) => t.id === taskId);
  const response = task?.response;
  if (!task || !response || response.variant !== 'team_input') return undefined;
  return { open: task.you_can_act === true && teamInputOpen(response) };
}

type Props = {
  workId: string;
  taskId: string;
  title: string;
  /** The team of the pressed row, when the row names one. */
  teamKey?: string;
  /** The project's title from the response (the Drawer's eyebrow). */
  eyebrow?: string;
  /** The team the person chose is no longer waiting after a re-read: the page closes the Drawer and says so. */
  onTeamGone: (name: string) => void;
  onClose: () => void;
  /** 200: the drawer is done; the page re-reads and tells the person. */
  onRecorded: (recorded: Recorded | undefined) => void;
  /** 401, 403 or 404: the page shows the signed-out or not-open view. */
  onAccessLost: (error: ApiError) => void;
};

export function ResponseDrawer({ workId, taskId, title, teamKey, eyebrow, onClose, onRecorded, onAccessLost, onTeamGone }: Props) {
  const flow = useResponse(workId, taskId);
  const phone = useIsPhone();
  const { view, notice, task } = flow;
  // The row's team is chosen once, when the form first has its teams; after that the person's own choice stands.
  const preset = useRef(false);
  const [edited, setEdited] = useState(false);
  const finished = useRef(false);

  const flowResponse = flow.response;
  const response: TaskResponse | undefined = useMemo(() => flowResponse && { ...flowResponse, teams: (flowResponse.teams ?? []).filter((t) => !teamDisabled(t)) }, [flowResponse]);
  const open = Boolean(task?.you_can_act && response && teamInputOpen(response));

  const { setEntry } = flow;
  useEffect(() => {
    if (preset.current || !teamKey || !open || !response?.teams?.some((t) => t.key === teamKey)) return;
    preset.current = true;
    setEntry('team', teamKey);
  }, [open, response, teamKey, setEntry]);

  const errorKind = view.kind === 'error' ? view.error : undefined;
  useEffect(() => {
    if (errorKind && (errorKind.kind === 'unauthenticated' || errorKind.kind === 'forbidden' || errorKind.kind === 'not_found')) onAccessLost(errorKind);
  }, [errorKind, onAccessLost]);

  // UX-1-1: a re-read (after a lost reply or a 409) that no longer lists the team the person chose closes the Drawer, so a form for one team is never recorded for another
  const chosen = useRef<{ key: string; name: string } | null>(null);
  const teamKeyNow = flow.entries.team;
  useEffect(() => {
    const teams = flow.response?.teams;
    if (!teams) return;
    if (teamKeyNow) {
      chosen.current = { key: teamKeyNow, name: teams.find((t) => t.key === teamKeyNow)?.name ?? teamKeyNow };
      return;
    }
    if (chosen.current && !finished.current) {
      const { name } = chosen.current;
      chosen.current = null;
      onTeamGone(name);
    }
  }, [teamKeyNow, flow.response, onTeamGone]);

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
      {RESPONSE_TEXT.cancel}
    </Button>
  );

  // on a phone the sheet has its own Close and F-18's Record bar is pinned at the bottom, so Cancel is the desktop footer's
  const showCancel = view.kind === 'form' && open && !phone;

  let body;
  if (view.kind === 'loading' || view.kind === 'done') body = <p>{RESPONSE_TEXT.loading}</p>;
  else if (view.kind === 'error') {
    body = (
      <>
        <Callout kind="problem">{RESPONSE_TEXT.loadFailed}</Callout>
        <Button kind="secondary" onClick={onClose}>
          {RESPONSE_TEXT.close}
        </Button>
      </>
    );
  } else if (!task || !response || !open) {
    body = (
      <>
        <p>{RESPONSE_TEXT.notOpen}</p>
        <Button kind="secondary" onClick={onClose}>
          {RESPONSE_TEXT.close}
        </Button>
      </>
    );
  } else {
    const unconfirmed = notice?.kind === 'unconfirmed';
    body = (
      <>
        {response.intro && <Callout kind="info">{response.intro}</Callout>}
        {notice?.kind === 'stale' && <Callout kind="warning">{RESPONSE_TEXT.stale}</Callout>}
        {notice?.kind === 'uncertain' && <Callout kind="warning">{RESPONSE_TEXT.uncertain}</Callout>}
        {unconfirmed && (
          <Callout kind="warning">
            <span>{RESPONSE_TEXT.unconfirmed}</span>{' '}
            <Button kind="secondary" disabled={notice.checking} onClick={() => void flow.recheck()}>
              {notice.checking ? RESPONSE_TEXT.checking : RESPONSE_TEXT.tryAgain}
            </Button>
          </Callout>
        )}
        <TeamInputForm
          task={task}
          response={response}
          entries={flow.entries}
          setEntry={edit}
          proof={flow.proof}
          busy={flow.busy}
          locked={unconfirmed}
          // one column with a pinned Record bar, as the board's Drawer draws it, at either width
          phone
          touched={edited || flow.proof.files.length > 0}
          onRecord={() => void flow.record()}
          notice={
            <>
              {notice?.kind === 'problem' && <Callout kind="problem">{notice.message}</Callout>}
              {notice?.kind === 'claim_failed' && <Callout kind="warning">{RESPONSE_TEXT.claimFailed}</Callout>}
            </>
          }
          heading={false}
        />
      </>
    );
  }

  return (
    <Drawer title={title} eyebrow={eyebrow} onClose={onClose} footer={showCancel ? cancelButton : undefined}>
      <div className="ws-respdrawer">{body}</div>
    </Drawer>
  );
}
