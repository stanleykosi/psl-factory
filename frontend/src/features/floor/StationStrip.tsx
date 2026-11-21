'use client';

import { Button, ErrorState, IconButton, Link, Loading } from '@/components';

import './floor.css';
import { rowMeta, rowTitle, stationCounts, type StationState } from './stationWork';

/** Rows past this many scroll inside the strip. */
export const SCROLL_AFTER = 20;

type Props = {
  line: string;
  station: string;
  /** The count the overview gives, shown until the read answers. */
  count: number;
  state: StationState;
  pinned: boolean;
  onUnpin: () => void;
  onRetry: () => void;
  onShowAll: () => void;
  /** The flat view says Open and Close; the 3D floor says Pinned and Unpin. */
  pinLabel?: string;
  closeLabel?: string;
};

/** The strip under the 3D floor, and under a line in the flat view (D-165): a station's head line and up to five rows, each a link to the work (D-162). */
export function StationStrip({ line, station, count, state, pinned, onUnpin, onRetry, onShowAll, pinLabel = 'Pinned', closeLabel = 'Unpin station' }: Props) {
  const ready = state.status === 'ready' ? state : null;
  const total = ready?.read.total ?? count;
  const needs = ready ? (ready.read.needs_person_count ?? (ready.read.items.length === total ? ready.read.items.filter((i) => i.needs_person).length : undefined)) : undefined;

  return (
    <section className="floor__strip" aria-label={`${line} · ${station}`}>
      <div className="floor__head">
        <p className="floor__headline" aria-live="polite">
          <strong>
            {line} · {station}
          </strong>
          <span>{stationCounts(total, needs)}</span>
        </p>
        {pinned && (
          <>
            <span className="floor__pin">{pinLabel}</span>
            <IconButton icon="close" label={closeLabel} bare onClick={onUnpin} />
          </>
        )}
      </div>
      {state.status === 'loading' && <Loading>Reading this station…</Loading>}
      {state.status === 'error' && (
        <ErrorState title="We couldn’t load this station’s work." retryLabel="Try again" onRetry={onRetry} />
      )}
      {ready && ready.read.items.length === 0 && <p className="floor__empty">Nothing here right now.</p>}
      {ready && ready.read.items.length > 0 && (
        <ul className={`floor__rows${ready.read.items.length > SCROLL_AFTER ? ' floor__rows--scroll' : ''}`}>
          {ready.read.items.map((item) => {
            const meta = rowMeta(item);
            return (
              <li key={item.work_id} className="floor__row">
                <Link href={`/work/${encodeURIComponent(item.work_id)}`}>{rowTitle(item)}</Link>
                <span className={`floor__meta${meta.person ? ' floor__meta--person' : ''}`}>{meta.text}</span>
              </li>
            );
          })}
        </ul>
      )}
      {ready && !ready.expanded && ready.read.total > ready.read.items.length && (
        <Button kind="secondary" size="sm" className="floor__all" busy={ready.busy} busyLabel="Loading…" onClick={onShowAll}>
          Show all {ready.read.total}
        </Button>
      )}
    </section>
  );
}
