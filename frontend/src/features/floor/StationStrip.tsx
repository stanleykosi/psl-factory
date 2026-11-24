'use client';

import { IconButton, Link } from '@/components';
import type { Station } from '@/features/overview/model';
import { workLink } from '@/features/overview/model';

import './floor.css';

type Props = {
  /** The line's title, and its key for the link into its queue. */
  title: string;
  lineKey: string;
  station: Station;
  pinned: boolean;
  onUnpin: () => void;
  /** The flat view says Open and Close; the 3D floor says Pinned and Unpin. */
  pinLabel?: string;
  closeLabel?: string;
};

/** The strip under the 3D floor, and under a line in the flat view (D-165): the station's count and a way into the line's queue (D-182 Q6). */
export function StationStrip({ title, lineKey, station, pinned, onUnpin, pinLabel = 'Pinned', closeLabel = 'Unpin station' }: Props) {
  const n = station.count;
  return (
    <section className="floor__strip" aria-label={`${title} · ${station.name}`}>
      <div className="floor__head">
        <p className="floor__headline" aria-live="polite">
          <strong>
            {title} · {station.name}
          </strong>
          <span>
            {n} {n === 1 ? 'item' : 'items'}
            {station.needs_person > 0 && `, ${station.needs_person} ${station.needs_person === 1 ? 'needs' : 'need'} a person`}
          </span>
        </p>
        {pinned && (
          <>
            <span className="floor__pin">{pinLabel}</span>
            <IconButton icon="close" label={closeLabel} bare onClick={onUnpin} />
          </>
        )}
      </div>
      <Link href={workLink(lineKey)} prefetch={false}>
        Open work
      </Link>
    </section>
  );
}
