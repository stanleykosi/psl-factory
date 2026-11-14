'use client';

// SCR-04 line drawer: the line's intake in the order returned, "What happens next" from `next`, and one start
// button. Errors come only from the server: a 422 names fields inline and lists the rest at the top; a 409, 403 or
// 404 keeps what was typed; an uncertain result locks the form until "Check again" (see useStartWork).
import Link from 'next/link';
import { useEffect, useRef } from 'react';

import { SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

import { DrawerFrame } from './DrawerFrame';
import { caseOptionUnusable, parentValue, startableHere } from './intake';
import { IntakeField } from './IntakeField';
import { AGENT_NAMES, startLabel } from './labels';
import type { Line } from './types';
import { useStartForm, type Notice } from './useStartWork';

type Props = {
  line: Line;
  /** Opened from the chooser: shows "change line" and Back returns to the chooser. */
  fromChooser: boolean;
  onBack: () => void;
  onClose: () => void;
  onStarted: (workId: string) => void;
  pathname: string;
};

export const CASE_UNUSABLE = 'This project can’t be started on from here.';

function InfoIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="9" cy="9" r="7" />
      <path d="M9 8v5" />
      <rect x="8.1" y="4.6" width="1.8" height="1.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

function NoticeCallout({ notice, agent, calloutRef }: { notice: Notice; agent: string | undefined; calloutRef: React.Ref<HTMLDivElement> }) {
  switch (notice.kind) {
    case 'invalid':
      return (
        <div ref={calloutRef} tabIndex={-1} className="psl-callout psl-callout--problem" role="alert">
          <WarningIcon />
          <span>
            {notice.count} things to fix before {agent ? `${agent} can start` : 'this can start'}.
            {notice.unmatched.length > 0 && (
              <ul className="sw-list">
                {notice.unmatched.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            )}
          </span>
        </div>
      );
    case 'stale':
      return (
        <div className="psl-callout psl-callout--warning" role="alert">
          <WarningIcon />
          <span>
            {notice.fixed ? 'This record' : 'This project'} changed since you opened the form. We&rsquo;ve loaded the latest
            version; check your entries and press start again.
          </span>
        </div>
      );
    case 'problem':
      return (
        <div className="psl-callout psl-callout--problem" role="alert">
          <WarningIcon />
          <span>
            {notice.lead && <strong>{notice.lead} </strong>}
            {notice.message}
          </span>
        </div>
      );
    case 'uncertain':
      return (
        <div className="psl-callout psl-callout--warning" role="alert">
          <WarningIcon />
          <span>
            We couldn&rsquo;t confirm the start. Check again: if it already started you&rsquo;ll go straight to it, and nothing
            starts twice.
          </span>
        </div>
      );
    case 'gone':
      return (
        <div className="psl-callout psl-callout--problem" role="alert">
          <WarningIcon />
          <span>You can no longer start this line.</span>
        </div>
      );
  }
}

function WhatHappensNext({ next }: { next: NonNullable<Line['next']> }) {
  const agent = next.agent ? AGENT_NAMES[next.agent] : undefined;
  return (
    <div className="sw-next">
      <span className="psl-drawer__eyebrow">WHAT HAPPENS NEXT</span>
      {next.station_count !== undefined && <strong>{next.station_count} stations.</strong>}
      {next.agent && agent && (
        <span className="sw-agent">
          <span className={`psl-avatar psl-avatar--20 psl-avatar--${next.agent}`} aria-hidden="true">
            {agent.charAt(0)}
          </span>
          {agent}
        </span>
      )}
      {next.summary && <span>{next.summary}</span>}
      {next.decided_by && next.decided_by.length > 0 && <span>Decided by {next.decided_by.join(' or ')}.</span>}
      {next.journey_url && (
        <Link href={next.journey_url} className="sw-journey">
          See the full journey
        </Link>
      )}
    </div>
  );
}

export function LineForm({ line, fromChooser, onBack, onClose, onStarted, pathname }: Props) {
  const form = useStartForm(line, onStarted);
  const calloutRef = useRef<HTMLDivElement>(null);
  const here = startableHere(line);
  const agent = line.next?.agent ? AGENT_NAMES[line.next.agent] : undefined;
  const { notice, noticeSeq } = form;

  useEffect(() => {
    if (notice?.kind === 'invalid') calloutRef.current?.focus();
  }, [notice, noticeSeq]);

  const readOnly = form.uncertain || form.busy;
  const unusable = caseOptionUnusable(line, form.values);
  const labels = Object.fromEntries(form.fields.map((f) => [f.name, f.label]));
  const eyebrow = notice?.kind === 'invalid' ? `${notice.count} things to fix` : 'START WORK';
  const subline = fromChooser ? (
    <>
      Line chosen from the Start work menu ·{' '}
      <button type="button" className="psl-btn psl-btn--text psl-btn--sm sw-change" onClick={onBack}>
        change line
      </button>
    </>
  ) : undefined;

  const back = (
    <button type="button" className="psl-btn psl-btn--secondary" onClick={fromChooser ? onBack : onClose}>
      {fromChooser ? 'Back' : 'Cancel'}
    </button>
  );

  if (form.signedOut) {
    return (
      <DrawerFrame eyebrow="START WORK" title={line.title} subline={subline} onClose={onClose} focusKey="signed-out" footer={back}>
        <SignedOutState pathname={pathname} />
      </DrawerFrame>
    );
  }

  if (!here) {
    return (
      <DrawerFrame eyebrow="START WORK" title={line.title} subline={subline} onClose={onClose} focusKey={`cant-${line.key}`} footer={back}>
        <div className="psl-callout psl-callout--info">
          <InfoIcon />
          <span>
            You can&rsquo;t start this line from here yet. <Link href="/assistant" onClick={onClose}>Describe it to Tola</Link> and
            she&rsquo;ll help you start it.
          </span>
        </div>
      </DrawerFrame>
    );
  }

  const canPress = !form.busy && notice?.kind !== 'gone' && (form.uncertain || form.caseRef !== null);
  const footer = (
    <>
      {back}
      {form.uncertain && <span className="psl-hint sw-foothint">If it started, it will appear in My work.</span>}
      {notice?.kind !== 'gone' && (
        <button
          type="button"
          className={`psl-btn sw-primary${form.busy ? ' is-busy' : ''}`}
          disabled={!canPress}
          aria-busy={form.busy || undefined}
          onClick={() => void form.submit()}
        >
          {form.busy ? (
            <>
              <span className="psl-busy" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              Starting…
            </>
          ) : form.uncertain ? (
            'Check again'
          ) : (
            startLabel(line.key)
          )}
        </button>
      )}
    </>
  );

  return (
    <DrawerFrame eyebrow={eyebrow} title={line.title} subline={subline} onClose={onClose} focusKey={`line-${line.key}`} footer={footer}>
      {notice && <NoticeCallout notice={notice} agent={agent} calloutRef={calloutRef} />}
      {form.fields.map((field) => (
        <IntakeField
          key={field.name}
          lineKey={line.key}
          field={field}
          value={form.values[field.name]}
          onChange={(value) => form.setValue(field.name, value)}
          parent={parentValue(field, form.values)}
          parentLabel={field.depends_on ? labels[field.depends_on] : undefined}
          readOnly={readOnly}
          error={form.fieldErrors[field.name]}
          note={field.name === line.case_field && unusable ? CASE_UNUSABLE : form.fieldNotes[field.name]}
        />
      ))}
      {line.next && <WhatHappensNext next={line.next} />}
    </DrawerFrame>
  );
}
