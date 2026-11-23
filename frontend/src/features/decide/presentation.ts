// The decision pager ("DECISIONS / 2 OF 5") and the "next decision" link come from the person's live decision list
// only (GET /work?queue=decisions). Drawn only when that read succeeded and holds this work; presentation only.
import type { QueueEntry } from './useDecision';

export type QueuePlace = { position: number; total: number };

/** This work's place in the decision list, or undefined when the list failed or does not hold it. */
export function queuePlace(queue: QueueEntry[] | null, workId: number | null): QueuePlace | undefined {
  if (!queue || workId === null) return undefined;
  const index = queue.findIndex((entry) => entry.id === workId);
  return index < 0 ? undefined : { position: index + 1, total: queue.length };
}

/** "2 of 5", when the list holds the work. */
export const queueText = (place: QueuePlace | undefined) => (place ? `${place.position} of ${place.total}` : undefined);
