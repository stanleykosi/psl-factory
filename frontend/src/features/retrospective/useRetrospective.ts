'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { ActionCreateBody, MeetingSaveBody } from '@/api/types';

import type { ClosureChecklist, MeetingDetail, MeetingList, MeetingOptions } from './model';
import { failureOf, type Failure } from './failure';
import { meetingIdFromUrl } from './model';

export type { Failure };

export type Load<T> = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; data: T };
export type OptionsState = Load<MeetingOptions> | { status: 'forbidden' };
export type Used = { status: 'none' } | { status: 'ok'; detail: MeetingDetail } | { status: 'failed'; versionId: number };
export type Selected = { meeting: number; version: number | null };
export type Query = { dossier: number | null; meeting: number | null; version: number | null };

const asError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** Reads for one project's retrospective page, and its two writes. No polling; a write is one attempt. */
export function useRetrospective(caseId: string, query: Query) {
  const [project, setProject] = useState<Load<{ title: string; sample: boolean }>>({ status: 'loading' });
  const [list, setList] = useState<Load<MeetingList>>({ status: 'loading' });
  const [options, setOptions] = useState<OptionsState>({ status: 'loading' });
  const [selected, setSelected] = useState<Selected | null>(query.meeting ? { meeting: query.meeting, version: query.version } : null);
  const [detail, setDetail] = useState<Load<MeetingDetail>>({ status: 'loading' });
  const [checklist, setChecklist] = useState<Load<ClosureChecklist> | { status: 'none' }>({ status: query.dossier ? 'loading' : 'none' });
  const [used, setUsed] = useState<Used>({ status: 'none' });
  const [moreBusy, setMoreBusy] = useState(false);
  const [moreFailed, setMoreFailed] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveFailure, setSaveFailure] = useState<Failure | null>(null);
  const [savedNote, setSavedNote] = useState<{ at: Date; version: number } | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionFailure, setActionFailure] = useState<Failure | null>(null);
  const inFlight = useRef(false);
  const listRef = useRef<MeetingList | null>(null);
  const path = { case_id: caseId };

  const readList = useCallback(async (page?: number) => call(liveApi.GET('/api/v1/projects/{case_id}/meetings', { params: { path: { case_id: caseId }, query: { kind: 'retrospective', ...(page ? { page } : {}) } } })), [caseId]);

  const loadList = useCallback(async () => {
    const data = await readList();
    listRef.current = data;
    setList({ status: 'ready', data });
    return data;
  }, [readList]);

  const loadChecklist = useCallback(async () => {
    if (!query.dossier) return;
    try {
      const data = await call(liveApi.GET('/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist', { params: { path: { case_id: caseId, dossier_id: query.dossier } } }));
      setChecklist({ status: 'ready', data });
    } catch (error) {
      setChecklist({ status: 'error', error: asError(error) });
    }
  }, [caseId, query.dossier]);

  const loadDetail = useCallback(
    async (at: Selected) => {
      try {
        const data = await call(liveApi.GET('/api/v1/projects/{case_id}/meetings/{meeting_id}', { params: { path: { case_id: caseId, meeting_id: at.meeting }, query: at.version ? { version_id: at.version } : {} } }));
        setDetail({ status: 'ready', data });
      } catch (error) {
        setDetail({ status: 'error', error: asError(error) });
      }
    },
    [caseId],
  );

  useEffect(() => {
    let live = true;
    // The effect only starts the reads.
    /* eslint-disable react-hooks/set-state-in-effect */
    setProject({ status: 'loading' });
    setList({ status: 'loading' });
    setOptions({ status: 'loading' });
    /* eslint-enable react-hooks/set-state-in-effect */
    call(liveApi.GET('/api/v1/projects/{case_id}', { params: { path } }))
      .then((data) => live && setProject({ status: 'ready', data: { title: data.title, sample: data.sample === true } }))
      .catch((error) => live && setProject({ status: 'error', error: asError(error) }));
    loadList()
      .then((data) => {
        if (live) setSelected((now) => now ?? (data.items[0] ? { meeting: data.items[0].id, version: null } : null));
      })
      .catch((error) => live && setList({ status: 'error', error: asError(error) }));
    call(liveApi.GET('/api/v1/projects/{case_id}/meetings/options', { params: { path } }))
      .then((data) => live && setOptions({ status: 'ready', data }))
      .catch((error) => live && setOptions(error instanceof ApiError && error.kind === 'forbidden' ? { status: 'forbidden' } : { status: 'error', error: asError(error) }));
    void loadChecklist();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, loadList, loadChecklist]);

  useEffect(() => {
    if (!selected) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetail({ status: 'loading' });
    void loadDetail(selected);
  }, [selected, loadDetail]);

  // The version the closure checklist used: its meeting is the one in the checklist's link, else the list row that has that version.
  const reference = checklist.status === 'ready' ? (checklist.data.checks.find((c) => c.key === 'retrospective')?.references[0] ?? null) : null;
  const checklistUrl = checklist.status === 'ready' ? checklist.data.retrospective_url : null;
  const listRows = list.status === 'ready' ? list.data.items : null;
  useEffect(() => {
    if (checklist.status !== 'ready' || reference === null || listRows === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUsed({ status: 'none' });
      return;
    }
    const meeting = meetingIdFromUrl(checklistUrl) ?? listRows.find((row) => row.version_id === reference)?.id ?? null;
    if (meeting === null) {
      setUsed({ status: 'failed', versionId: reference });
      return;
    }
    let live = true;
    call(liveApi.GET('/api/v1/projects/{case_id}/meetings/{meeting_id}', { params: { path: { case_id: caseId, meeting_id: meeting }, query: { version_id: reference } } }))
      .then((data) => live && setUsed({ status: 'ok', detail: data }))
      .catch(() => live && setUsed({ status: 'failed', versionId: reference }));
    return () => {
      live = false;
    };
  }, [checklist, reference, checklistUrl, listRows, caseId]);

  const showMore = useCallback(async () => {
    const next = listRef.current?.next_page;
    if (!next) return;
    setMoreBusy(true);
    setMoreFailed(false);
    try {
      const page = await readList(next);
      const merged = { ...page, items: [...(listRef.current?.items ?? []), ...page.items] };
      listRef.current = merged;
      setList({ status: 'ready', data: merged });
    } catch {
      setMoreFailed(true);
    }
    setMoreBusy(false);
  }, [readList]);

  const reload = useCallback(async () => {
    const data = await loadList();
    await Promise.all([selected ? loadDetail(selected) : undefined, loadChecklist()]);
    return data;
  }, [loadList, loadDetail, loadChecklist, selected]);

  /** After a write: re-read the list, the opened version and the checklist; "saved" is drawn from this read only. */
  const confirmSaved = useCallback(
    async (meeting: number, version: number) => {
      const at: Selected = { meeting, version: null };
      await loadList();
      setSelected(at);
      await Promise.all([loadDetail(at), loadChecklist()]);
      setSavedNote({ at: new Date(), version });
    },
    [loadList, loadDetail, loadChecklist],
  );

  const save = useCallback(
    async (body: MeetingSaveBody): Promise<boolean> => {
      if (inFlight.current) return false;
      inFlight.current = true;
      setSaveBusy(true);
      setSaveFailure(null);
      setSavedNote(null);
      const before = listRef.current?.items.find((row) => row.reference === body.reference)?.version ?? 0;
      let ok = false;
      let posted = false;
      try {
        const saved = await call(liveApi.POST('/api/v1/projects/{case_id}/meetings', { params: { path, header: csrfHeader.header }, body }));
        posted = true;
        await confirmSaved(saved.id, saved.version);
        ok = true;
      } catch (error) {
        // Once the POST has answered, a failed re-read is only "not confirmed yet", never a reason to press Save again.
        const failure = posted ? failureOf(networkError()) : failureOf(asError(error));
        setSaveFailure(failure);
        if (failure.kind === 'stale') await loadList().catch(() => undefined);
        else if (failure.kind === 'unconfirmed') {
          // No automatic retry: re-read what was recorded, and keep Save off until that read has shown it.
          try {
            const data = await loadList();
            const row = data.items.find((r) => r.reference === body.reference);
            if (row && row.version > before) {
              await confirmSaved(row.id, row.version);
              setSaveFailure(null);
              ok = true;
            } else setSaveFailure({ kind: 'notsaved', message: 'It was not saved. Press Save again.', fields: {} });
          } catch {
            /* the failure stays "unconfirmed": Save stays off until Check again shows the result */
          }
        }
      }
      inFlight.current = false;
      setSaveBusy(false);
      return ok;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [caseId, confirmSaved, loadList],
  );

  /** Save stays off after "We couldn't confirm it saved" until this read has shown the result. */
  const checkAgain = useCallback(async () => {
    setSaveBusy(true);
    try {
      await loadList();
      setSaveFailure({ kind: 'notsaved', message: 'It was not saved. Press Save again.', fields: {} });
    } catch {
      /* still unconfirmed */
    }
    setSaveBusy(false);
  }, [loadList]);

  const createAction = useCallback(
    async (body: ActionCreateBody): Promise<boolean> => {
      if (inFlight.current) return false;
      inFlight.current = true;
      setActionBusy(true);
      setActionFailure(null);
      let ok = false;
      try {
        await call(liveApi.POST('/api/v1/projects/{case_id}/actions/create', { params: { path, header: csrfHeader.header }, body }));
        await loadList();
        if (selected) await loadDetail(selected);
        ok = true;
      } catch (error) {
        const failure = failureOf(asError(error));
        setActionFailure(failure.kind === 'unconfirmed' ? { ...failure, kind: 'retry', message: "We couldn't confirm it was created. The follow-up actions below show what was recorded." } : failure);
        // Re-read so the result is shown, and a retry is not met by a duplicate reference.
        if (failure.kind === 'stale' || failure.kind === 'unconfirmed') {
          await loadList().catch(() => undefined);
          if (selected) await loadDetail(selected);
        }
      }
      inFlight.current = false;
      setActionBusy(false);
      return ok;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [caseId, loadList, loadDetail, selected],
  );

  return { project, list, options, selected, setSelected, detail, checklist, used, showMore, moreBusy, moreFailed, reload, save, saveBusy, saveFailure, savedNote, checkAgain, createAction, actionBusy, actionFailure, clearActionFailure: () => setActionFailure(null) };
}
