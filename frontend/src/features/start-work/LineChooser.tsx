'use client';

// SCR-04 "Choose a line": the lines E-LINES returned as bordered cards, grouped by `group` in the order returned
// (named groups for assistive technology; the board draws no visible group headings),
// with a search on title and subtitle. Only returned lines are offered; nothing is added from /me or from roles.
// On the phone (SCR-04-mobile-lines) the sheet shows the count in its head and the titles only, with no search.
import Image from 'next/image';
import Link from 'next/link';
import { useId, useMemo, useState } from 'react';

import { SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

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
      <Image className="psl-avatar psl-avatar--tola" src="/agents/tola.png" alt="" width={28} height={28} />
      <span>
        <strong>Not sure which line?</strong> Describe it to Tola
      </span>
    </Link>
  );
}

function Loading() {
  return (
    <div className="sw-loading">
      <div className="shell-skel" aria-hidden="true">
        <span className="psl-skel" style={{ width: '90%' }} />
        <span className="psl-skel" style={{ width: '70%' }} />
        <span className="psl-skel" style={{ width: '80%' }} />
      </div>
      <span className="psl-loading" role="status">
        <span className="psl-busy" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        Loading…
      </span>
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
  if (state.status === 'loading') body = <Loading />;
  else if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
    else if (error.kind === 'forbidden' || error.kind === 'not_found') {
      body = (
        <div className="psl-callout psl-callout--problem" role="alert">
          <WarningIcon />
          <span>{error.message}</span>
        </div>
      );
    } else {
      body = (
        <>
          <div className="psl-callout psl-callout--problem" role="alert">
            <WarningIcon />
            <span>We couldn&rsquo;t load your lines. Nothing was started.</span>
          </div>
          <button type="button" className="psl-btn psl-btn--secondary sw-retry" onClick={onRetry}>
            Try again
          </button>
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
            <div className="psl-search">
              <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="7.5" cy="7.5" r="5.5" />
                <path d="M11.5 11.5L16 16" />
              </svg>
              <input
                type="search"
                className="psl-input"
                aria-label="Find a line"
                placeholder="Find a line…"
                value={q}
                onChange={(event) => setQ(event.target.value)}
              />
            </div>
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
              <div role="group" aria-label={group} key={group} className="sw-group">
                {lines.map((line) => (
                  <label key={line.key} className="sw-line">
                    <input
                      type="radio"
                      name="start-line"
                      value={line.key}
                      checked={chosen === line.key}
                      onChange={() => setChosen(line.key)}
                    />
                    <strong>{line.title}</strong>
                    {wide && line.subtitle && <span className="sw-line__sub">{line.subtitle}</span>}
                  </label>
                ))}
              </div>
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
      narrow
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
            <button type="button" className="psl-btn psl-btn--secondary sw-secondary" onClick={onClose}>
              Back
            </button>
          )}
          <button type="button" className="psl-btn psl-btn--start sw-primary" disabled={!selected} onClick={() => selected && onNext(selected)}>
            Next
          </button>
        </>
      }
    >
      {body}
    </DrawerFrame>
  );
}
