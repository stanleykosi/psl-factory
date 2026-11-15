'use client';

// The follow-up the agent drafted on an unknown outcome (SCR-16 unknown board). It shows the agent, its checks, the
// recipient exactly as returned and the draft; Send and Edit show only when the API allows them and the draft is
// still a draft. Edit saves nothing: the edited text goes with the send. The states the boards do not draw
// (sending, sent, effect_uncertain, a changed draft) use the F-09 callouts (Conflicts 14).
import { useEffect, useRef, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { AgentChecklist, Button, Callout, formatDate, formatTime, Panel, TextArea } from '@/components';
import type { ResponseWorkItem } from '@/features/response';
import { AGENT_LABELS } from '@/features/response/labels';

import type { Followup } from './contract';
import { useFollowup } from './useFollowup';

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

function Checks({ followup, showNote }: { followup: Followup; showNote: boolean }) {
  const checks = followup.checks ?? [];
  const done = checks.length > 0 && checks.every((c) => c.status === 'done');
  if (!followup.agent) return null;
  return (
    <AgentChecklist
      agent={followup.agent}
      task="Follow-up email"
      status={done ? 'done' : 'working'}
      steps={checks.map((c) => ({ text: c.text, status: c.status, source: c.source }))}
      foot={showNote ? (followup.note ?? 'It goes only if you send it.') : undefined}
      label={`${AGENT_LABELS[followup.agent].name}, ${AGENT_LABELS[followup.agent].role}`}
    />
  );
}

export function FollowupCard({ item, followup, reload }: { item: ResponseWorkItem; followup: Followup; reload: () => Promise<ResponseWorkItem | ApiError> }) {
  const flow = useFollowup(item, followup, reload);
  const agent = followup.agent ? AGENT_LABELS[followup.agent] : undefined;
  const status = followup.status === 'drafted' && flow.replied ? flow.replied : followup.status;
  const unconfirmed = flow.notice?.kind === 'unconfirmed';
  const open = status === 'drafted' && !unconfirmed;
  const canSend = open && followup.can_send === true && !flow.refused;
  const canEdit = open && followup.can_edit === true && !flow.refused;
  const statusLine = useRef<HTMLParagraphElement>(null);
  // After Send the button is gone; keyboard focus moves to the status line so the person keeps their place.
  useEffect(() => {
    if (flow.replied && (status === 'sending' || status === 'sent')) statusLine.current?.focus();
  }, [flow.replied, status]);

  return (
    <Panel head={agent ? `Follow-up email · drafted by ${agent.name}` : 'Follow-up email'} className="rfp-followup">
      <Checks followup={followup} showNote={status === 'drafted' && (canSend || canEdit)} />
      <p className="rfp-followup__to">
        To <span className="rfp-followup__addr">{followup.to}</span> · draft v{followup.version}
      </p>
      {flow.editing && canEdit ? (
        <TextArea label="Follow-up text" value={flow.text} onChange={(e) => flow.setText(e.target.value)} className="rfp-followup__edit" fieldClassName="resp-field" />
      ) : (
        <div className="rfp-followup__body">{followup.body}</div>
      )}
      {flow.notice?.kind === 'stale' && (
        <>
          <Warning>The draft changed. Check it before you send.</Warning>
          {flow.editing && (
            <div className="rfp-followup__current">
              <span className="psl-label">Current draft (v{followup.version})</span>
              <div className="rfp-followup__body">{followup.body}</div>
            </div>
          )}
        </>
      )}
      {flow.notice?.kind === 'problem' && <Callout kind="problem">{flow.notice.message}</Callout>}
      {flow.notice?.kind === 'uncertain' && status === 'drafted' && (
        <Warning>We couldn&rsquo;t confirm the follow-up was sent. We&rsquo;ve reloaded it; nothing was sent again.</Warning>
      )}
      {unconfirmed && (
        <Warning
          action={
            <Button kind="secondary" size="sm" busy={flow.notice?.kind === 'unconfirmed' && flow.notice.checking} busyLabel="Checking…" onClick={() => void flow.check()}>
              Try again
            </Button>
          }
        >
          We couldn&rsquo;t confirm whether the follow-up was sent, and couldn&rsquo;t reload to check. Sending stays off. Try again reloads the item; it
          doesn&rsquo;t send anything.
        </Warning>
      )}
      {/* one element for both, so focus stays on it when Sending… becomes Sent */}
      {(status === 'sending' || status === 'sent') && (
        <p ref={statusLine} tabIndex={-1} className="rfp-followup__status" role="status">
          {status === 'sending' ? 'Sending…' : followup.sent_at ? `Sent ${formatDate(followup.sent_at)} ${formatTime(followup.sent_at)}` : 'Sent'}
        </p>
      )}
      {status === 'effect_uncertain' && (
        <Warning
          action={
            <Button kind="secondary" size="sm" onClick={() => void flow.check()}>
              Check again
            </Button>
          }
        >
          We couldn&rsquo;t confirm the follow-up was sent. It won&rsquo;t be sent again until it has been checked.
        </Warning>
      )}
      {flow.editing && canEdit && flow.blank && (
        <p className="psl-hint" role="status">
          The box is empty. Write the follow-up, or use the draft.
        </p>
      )}
      {open && !(followup.can_send === true || followup.can_edit === true) && !flow.refused && (
        <p className="psl-hint">You can’t send this follow-up. Only people PSL allows to send follow-ups can.</p>
      )}
      {(canSend || canEdit) && (
        <div className="rfp-followup__actions">
          {canSend && (
            <Button size="lg" disabled={flow.blank} busy={flow.busy} busyLabel="Sending…" onClick={() => void flow.send()}>
              Send follow-up
            </Button>
          )}
          {canEdit && (
            <Button kind="secondary" size="lg" disabled={flow.busy} onClick={flow.editing ? flow.useDraft : flow.edit}>
              {flow.editing ? 'Use the draft' : 'Edit'}
            </Button>
          )}
        </div>
      )}
    </Panel>
  );
}
