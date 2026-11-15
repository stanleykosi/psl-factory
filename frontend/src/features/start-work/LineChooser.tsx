'use client';

// SCR-04 "Choose a line": the lines E-LINES returned as bordered cards, grouped by `group` in the order returned
// (named groups for assistive technology; the board draws no visible group headings),
// with a search on title and subtitle. Only returned lines are offered; nothing is added from /me or from roles.
// On the phone (SCR-04-mobile-lines) the sheet shows the count in its head and the titles only, with no search.
import Link from 'next/link';
import { useId, useMemo, useState } from 'react';

import { AgentAvatar, Button, Callout, Loading, RadioGroup, SearchField, Skeleton, VisuallyHidden } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { DrawerFrame, useWide } from './DrawerFrame';
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

export function LineChooser({ state, onRetry, onNext, onClose, pathname }: Props) {
  const wide = useWide();
  const [q, setQ] = useState('');
  const [chosen, setChosen] = useState<string | null>(null);
  const countId = useId();
  const items = useMemo(() => (state.status === 'ready' ? state.data.items : []), [state]);
  const groups = useMemo(() => {
    const needle = wide ? q.trim().toLowerCase() : '';
    const shown = items.filter((line) => `${line.title}\n${line.subtitle ?? ''}`.toLowerCase().includes(needle));
    const byGroup = new Map<string, Line[]>();
    for (const line of shown) byGroup.set(line.group, [...(byGroup.get(line.group) ?? []), line]);
    return [...byGroup];
  }, [items, q, wide]);
  const selected = items.find((line) => line.key === chosen);

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
              LINES YOU CAN START · {items.length}
            </span>
          </>
        )}
        {groups.length === 0 ? (
          <p className="sw-plain">{`No line matches "${q.trim()}".`}</p>
        ) : (
          <div role="radiogroup" aria-labelledby={countId} className="sw-lines">
            {groups.map(([group, lines]) => (
              <RadioGroup
                key={group}
                className="sw-group"
                legend={<VisuallyHidden>{group}</VisuallyHidden>}
                name="start-line"
                cards
                value={chosen ?? undefined}
                onChange={setChosen}
                options={lines.map((line) => ({ value: line.key, label: line.title, detail: wide ? line.subtitle : undefined }))}
              />
            ))}
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
          <span id={countId}>Lines you can start · {items.length}</span>
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
