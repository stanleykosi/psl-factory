// MiniStationBar (design/system/project/components/MiniStationBar, CMP-03): one small segment per station for list
// rows and phone headers, always with its words beside it ("4 of 7 · Finance review"); the bar alone is never the
// signal, so it is hidden from screen readers and the words carry it.
import type { StationStatus } from './StationTrack';

const SEGMENT: Record<StationStatus, string> = { done: 'd', person: 'p', agent: 'a', waiting: 'w', stopped: 's', verified: 'v', todo: 't' };

export function MiniStationBar({ stations, text, className }: { stations: StationStatus[]; /** Required: the words. */ text: string; className?: string }) {
  return (
    <span className={className ? `psl-mini ${className}` : 'psl-mini'}>
      <span className="psl-mini__bar" aria-hidden="true">
        {stations.map((s, i) => (
          <i key={i} className={SEGMENT[s]} />
        ))}
      </span>
      <span className="psl-mini__text">{text}</span>
    </span>
  );
}
