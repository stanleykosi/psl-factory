'use client';

// SCR-04 data flow. E-LINES is read each time the drawer opens, so grants are current. A start is one
// E-WORK-START per press with CSRF, the case revision and an idempotency key (PMO-0-2): the key is made when the
// line's drawer opens, a double press sends one request, and an uncertain result (network, timeout or 5xx) locks
// the form and resends only on "Check again" with the same body and key. A definitive 409 or 422 means nothing was
// written: the form unlocks and the next press uses a new key. A stale 409 keeps every value and re-reads the
// revision from where it came from (PMO-0-3); nothing is ever resent automatically.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';

import {
  buildIntake,
  dependentsOf,
  newIdempotencyKey,
  parentValue,
  resolveCase,
  shownFields,
  type FieldValue,
  type Values,
} from './intake';
import type { FieldProblem, Line, LineOption, Lines, StartBody } from './types';

export const START_TIMEOUT_MS = 20000;
export const OPTIONS_LIMIT = 20;

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

export type LinesState = { status: 'loading' } | { status: 'ready'; data: Lines } | { status: 'error'; error: ApiError };

export function fetchLines(): Promise<Lines> {
  return call(api.GET('/api/v1/lines'));
}

/** E-LINES for one opening of the drawer; reload() is the chooser's Try again. */
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

export type OptionsQuery = { parent?: string; q?: string; cursor?: string };

/** One page of E-LINE-OPTIONS; `q` is sent only when not empty and the page size is always 20. */
export function fetchOptions(lineKey: string, field: string, query: OptionsQuery) {
  const { parent, q, cursor } = query;
  return call(
    api.GET('/api/v1/lines/{line_key}/fields/{field}/options', {
      params: {
        path: { line_key: lineKey, field },
        query: { parent, q: q ? q : undefined, cursor, limit: OPTIONS_LIMIT },
      },
    }),
  );
}

export type Notice =
  /** `unmatched`: 422 problems naming no rendered field, drawn as their own boxes (SCR-04-validation "Billing
   *  contact"); `general`: the message of a 422 that names no field at all. */
  | { kind: 'invalid'; count: number; unmatched: FieldProblem[]; general?: string }
  | { kind: 'stale'; fixed: boolean }
  | { kind: 'problem'; lead?: string; message: string }
  | { kind: 'uncertain' }
  | { kind: 'gone' };

export const NO_LONGER_AVAILABLE = 'That choice is no longer available. Choose again.';

/** One line's drawer: values, the case, the key and the start request. */
export function useStartForm(line: Line, onStarted: (workId: string) => void) {
  const fields = useMemo(() => shownFields(line), [line]);
  const [values, setValues] = useState<Values>({});
  // A fixed case's revision as last read from E-LINES (it changes only after a 409 re-read).
  const [fixedRevision, setFixedRevision] = useState(line.case_revision);
  const [key, setKey] = useState(newIdempotencyKey);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  // Bumped with every new notice, so the drawer can move focus to it.
  const [noticeSeq, setNoticeSeq] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [fieldNotes, setFieldNotes] = useState<Record<string, string>>({});
  // After a 422 the start button waits for a change, as SCR-04-validation draws it greyed.
  const [awaitingChange, setAwaitingChange] = useState(false);
  // One write at a time, checked synchronously so a double press cannot send two starts.
  const writing = useRef(false);
  // The exact body last sent; "Check again" resends it unchanged with the same key.
  const sent = useRef<StartBody | null>(null);

  const caseLine = useMemo(() => ({ ...line, case_revision: fixedRevision }), [line, fixedRevision]);
  const caseRef = resolveCase(caseLine, values);

  const show = useCallback((next: Notice | null) => {
    setNotice(next);
    setNoticeSeq((n) => n + 1);
  }, []);

  const setValue = useCallback(
    (name: string, value: FieldValue | undefined) => {
      const cleared = dependentsOf(fields, name);
      setAwaitingChange(false);
      setValues((current) => {
        const next = { ...current, [name]: value };
        for (const dependent of cleared) delete next[dependent];
        return next;
      });
      setFieldNotes((current) => {
        const next = { ...current };
        for (const dependent of [name, ...cleared]) delete next[dependent];
        return next;
      });
    },
    [fields],
  );

  /** PMO-0-3: keep every value and re-read the case revision from where it came from. */
  const reloadRevision = useCallback(async () => {
    if (line.case_scope === 'fixed') {
      try {
        const current = (await fetchLines()).items.find((l) => l.key === line.key);
        if (!current) return show({ kind: 'gone' });
        setFixedRevision(current.case_revision);
      } catch {
        // The stale notice still shows; the next press sends what was last read and answers again.
      }
      return show({ kind: 'stale', fixed: true });
    }
    const field = fields.find((f) => f.name === line.case_field);
    const chosen = field ? (values[field.name] as LineOption | undefined) : undefined;
    if (!field || !chosen) return show({ kind: 'stale', fixed: false });
    try {
      const page = await fetchOptions(line.key, field.name, { parent: parentValue(field, values), q: chosen.label });
      const fresh = page.items.find((option) => option.value === chosen.value);
      if (fresh) setValues((current) => ({ ...current, [field.name]: fresh }));
      else {
        setValue(field.name, undefined);
        setFieldNotes((current) => ({ ...current, [field.name]: NO_LONGER_AVAILABLE }));
      }
    } catch (error) {
      const apiError = asApiError(error);
      if (apiError.kind === 'not_found' || apiError.kind === 'forbidden') return show({ kind: 'gone' });
    }
    show({ kind: 'stale', fixed: false });
  }, [fields, line, setValue, show, values]);

  const submit = useCallback(async () => {
    if (writing.current) return;
    const body: StartBody | null =
      uncertain && sent.current
        ? sent.current
        : caseRef && { line: line.key, ...caseRef, intake: buildIntake(fields, values), idempotency_key: key };
    if (!body) return;
    writing.current = true;
    sent.current = body;
    setBusy(true);
    try {
      let response: Response;
      let data: unknown;
      let error: unknown;
      try {
        ({ response, data, error } = await api.POST('/api/v1/work', { body, signal: AbortSignal.timeout(START_TIMEOUT_MS) }));
      } catch (thrown) {
        // Thrown before sending (no CSRF token): nothing was sent. Anything else may have reached the server.
        if (thrown instanceof ApiError && thrown.kind === 'unauthenticated') return setSignedOut(true);
        setUncertain(true);
        return show({ kind: 'uncertain' });
      }
      if (response.status === 201) return onStarted((data as { work_id: string }).work_id);
      if (response.status >= 500 || response.status < 400) {
        setUncertain(true);
        return show({ kind: 'uncertain' });
      }
      // A definitive answer: unlock the form.
      setUncertain(false);
      sent.current = null;
      const apiError = errorFromResponse(response.status, error);
      if (apiError.kind === 'unauthenticated') return setSignedOut(true);
      setFieldErrors({});
      if (response.status === 422) {
        setKey(newIdempotencyKey());
        const problems = ((error as { fields?: FieldProblem[] } | undefined)?.fields ?? []).filter(
          (p) => typeof p?.name === 'string' && typeof p?.message === 'string',
        );
        const names = new Set(fields.map((f) => f.name));
        const inline = Object.fromEntries(problems.filter((p) => names.has(p.name)).map((p) => [p.name, p.message]));
        const unmatched = problems.filter((p) => !names.has(p.name));
        setFieldErrors(inline);
        setAwaitingChange(true);
        return show({ kind: 'invalid', count: problems.length || 1, unmatched, general: problems.length > 0 ? undefined : apiError.message });
      }
      if (response.status === 409) {
        setKey(newIdempotencyKey());
        if (apiError.code === 'idempotency_key_reused') return show({ kind: 'problem', message: apiError.message });
        return await reloadRevision();
      }
      const lead = response.status === 403 || response.status === 404 ? 'You can’t start this here.' : undefined;
      show({ kind: 'problem', lead, message: apiError.message });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [caseRef, fields, key, line.key, onStarted, reloadRevision, show, uncertain, values]);

  return {
    fields,
    values,
    setValue,
    caseRef,
    busy,
    uncertain,
    signedOut,
    notice,
    noticeSeq,
    fieldErrors,
    fieldNotes,
    awaitingChange,
    submit,
  };
}
