'use client';

// SCR-04 "Choose a line": the lines `GET /lines` returned as bordered cards in the order returned, with a search on title
// and description. A line with a registered form and `can_submit_via_api` is a choice; any other (except `invoice`, which
// is not shown) is an "unavailable" card with a link to its full form. Nothing is added from /me or from roles.
// On the phone (SCR-04-mobile-lines) the sheet shows the count in its head and the titles only, with no search.
import Link from 'next/link';
import { useId, useMemo, useState } from 'react';

import { AgentAvatar, Button, Callout, Loading, RadioGroup, SearchField, Skeleton, VisuallyHidden } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { DrawerFrame, useWide } from './DrawerFrame';
import { UNAVAILABLE_LINK, UNAVAILABLE_NOTE } from './labels';
import { lineFormFor } from './lines';
import type { Line } from './types';
import type { LinesState } from './useStartWork';

type Props = {
  state: LinesState;
  onRetry: () => void;
  onNext: (line: Line) => void;
  onClose: () => void;
  pathname: string;
};

function TolaLink({ onClose }: { onClose: () => void }) {
  return (
    <Link href="/assistant" className="psl-callout psl-callout--info sw-tola" onClick={onClose}>
      <AgentAvatar agent="tola" size={32} />
      <span>
        <strong>Not sure which line?</strong> Describe it to Tola
      </span>
    </Link>
  );
}

function LoadingLines() {
  return (
    <div className="sw-loading">
      <Skeleton widths={[90, 70, 80]} />
      <Loading>Loading…</Loading>
    </div>
  );
}

/** The lines this screen lists: all lines `GET /lines` gives except `invoice`, in that order. */
export const listedLines = (items: Line[]) => items.filter((line) => (line.key as string) !== 'invoice');

/** Startable: the contract lets the API start it and a form is registered for it. */
export const isStartable = (line: Line) => line.can_submit_via_api && lineFormFor(line.key) !== undefined;

function Unavailable({ line, wide }: { line: Line; wide: boolean }) {
  return (
    <div className="psl-choice sw-unavailable" data-line={line.key}>
      <span>
        <strong>{line.title}</strong>
        {wide && line.description && <small>{line.description}</small>}
        <small className="sw-unavailable__note">
          {UNAVAILABLE_NOTE} <a href={line.django_url}>{UNAVAILABLE_LINK}</a>
        </small>
      </span>
    </div>
  );
}

export function LineChooser({ state, onRetry, onNext, onClose, pathname }: Props) {
  const wide = useWide();
  const [q, setQ] = useState('');
  const [chosen, setChosen] = useState<string | null>(null);
  const countId = useId();
  const items = useMemo(() => (state.status === 'ready' ? listedLines(state.data.items) : []), [state]);
  const shown = useMemo(() => {
    const needle = wide ? q.trim().toLowerCase() : '';
    return items.filter((line) => `${line.title}\n${line.description}`.toLowerCase().includes(needle));
  }, [items, q, wide]);
  // Runs of startable lines are one radio group each; an unavailable card sits between them where it was returned.
  const runs = useMemo(() => {
    const out: ({ kind: 'choose'; lines: Line[] } | { kind: 'unavailable'; line: Line })[] = [];
    for (const line of shown) {
      const last = out[out.length - 1];
      if (!isStartable(line)) out.push({ kind: 'unavailable', line });
      else if (last?.kind === 'choose') last.lines.push(line);
      else out.push({ kind: 'choose', lines: [line] });
    }
    return out;
  }, [shown]);
  const startable = useMemo(() => items.filter(isStartable).length, [items]);
  const selected = items.find((line) => line.key === chosen && isStartable(line));

  let body;
  if (state.status === 'loading') body = <LoadingLines />;
  else if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
    else if (error.kind === 'forbidden' || error.kind === 'not_found') {
      body = (
        <Callout kind="problem">{error.message}</Callout>
      );
    } else {
      body = (
        <>
          <Callout kind="problem">We couldn&rsquo;t load your lines. Nothing was started.</Callout>
          <Button kind="secondary" className="sw-retry" onClick={onRetry}>
            Try again
          </Button>
        </>
      );
    }
  } else if (items.length === 0) {
    body = (
      <>
        <p className="sw-plain">There are no lines you can start right now.</p>
        <TolaLink onClose={onClose} />
      </>
    );
  } else {
    body = (
      <>
        {wide && (
          <>
            <SearchField label="Find a line" placeholder="Find a line…" value={q} onChange={setQ} />
            <span className="psl-drawer__eyebrow" id={countId}>
              LINES YOU CAN START · {startable}
            </span>
          </>
        )}
        {shown.length === 0 ? (
          <p className="sw-plain">{`No line matches "${q.trim()}".`}</p>
        ) : (
          <div role="group" aria-labelledby={countId} className="sw-lines">
            {runs.map((run, at) =>
              run.kind === 'unavailable' ? (
                <Unavailable key={run.line.key} line={run.line} wide={wide} />
              ) : (
                <RadioGroup
                  key={`run-${at}`}
                  className="sw-group"
                  legend={<VisuallyHidden>Lines you can start</VisuallyHidden>}
                  name="start-line"
                  cards
                  value={chosen ?? undefined}
                  onChange={setChosen}
                  options={run.lines.map((line) => ({ value: line.key, label: line.title, detail: wide ? line.description : undefined }))}
                />
              ),
            )}
          </div>
        )}
        <TolaLink onClose={onClose} />
        {wide && <p className="psl-hint sw-plain">You only see lines your roles let you start. Ask your Lead if one is missing.</p>}
      </>
    );
  }

  return (
    <DrawerFrame
      eyebrow="START WORK"
      title="Choose a line"
      subline={
        wide ? (
          'Step 1 of 2'
        ) : state.status === 'ready' && items.length > 0 ? (
          <span id={countId}>Lines you can start · {startable}</span>
        ) : undefined
      }
      onClose={onClose}
      focusKey={`chooser-${state.status}`}
      footer={
        <>
          {wide && (
            <Button kind="secondary" className="sw-secondary" onClick={onClose}>
              Back
            </Button>
          )}
          <Button kind="start" className="sw-primary" disabled={!selected} onClick={() => selected && onNext(selected)}>
            Next
          </Button>
        </>
      }
    >
      {body}
    </DrawerFrame>
  );
}
