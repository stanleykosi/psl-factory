'use client';

// SCR-04 reads. `GET /lines` is read each time the drawer opens, so grants are current. Projects come from
// `GET /lines/projects` and a line's source records from `GET /projects/{case_id}/intake-sources`; the start itself is
// the drawer's own state machine (useStart.ts). `fetchOptions` and `ProofState` stay for the v7 intake pieces
// (RecordPicker, StartProof) that StepForm still draws.
import { useCallback, useEffect, useState } from 'react';

import { api, call, liveApi } from '@/api/client';
import type { paths } from '@/api/live-schema';
import { ApiError, networkError } from '@/api/errors';
import type { PageSize } from '@/components';

import type { Lines, ProjectOptions } from './types';

/** What one evidence field's uploader reports: the confirmed ids, its files, and the revision it now holds. */
export type ProofState = { ids: string[]; count: number; busy: boolean; failed: boolean; revision: number | undefined };

export const START_TIMEOUT_MS = 20000;
export const OPTIONS_LIMIT = 20;
/** The contract's longest search. */
export const SEARCH_MAX = 120;

type LineKey = paths['/api/v1/lines/projects']['get']['parameters']['query']['line'];

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

export type LinesState = { status: 'loading' } | { status: 'ready'; data: Lines } | { status: 'error'; error: ApiError };

export function fetchLines(): Promise<Lines> {
  return call(liveApi.GET('/api/v1/lines'));
}

/** `GET /lines` for one opening of the drawer; reload() is the chooser's Try again. */
export function useLines() {
  const [state, setState] = useState<LinesState>({ status: 'loading' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      setState({ status: 'ready', data: await fetchLines() });
    } catch (error) {
      setState({ status: 'error', error: asApiError(error) });
    }
  }, []);

  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, reload: load };
}

/** One page of the projects a line can start on. `q` is sent only when it is not empty (trimmed, at most 120);
 *  `page` only when asked for (the server's first page is the default). */
export function fetchProjects(line: string, q: string, page?: number): Promise<ProjectOptions> {
  const search = q.trim().slice(0, SEARCH_MAX);
  return call(
    liveApi.GET('/api/v1/lines/projects', {
      params: { query: { line: line as LineKey, q: search || undefined, page } },
    }),
  );
}

export type SourcesQuery = { field?: string; parentId?: number; before?: number };

/** One page of a line's source records for a project. Each query value is sent only when set. The answer's
 *  `case_revision` is the freshest the form has. Built for the lines after the weekly report (F-88). */
export async function fetchSources(caseId: string, line: string, query: SourcesQuery = {}) {
  const { field, parentId, before } = query;
  const data = await call(
    liveApi.GET('/api/v1/projects/{case_id}/intake-sources', {
      params: { path: { case_id: caseId }, query: { line: line as LineKey, field, parent_id: parentId, before } },
    }),
  );
  return { caseRevision: data.case_revision, fields: data.fields, items: data.items, nextBefore: data.next_before };
}

export type OptionsQuery = { parent?: string; q?: string; cursor?: string; limit?: PageSize };

/** One page of the v7 E-LINE-OPTIONS (StepForm's record fields); `q` is sent only when not empty. */
export function fetchOptions(lineKey: string, field: string, query: OptionsQuery) {
  const { parent, q, cursor, limit = OPTIONS_LIMIT } = query;
  return call(
    api.GET('/api/v1/lines/{line_key}/fields/{field}/options', {
      params: {
        path: { line_key: lineKey, field },
        query: { parent, q: q ? q : undefined, cursor, limit },
      },
    }),
  );
}
