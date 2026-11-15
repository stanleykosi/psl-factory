'use client';

// SCR-04 line drawer: the line's intake in the order returned, "What happens next" from `next`, and one start
// button. Errors come only from the server: a 422 names fields inline and draws a problem with a field this drawer
// does not render as its own box; a 409, 403 or 404 keeps what was typed; an uncertain result locks the form until
// "Check again" (see useStartWork). The head and footer follow the boards: from 720px "START WORK", the title and
// "Line chosen from the Start work menu · change line" over Back or Cancel and the start button; on the phone the
// sheet head reads "Step 2 of 2 · change line" and the footer is the start button alone.
import Link from 'next/link';
import { Fragment, type ReactNode } from 'react';

import { Button, Callout, Icon } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { DrawerFrame, useWide } from './DrawerFrame';
import { caseOptionUnusable, parentValue, startableHere } from './intake';
import { IntakeField } from './IntakeField';
import { AGENT_NAMES, drawerTitle, footerGoesBack, journeyLabel, startLabel } from './labels';
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

export function toFix(count: number): string {
  return `${count} ${count === 1 ? 'thing' : 'things'} to fix`;
}

type CalloutProps = { notice: Notice; agent: string | undefined; wide: boolean; seq: number };

function NoticeCallout({ notice, agent, wide, seq }: CalloutProps) {
  switch (notice.kind) {
    case 'invalid':
      // SCR-04-mobile-validation keeps only the count.
      return (
        <>
          <Callout key={seq} kind="problem" focusOnShow>
            {wide ? `${toFix(notice.count)} before ${agent ? `${agent} can start` : 'this can start'}.` : toFix(notice.count)}
            {notice.general && (
              <>
                {' '}
                {notice.general}
              </>
            )}
          </Callout>
        </>
      );
    case 'stale':
      return (
        <div role="alert">
          <Callout kind="warning">
            {notice.fixed ? 'This record' : 'This project'} changed since you opened the form. We&rsquo;ve loaded the latest
            version; check your entries and press start again.
          </Callout>
        </div>
      );
    case 'problem':
      return (
        <Callout kind="problem">
          {notice.lead && <strong>{notice.lead} </strong>}
          {notice.message}
        </Callout>
      );
    case 'uncertain':
      return (
        <div role="alert">
          <Callout kind="warning">
            We couldn&rsquo;t confirm the start. Check again: if it already started you&rsquo;ll go straight to it, and nothing
            starts twice.
          </Callout>
        </div>
      );
    case 'gone':
      return <Callout kind="problem">You can no longer start this line.</Callout>;
  }
}

/** A 422 problem for a field this drawer does not render (SCR-04-validation "Billing contact"), named from its key. */
function ProblemBox({ problem }: { problem: FieldProblem }) {
  const name = problem.name.replace(/_/g, ' ');
  return (
    <div className="psl-field sw-field" data-field={problem.name}>
      <span className="psl-label">{name.charAt(0).toUpperCase() + name.slice(1)}</span>
      <span className="psl-input is-error sw-display">—</span>
      <span className="psl-error">
        <Icon name="warn" />
        <span>{problem.message}</span>
      </span>
    </div>
  );
}

/** A same-origin link only, as its path; anything else is not linked. The URL parser drops tabs and newlines and
 *  reads a backslash as "/", so a value holding a control character or a backslash is refused before it is resolved.
 *  A resolved path that starts "//" (dot segments can leave one) would read as another site, so it is refused too. */
export function safePath(url: string | undefined, origin = window.location.origin): string | undefined {
  if (!url || /[\u0000-\u001f\u007f\\]/.test(url)) return undefined;
  let resolved: URL;
  try {
    resolved = new URL(url, origin);
  } catch {
    return undefined;
  }
  if (resolved.origin !== origin || resolved.pathname.startsWith('//')) return undefined;
  return resolved.pathname + resolved.search + resolved.hash;
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
  const here = startableHere(line);
  const agent = line.next?.agent ? AGENT_NAMES[line.next.agent] : undefined;
  const { notice, noticeSeq } = form;

  const readOnly = form.uncertain || form.busy;
  const unusable = caseOptionUnusable(line, form.values);
  const labels = Object.fromEntries(form.fields.map((f) => [f.name, f.label]));
  const title = drawerTitle(line, !wide);
  const changeLine = (
    <Button kind="text" size="sm" className="sw-change" onClick={onBack}>
      change line
    </Button>
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
    <Button kind="secondary" className="sw-secondary" onClick={goesBack ? onBack : onClose}>
      {goesBack ? 'Back' : 'Cancel'}
    </Button>
  );

  if (form.signedOut) {
    return (
      <DrawerFrame eyebrow="START WORK" title={title} subline={subline} onClose={onClose} footer={back} focusKey="signed-out">
        <SignedOutState pathname={pathname} />
      </DrawerFrame>
    );
  }

  if (!here) {
    return (
      <DrawerFrame eyebrow="START WORK" title={title} subline={subline} onClose={onClose} footer={back} focusKey={`cant-${line.key}`}>
        <Callout kind="info">
          You can&rsquo;t start this line from here yet. <Link href="/assistant" onClick={onClose}>Describe it to Tola</Link> and
          she&rsquo;ll help you start it.
        </Callout>
      </DrawerFrame>
    );
  }

  const canPress = !form.awaitingChange && notice?.kind !== 'gone' && (form.uncertain || form.caseRef !== null);
  const footer = (
    <>
      {form.uncertain && <span className="psl-hint sw-foothint">If it started, it will appear in My work.</span>}
      {wide && back}
      {notice?.kind !== 'gone' && (
        <Button
          kind="start"
          className="sw-primary"
          disabled={!canPress}
          busy={form.busy}
          busyLabel="Starting…"
          onClick={() => void form.submit()}
        >
          {form.uncertain ? 'Check again' : startLabel(line.key)}
        </Button>
      )}
    </>
  );

  return (
    <DrawerFrame eyebrow="START WORK" title={title} subline={subline} onClose={onClose} footer={footer} focusKey={`line-${line.key}`}>
      {notice && <NoticeCallout notice={notice} agent={agent} wide={wide} seq={noticeSeq} />}
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
