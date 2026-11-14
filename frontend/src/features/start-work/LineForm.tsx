'use client';

// SCR-04 line drawer: the line's intake in the order returned, "What happens next" from `next`, and one start
// button. Errors come only from the server: a 422 names fields inline and draws a problem with a field this drawer
// does not render as its own box; a 409, 403 or 404 keeps what was typed; an uncertain result locks the form until
// "Check again" (see useStartWork). The head and footer follow the boards: from 720px "START WORK", the title and
// "Line chosen from the Start work menu · change line" over Back or Cancel and the start button; on the phone the
// sheet head reads "Step 2 of 2 · change line" and the footer is the start button alone.
import Link from 'next/link';
import { Fragment, useEffect, useRef, type ReactNode } from 'react';

import { SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

import { DrawerFrame, useWide } from './DrawerFrame';
import { caseOptionUnusable, parentValue, startableHere } from './intake';
import { IntakeField } from './IntakeField';
import { AGENT_NAMES, drawerTitle, footerGoesBack, journeyLabel, narrowDrawer, startLabel } from './labels';
import type { Field, FieldProblem, Line } from './types';
import { useStartForm, type Notice } from './useStartWork';

type Props = {
  line: Line;
  /** Back and "change line" go to the chooser. */
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

export function toFix(count: number): string {
  return `${count} ${count === 1 ? 'thing' : 'things'} to fix`;
}

type CalloutProps = { notice: Notice; agent: string | undefined; wide: boolean; calloutRef: React.Ref<HTMLDivElement> };

function NoticeCallout({ notice, agent, wide, calloutRef }: CalloutProps) {
  switch (notice.kind) {
    case 'invalid':
      // SCR-04-mobile-validation keeps only the count.
      return (
        <div ref={calloutRef} tabIndex={-1} className="psl-callout psl-callout--problem" role="alert">
          {wide && <WarningIcon />}
          <span>
            {wide ? `${toFix(notice.count)} before ${agent ? `${agent} can start` : 'this can start'}.` : toFix(notice.count)}
            {notice.general && (
              <>
                {' '}
                {notice.general}
              </>
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

/** A 422 problem for a field this drawer does not render (SCR-04-validation "Billing contact"), named from its key. */
function ProblemBox({ problem }: { problem: FieldProblem }) {
  const name = problem.name.replace(/_/g, ' ');
  return (
    <div className="psl-field sw-field" data-field={problem.name}>
      <span className="psl-label">{name.charAt(0).toUpperCase() + name.slice(1)}</span>
      <span className="psl-input is-error sw-display">—</span>
      <span className="psl-error">{problem.message}</span>
    </div>
  );
}

/** A same-origin link only, as its path; anything else is not linked. The URL parser drops tabs and newlines and
 *  reads a backslash as "/", so a value holding a control character or a backslash is refused before it is resolved. */
export function safePath(url: string | undefined, origin = window.location.origin): string | undefined {
  if (!url || /[\u0000-\u001f\u007f\\]/.test(url)) return undefined;
  let resolved: URL;
  try {
    resolved = new URL(url, origin);
  } catch {
    return undefined;
  }
  return resolved.origin === origin ? resolved.pathname + resolved.search + resolved.hash : undefined;
}

/** The decision in the line's words, e.g. "a Finance Lead decides", drawn in the deciding red. */
function Decides({ by }: { by: string[] }) {
  return <span className="sw-decides">a {by.join(' or ')} decides</span>;
}

/**
 * "What happens next" as one line (SCR-04-desktop): "<n> stations." then the summary, its parts joined by " · ",
 * with the decision after the first part, then the journey link. On the phone (SCR-04-mobile) one short line:
 * "Next:" the agent and its first word of work, then the decision.
 */
function WhatHappensNext({ lineKey, next, wide }: { lineKey: string; next: NonNullable<Line['next']>; wide: boolean }) {
  const agent = next.agent ? AGENT_NAMES[next.agent] : undefined;
  const parts = (next.summary ?? '').split(' · ').filter(Boolean);
  const by = next.decided_by && next.decided_by.length > 0 ? next.decided_by : undefined;
  const journey = safePath(next.journey_url);
  if (!wide) {
    const words = parts[0]?.split(' ') ?? [];
    const lead = agent && words[0] === agent ? words.slice(0, 2).join(' ') : agent;
    if (!lead && !by) return null;
    return (
      <p className="sw-next sw-plain">
        <strong>Next:</strong> {lead}
        {lead && by && ' · '}
        {by && <Decides by={by} />}
      </p>
    );
  }
  const pieces: ReactNode[] = [...parts];
  if (by) pieces.splice(Math.min(1, pieces.length), 0, <Decides key="by" by={by} />);
  return (
    <div className="sw-next">
      <span className="psl-drawer__eyebrow">WHAT HAPPENS NEXT</span>
      <span>
        {next.station_count !== undefined && <strong>{next.station_count} stations.</strong>}
        {pieces.map((piece, at) => (
          <Fragment key={at}>
            {at === 0 ? (next.station_count !== undefined ? ' ' : '') : ' · '}
            {piece}
          </Fragment>
        ))}
      </span>
      {journey && (
        <Link href={journey} className="sw-journey">
          {journeyLabel(lineKey)}
        </Link>
      )}
    </div>
  );
}

/** A field's help goes under the proof box straight after it, the proof for that answer (SCR-04-*-change). */
function movedHelp(fields: Field[], at: number): { id: string; text?: string } | undefined {
  const owner = fields[at + 1]?.type === 'evidence' ? fields[at] : fields[at]?.type === 'evidence' ? fields[at - 1] : undefined;
  if (!owner?.help || owner.type === 'evidence') return undefined;
  const id = `sw-help-${owner.name}`;
  return owner === fields[at] ? { id } : { id, text: owner.help };
}

export function LineForm({ line, onBack, onClose, onStarted, pathname }: Props) {
  const wide = useWide();
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
  const title = drawerTitle(line, !wide);
  const changeLine = (
    <button type="button" className="psl-btn psl-btn--text psl-btn--sm sw-change" onClick={onBack}>
      change line
    </button>
  );
  const subline =
    notice?.kind === 'invalid' ? (
      toFix(notice.count)
    ) : wide ? (
      <>Line chosen from the Start work menu · {changeLine}</>
    ) : (
      <>Step 2 of 2 · {changeLine}</>
    );

  const goesBack = footerGoesBack(line.key);
  const back = (
    <button type="button" className="psl-btn psl-btn--secondary sw-secondary" onClick={goesBack ? onBack : onClose}>
      {goesBack ? 'Back' : 'Cancel'}
    </button>
  );

  if (form.signedOut) {
    return (
      <DrawerFrame eyebrow="START WORK" title={title} narrow={narrowDrawer(line.key)} subline={subline} onClose={onClose} focusKey="signed-out" footer={back}>
        <SignedOutState pathname={pathname} />
      </DrawerFrame>
    );
  }

  if (!here) {
    return (
      <DrawerFrame eyebrow="START WORK" title={title} narrow={narrowDrawer(line.key)} subline={subline} onClose={onClose} focusKey={`cant-${line.key}`} footer={back}>
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

  const canPress = !form.busy && !form.awaitingChange && notice?.kind !== 'gone' && (form.uncertain || form.caseRef !== null);
  const footer = (
    <>
      {form.uncertain && <span className="psl-hint sw-foothint">If it started, it will appear in My work.</span>}
      {wide && back}
      {notice?.kind !== 'gone' && (
        <button
          type="button"
          className={`psl-btn psl-btn--start sw-primary${form.busy ? ' is-busy' : ''}`}
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
    <DrawerFrame eyebrow="START WORK" title={title} narrow={narrowDrawer(line.key)} subline={subline} onClose={onClose} focusKey={`line-${line.key}`} footer={footer}>
      {notice && <NoticeCallout notice={notice} agent={agent} wide={wide} calloutRef={calloutRef} />}
      {form.fields.map((field, at) => (
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
          movedHelp={movedHelp(form.fields, at)}
        />
      ))}
      {notice?.kind === 'invalid' && notice.unmatched.map((problem, at) => <ProblemBox key={`${problem.name}-${at}`} problem={problem} />)}
      {line.next && <WhatHappensNext lineKey={line.key} next={line.next} wide={wide} />}
    </DrawerFrame>
  );
}
