// PROPOSAL (F-16 board data): detail the SCR-03 boards draw that E-WORK-ITEM has no field for yet (the queue
// pager, the subject line, the agent's summary, the not-yours comment box). Typed here only; read from the
// response with a safe cast and hidden when absent, so live responses (which never carry it) render as before.
// Presentation only: nothing here decides access or authority, nothing here is ever sent to an endpoint, and a
// contract field always wins where one exists.
import type { WorkItem } from '@/api/types';
import { isAppPath } from '@/features/work-item/presentation';

export type DecidePresentation = {
  /** "DECISIONS / 1 OF 3 / …" and "Next decision · 2 of 3". */
  queue?: {
    position: number;
    total: number;
    /** Navigation only: rendered when the href is an app path. */
    next?: { label: string; href: string };
  };
  /** "Lagoon Health, milestone 2": after the task title in the page title. */
  subject?: string;
  /** "Lagoon Health": the done heading reads "Invoice v2 for Lagoon Health is approved". */
  client?: string;
  /** "waiting 2h" in the phone station line. */
  waiting?: string;
  agent?: {
    /** "Finance agent". */
    role?: string;
    /** The desktop agent card's line. */
    summary?: string;
    /** The phone boards' one-line version of the summary. */
    phone_summary?: string;
    /** The steps link's name; "See <name>’s steps" when absent. */
    link_label?: string;
    /** The stale board's agent line (desktop). */
    note?: string;
    /** The stale board's agent line (phone). */
    phone_note?: string;
  };
  /** The not-yours board's comment box: drawn disabled, never sent (no endpoint exists). */
  comment?: { label: string; action: string };
};

/** The `decide_presentation` block of a work item response, if the response carries one. */
export function decidePresentationOf(item: WorkItem | null | undefined): DecidePresentation | undefined {
  const value = item && (item as WorkItem & { decide_presentation?: unknown }).decide_presentation;
  return value && typeof value === 'object' ? (value as DecidePresentation) : undefined;
}

/** "Next decision · 2 of 3" only when it links inside the app. */
export function nextDecision(view: DecidePresentation | undefined): { label: string; href: string } | undefined {
  const next = view?.queue?.next;
  return next && typeof next.href === 'string' && isAppPath(next.href) ? next : undefined;
}

/** "1 of 3", when the block carries a queue position. */
export function queueText(view: DecidePresentation | undefined): string | undefined {
  const queue = view?.queue;
  return queue && Number.isInteger(queue.position) && Number.isInteger(queue.total) ? `${queue.position} of ${queue.total}` : undefined;
}
