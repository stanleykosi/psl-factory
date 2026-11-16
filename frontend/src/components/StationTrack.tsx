'use client';

// StationTrack (design/system/project/components/StationTrack, CMP-02): every station of a work item's line in
// order, which are done and where it is held. Each station has its number, name and a one-line status; the
// current one is aria-current="step" and is scrolled into view (the track scrolls sideways on phones).
import { useEffect, useRef } from 'react';

import { cx } from './internal';

export type StationStatus = 'done' | 'person' | 'agent' | 'waiting' | 'stopped' | 'verified' | 'todo';
export type Station = { name: string; status: StationStatus; /** "Chidi drafted v2", "Needs your decision". */ text: string };

const CURRENT = new Set<StationStatus>(['person', 'agent', 'waiting', 'stopped']);

export function StationTrack({ stations, label = 'Stations in order', className }: { stations: Station[]; label?: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const current = stations.findIndex((s) => CURRENT.has(s.status));
  useEffect(() => {
    if (current < 0) return;
    ref.current?.children[current]?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [current]);
  return (
    // The track scrolls sideways on phones; it takes focus so a keyboard can scroll it.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div ref={ref} className={cx('psl-track', className)} role="list" aria-label={label} tabIndex={0}>
      {stations.map((station, i) => (
        <div key={i} role="listitem" className={`psl-station psl-station--${station.status}`} aria-current={i === current ? 'step' : undefined}>
          <b>{String(i + 1).padStart(2, '0')}</b>
          <strong>{station.name}</strong>
          <span>{station.text}</span>
        </div>
      ))}
    </div>
  );
}
