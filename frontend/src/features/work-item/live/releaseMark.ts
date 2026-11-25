'use client';

// F-90: what the page remembers about an invoice release it sent, per work item and revision. A release moves money and the
// request has no key, so the page must not offer it again while the server may already have acted on the first one. The mark is
// written before the request and kept in the browser (LC-Q22), so a reload does not clear it. It holds the release only while
// the item still lists `release_invoice` at the revision it was sent with; a new revision, or the action gone, ends it.
import { useSyncExternalStore } from 'react';

import type { LiveWorkItem } from '@/api/types';

/** 'requested': the server accepted it (202). 'uncertain': no answer we can trust (timeout, 5xx), or the page closed mid-send. */
export type ReleaseMark = { revision: number; kind: 'requested' | 'uncertain' };

const KEY = (workId: number) => `psl.release-invoice.${workId}`;
const memory = new Map<number, string | null>();
const listeners = new Set<() => void>();

function raw(workId: number): string | null {
  if (memory.has(workId)) return memory.get(workId) ?? null;
  try {
    return window.localStorage.getItem(KEY(workId));
  } catch {
    return null;
  }
}

function parse(text: string | null): ReleaseMark | null {
  if (text === null) return null;
  try {
    const value = JSON.parse(text) as Partial<ReleaseMark>;
    if (Number.isInteger(value.revision) && (value.kind === 'requested' || value.kind === 'uncertain')) return { revision: value.revision as number, kind: value.kind };
  } catch {
    /* an unreadable mark is treated as a mark we cannot trust: see below */
  }
  return { revision: -1, kind: 'uncertain' };
}

/** The mark kept for this work item (null: none). Reads the latest write at once, so a double click sees the first press. */
export const readMark = (workId: number): ReleaseMark | null => parse(raw(workId));

export function writeMark(workId: number, mark: ReleaseMark | null): void {
  const text = mark ? JSON.stringify(mark) : null;
  memory.set(workId, text);
  try {
    if (text === null) window.localStorage.removeItem(KEY(workId));
    else window.localStorage.setItem(KEY(workId), text);
  } catch {
    /* storage is off: the page still holds the release for as long as it stays open */
  }
  listeners.forEach((listener) => listener());
}

/** The mark when it still applies to this item: the server lists the action at the revision the release was sent with. */
export function heldMark(item: Pick<LiveWorkItem, 'id' | 'revision' | 'actions'>): ReleaseMark | null {
  const mark = readMark(item.id);
  if (!mark || !item.actions.includes('release_invoice')) return null;
  // a mark we could not read (revision -1) holds the release at whatever revision the item is on
  return mark.revision === -1 || mark.revision === item.revision ? mark : null;
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  window.addEventListener('storage', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', listener);
  };
};

/** The stored text, so a change re-renders the page (the string is compared by value). */
export function useReleaseMark(workId: number): ReleaseMark | null {
  const text = useSyncExternalStore(subscribe, () => raw(workId), () => null);
  return parse(text);
}

/** Test seam: forget every mark (the stored ones too). */
export function resetReleaseMarks(): void {
  try {
    for (const workId of memory.keys()) window.localStorage.removeItem(KEY(workId));
    Object.keys(window.localStorage).filter((k) => k.startsWith('psl.release-invoice.')).forEach((k) => window.localStorage.removeItem(k));
  } catch {
    /* nothing stored */
  }
  memory.clear();
  listeners.forEach((listener) => listener());
}
