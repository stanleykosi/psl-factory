'use client';

// The work at one station, for the 3D floor's readout strip (D-162). PROPOSAL G-OVERVIEW-STATION, not in v7: GET
// /api/v1/overview/stations/items. Reads are cached per station for as long as the floor is open; a station whose count
// or needs-a-person mark changed is read again. A failed read is never kept.
import { useCallback, useEffect, useReducer, useState } from 'react';

import { api, call } from '@/api/client';
import { formatAge } from '@/features/my-work/model';

export type StationItem = {
  work_id: string;
  title: string;
  project_title?: string;
  client?: string;
  reference: string;
  state: string;
  waiting_since?: string;
  needs_person: boolean;
  held_by: { kind: 'role' | 'agent'; name: string };
};
export type StationRead = { items: StationItem[]; total: number; needs_person_count?: number; next_cursor?: string; as_of: string };
type Cached = StationRead & { expanded: boolean };

const PATH = '/api/v1/overview/stations/items';
/** Rows read first: the strip shows five. "Show all" reads the rest, a page of 50 at a time, up to this many in all. */
export const FIRST_ROWS = 5;
const PAGE = 50;
const MOST = 200;

type Result = { data: StationRead; response: Response } | { data?: never; error: unknown; response: Response };
type UntypedGet = { GET: (path: string, init: { params: { query: Record<string, string | number> } }) => Promise<Result> };

const read = (line: string, station: string, limit: number, cursor?: string) =>
  call((api as unknown as UntypedGet).GET(PATH, { params: { query: { line, station, limit, ...(cursor ? { cursor } : {}) } } }));

export type StationTarget = { line: string; station: string; count: number; needsPerson: boolean };
const keyOf = (t: StationTarget) => [t.line, t.station, t.count, t.needsPerson].join('\u0000');

export type StationState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; read: StationRead; expanded: boolean; busy: boolean };

/** The read of the station shown, with Try again and Show all. Null while no station is shown. */
export function useStationWork(target: StationTarget | null) {
  const [cache] = useState(() => new Map<string, Cached>());
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = target ? keyOf(target) : null;
  const line = target?.line;
  const station = target?.station;

  useEffect(() => {
    if (!key || line === undefined || station === undefined || cache.has(key)) return;
    let live = true;
    read(line, station, FIRST_ROWS).then(
      (page) => {
        cache.set(key, { ...page, expanded: false });
        bump();
      },
      () => live && setFailed(key),
    );
    return () => {
      live = false;
    };
  }, [key, line, station, attempt, cache]);

  const showAll = useCallback(async () => {
    const first = key ? cache.get(key) : undefined;
    if (!key || !first || line === undefined || station === undefined) return;
    setBusy(key);
    setFailed(null);
    try {
      const items = [...first.items];
      let cursor = first.next_cursor;
      while (cursor && items.length < MOST) {
        const page = await read(line, station, PAGE, cursor);
        items.push(...page.items);
        cursor = page.next_cursor;
      }
      cache.set(key, { ...first, items, next_cursor: cursor, expanded: true });
      bump();
    } catch {
      setFailed(key);
    } finally {
      setBusy(null);
    }
  }, [key, line, station, cache]);

  const retry = useCallback(() => {
    if (key && cache.has(key)) return void showAll();
    setFailed(null);
    setAttempt((n) => n + 1);
  }, [key, cache, showAll]);

  const got = key ? cache.get(key) : undefined;
  const state: StationState | null = !key ? null : failed === key ? { status: 'error' } : got ? { status: 'ready', read: got, expanded: got.expanded, busy: busy === key } : { status: 'loading' };
  return { state, retry, showAll };
}

/** The link text of a row: the project, else the client, else the work's own title. */
export const rowTitle = (item: StationItem) => item.project_title ?? item.client ?? item.title;

/** The mono words at the right of a row, and whether they ask for a person. */
export function rowMeta(item: StationItem, now = Date.now()): { text: string; person: boolean } {
  if (item.needs_person) return { text: 'needs a person', person: true };
  if (item.held_by.kind === 'agent') return { text: `${item.held_by.name} working`, person: false };
  const since = item.waiting_since ? Date.parse(item.waiting_since) : NaN;
  return { text: Number.isNaN(since) ? item.reference : `${item.reference} · waiting ${formatAge(Math.max(0, (now - since) / 1000))}`, person: false };
}

/** "3 here · 1 needs a person" (the second part only when someone is needed). */
export function stationCounts(total: number, needs: number | undefined): string {
  const here = `${total} here`;
  return needs ? `${here} · ${needs} ${needs === 1 ? 'needs' : 'need'} a person` : here;
}
