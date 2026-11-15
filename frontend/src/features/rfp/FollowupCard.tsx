'use client';

// The follow-up the agent drafted on an unknown outcome (SCR-16 unknown board). It shows the agent, its checks, the
// recipient exactly as returned and the draft; Send and Edit show only when the API allows them and the draft is
// still a draft. Edit saves nothing: the edited text goes with the send. The states the boards do not draw
// (sending, sent, effect_uncertain, a changed draft) use the F-09 callouts (Conflicts 14).
import { useEffect, useRef, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { WarningIcon } from '@/shell/icons';
import type { ResponseWorkItem } from '@/features/response';
import { AGENT_LABELS, formatClock, formatDay } from '@/features/response/labels';

import type { Followup } from './contract';
import { useFollowup } from './useFollowup';

function Warning({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="psl-callout psl-callout--warning resp-retry" role="alert">
      <WarningIcon />
      <span>{children}</span>
      {action}
    </div>
  );
}

function Checks({ followup, showNote }: { followup: Followup; showNote: boolean }) {
  const agent = followup.agent ? AGENT_LABELS[followup.agent] : undefined;
  const checks = followup.checks ?? [];
  const done = checks.length > 0 && checks.every((c) => c.status === 'done');
  if (!agent && checks.length === 0) return null;
  return (
    <section className="psl-panel psl-panel--agent rfp-agent" aria-label={agent ? `${agent.name}, ${agent.role}` : 'Agent checks'}>
      <div className="rfp-agent__head">
        {followup.agent && (
          // eslint-disable-next-line @next/next/no-img-element -- a fixed 32px avatar from public/agents
          <img src={`/agents/${followup.agent}.png`} alt="" width={32} height={32} className="rfp-agent__img" />
        )}
        <span className="rfp-agent__name">
          <strong>Follow-up email</strong>
          {agent && (
            <span className="rfp-agent__role">
              {agent.name} · {agent.role}
              {done && ' · done'}
            </span>
          )}
        </span>
        {done && <span className="psl-tag psl-tag--agent rfp-agent__tag">DONE</span>}
      </div>
      {checks.length > 0 && (
        <ol className="psl-steps">
          {checks.map((c, i) => (
            <li key={i} className={`psl-step psl-step--${c.status}`}>
              <span className="psl-step__box" aria-hidden="true">
                {c.status === 'done' && (
                  <svg width="12" height="12" viewBox="0 0 12 12">
                    <path d="M2 6.5l2.5 2.5L10 3" fill="none" stroke="currentColor" strokeWidth="2" />
                  </svg>
                )}
              </span>
              <span className="psl-step__text">
                <span>
                  {c.text}
                  <span className="work-sr"> ({c.status === 'done' ? 'done' : c.status === 'now' ? 'in progress' : 'next'})</span>
                </span>
                {c.source && <span className="psl-step__ref">{c.source}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
      {showNote && <p className="rfp-agent__note">{followup.note ?? 'It goes only if you send it.'}</p>}
    </section>
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
    <section className="psl-panel rfp-followup" aria-labelledby="rfp-followup-head">
      <h2 id="rfp-followup-head" className="psl-panel__head">
        {agent ? `Follow-up email · drafted by ${agent.name}` : 'Follow-up email'}
      </h2>
      <div className="psl-panel__body">
        <Checks followup={followup} showNote={status === 'drafted' && (canSend || canEdit)} />
        <p className="rfp-followup__to">
          To <span className="rfp-followup__addr">{followup.to}</span> · draft v{followup.version}
        </p>
        {flow.editing && canEdit ? (
          <label className="resp-field">
            <span className="resp-label">Follow-up text</span>
            <textarea className="psl-input psl-input--area rfp-followup__edit" value={flow.text} onChange={(e) => flow.setText(e.target.value)} />
          </label>
        ) : (
          <div className="rfp-followup__body">{followup.body}</div>
        )}
        {flow.notice?.kind === 'stale' && (
          <>
            <Warning>The draft changed. Check it before you send.</Warning>
            {flow.editing && (
              <div className="rfp-followup__current">
                <span className="resp-label">Current draft (v{followup.version})</span>
                <div className="rfp-followup__body">{followup.body}</div>
              </div>
            )}
          </>
        )}
        {flow.notice?.kind === 'problem' && (
          <div className="psl-callout psl-callout--problem" role="alert">
            <WarningIcon />
            <span>{flow.notice.message}</span>
          </div>
        )}
        {flow.notice?.kind === 'uncertain' && status === 'drafted' && (
          <Warning>We couldn&rsquo;t confirm the follow-up was sent. We&rsquo;ve reloaded it; nothing was sent again.</Warning>
        )}
        {unconfirmed && (
          <Warning
            action={
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" disabled={flow.notice?.kind === 'unconfirmed' && flow.notice.checking} onClick={() => void flow.check()}>
                Try again
              </button>
            }
          >
            We couldn&rsquo;t confirm whether the follow-up was sent, and couldn&rsquo;t reload to check. Sending stays off. Try again reloads the item; it
            doesn&rsquo;t send anything.
          </Warning>
        )}
        {/* one element for both, so focus stays on it when Sending… becomes Sent */}
        {(status === 'sending' || status === 'sent') && (
          <p ref={statusLine} tabIndex={-1} className="rfp-followup__status" role="status">
            {status === 'sending' ? 'Sending…' : followup.sent_at ? `Sent ${formatDay(followup.sent_at)} ${formatClock(followup.sent_at)}` : 'Sent'}
          </p>
        )}
        {status === 'effect_uncertain' && (
          <Warning
            action={
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => void flow.check()}>
                Check again
              </button>
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
              <button type="button" className="psl-btn psl-btn--lg" disabled={flow.busy || flow.blank} onClick={() => void flow.send()}>
                {flow.busy ? 'Sending…' : 'Send follow-up'}
              </button>
            )}
            {canEdit && (
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg" disabled={flow.busy} onClick={flow.editing ? flow.useDraft : flow.edit}>
                {flow.editing ? 'Use the draft' : 'Edit'}
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
