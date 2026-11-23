'use client';

// SCR-04 data flow. E-LINES is read each time the drawer opens, so grants are current. A start is one
// E-WORK-START per press with CSRF, the case revision and an idempotency key (PMO-0-2): the key is made when the
// line's drawer opens, a double press sends one request, and an uncertain result (network, timeout or 5xx) locks
// the form and resends only on "Check again" with the same body and key. A definitive 409 or 422 means nothing was
// written: the form unlocks and the next press uses a new key. A stale 409 keeps every value and re-reads the
// revision from where it came from (PMO-0-3); nothing is ever resent automatically. Proof (FE-M2A-PROOF) is uploaded
// to the same case first, each upload carrying the revision the last one returned: the start sends the confirmed
// evidence_ids and that revision, uses the key made when the drawer opened, and waits while any file is uploading or
// failed. A new project means a new case, so proof added to the old one is dropped from the start.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import type { PageSize } from '@/components';

import {
  buildIntake,
  dependentsOf,
  emptyRequired,
  fillable,
  isNew,
  newIdempotencyKey,
  parentValue,
  resolveCase,
  shownFields,
  type FieldValue,
  type Values,
} from './intake';
import { CANT_ADD } from './labels';
import { isShown, shownNow } from './showWhen';
import type { Field, FieldProblem, Line, LineOption, Lines, StartBody } from './types';

/** What one evidence field's uploader reports: the confirmed ids, its files, and the revision it now holds. */
export type ProofState = { ids: string[]; count: number; busy: boolean; failed: boolean; revision: number | undefined };

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

export type OptionsQuery = { parent?: string; q?: string; cursor?: string; limit?: PageSize };

/** One page of E-LINE-OPTIONS; `q` is sent only when not empty and the page size is 20 unless the picker's paging footer asks for another. */
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

export type Notice =
  /** `unmatched`: 422 problems naming no rendered field, drawn as their own boxes (SCR-04-validation "Billing
   *  contact"); `general`: the message of a 422 that names no field at all. */
  | { kind: 'invalid'; count: number; unmatched: FieldProblem[]; general?: string }
  | { kind: 'stale'; fixed: boolean }
  | { kind: 'problem'; lead?: string; message: string }
  | { kind: 'uncertain' }
  | { kind: 'gone' };

const requiredMessage = (field: Field) => `${field.label} is required.`;

/** The option a choice field's `value` names (the line's default, from data); none is picked when it names none. */
function defaultChoices(fields: Field[]): Values {
  const chosen: Values = {};
  for (const field of fields) {
    if (field.type === 'choice' && field.value && field.options?.some((o) => o.value === field.value)) chosen[field.name] = field.value;
  }
  return chosen;
}

export const NO_LONGER_AVAILABLE = 'That choice is no longer available. Choose again.';

/** How many pages of options are searched for a prefilled value before it counts as not served. */
const PREFILL_PAGES = 5;

/** A prefilled value for one field, or undefined when it is not one this release prefills. */
function plainValue(field: Field, raw: unknown): FieldValue | undefined {
  switch (field.type) {
    case 'text':
    case 'long_text':
    case 'date':
    case 'period':
    case 'datetime':
    case 'choice':
      return typeof raw === 'string' ? raw : undefined;
    case 'integer':
      return typeof raw === 'number' && Number.isSafeInteger(raw) ? String(raw) : undefined;
    case 'date_range': {
      const range = raw as { from?: unknown; to?: unknown } | null;
      return range && typeof range === 'object' && (typeof range.from === 'string' || typeof range.to === 'string')
        ? { from: typeof range.from === 'string' ? range.from : '', to: typeof range.to === 'string' ? range.to : '' }
        : undefined;
    }
    default:
      return undefined;
  }
}

/** The options of a record field that match the wanted values, searched across a few pages; none is invented. */
async function findOptions(lineKey: string, field: string, parent: string | undefined, wanted: string[]): Promise<LineOption[]> {
  const found = new Map<string, LineOption>();
  let cursor: string | undefined;
  for (let page = 0; page < PREFILL_PAGES; page += 1) {
    const result = await fetchOptions(lineKey, field, { parent, cursor });
    for (const option of result.items) if (wanted.includes(option.value) && !option.disabled_reason) found.set(option.value, option);
    cursor = result.next_cursor;
    if (found.size === wanted.length || !cursor) break;
  }
  return wanted.flatMap((value) => found.get(value) ?? []);
}

/**
 * One line's drawer: values, the case, the key and the start request. `initialIntake` (the assistant's draft) fills the
 * form once as the person would: text is copied, record values are looked up in the options this person is served
 * (a value not served stays empty with a note), and the case and revision come from the chosen option as always. The
 * form is read-only meanwhile (`prefilling`). It is a starting point: nothing is sent until the person presses start.
 */
export function useStartForm(line: Line, onStarted: (workId: string) => void, initialIntake?: Record<string, unknown>, onConflict?: () => void) {
  const fields = useMemo(() => shownFields(line), [line]);
  // A choice field whose `value` names one of its options starts with it selected (D-130: the options, and so the default, are data).
  const [values, setValues] = useState<Values>(() => defaultChoices(fields));
  // F-49: a field whose `show_when` is not met is not drawn and never sent.
  const drawn = useMemo(() => shownNow(fields, values), [fields, values]);
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
  // Bumped when a press finds required fields empty; `focusName` is the first of them (the drawer moves focus to it).
  const [focus, setFocus] = useState<{ seq: number; name: string }>({ seq: 0, name: '' });
  const [fieldNotes, setFieldNotes] = useState<Record<string, string>>({});
  // After a 422 the start button waits for a change, as SCR-04-validation draws it greyed.
  const [awaitingChange, setAwaitingChange] = useState(false);
  const [prefilling, setPrefilling] = useState(initialIntake !== undefined);
  const initial = useRef(initialIntake);
  // One write at a time, checked synchronously so a double press cannot send two starts.
  const writing = useRef(false);
  // The exact body last sent; "Check again" resends it unchanged with the same key.
  const sent = useRef<StartBody | null>(null);
  // Each evidence field's uploader, by field name.
  const [proof, setProof] = useState<Record<string, ProofState>>({});
  // The case revision the last upload (or upload re-read) returned; undefined means "the case as read".
  const [proofRevision, setProofRevision] = useState<number | undefined>(undefined);
  // Proof was added, then the project (so the case) changed: the line under the Proof box says so.
  const [proofMoved, setProofMoved] = useState(false);

  useEffect(() => {
    const wanted = initial.current;
    if (!wanted) return undefined;
    let cancelled = false;
    void (async () => {
      const filled: Values = {};
      const notes: Record<string, string> = {};
      for (const field of fields) {
        const raw = wanted[field.name];
        if (raw === undefined || raw === null) continue;
        if (field.type !== 'record' && field.type !== 'records') {
          const value = plainValue(field, raw);
          if (value !== undefined) filled[field.name] = value;
          continue;
        }
        const values = (Array.isArray(raw) ? raw : [raw]).filter((v): v is string => typeof v === 'string');
        const parent = parentValue(field, filled);
        if (values.length === 0 || (field.depends_on && parent === undefined)) {
          notes[field.name] = NO_LONGER_AVAILABLE;
          continue;
        }
        try {
          const options = await findOptions(line.key, field.name, parent, values);
          if (options.length === 0) notes[field.name] = NO_LONGER_AVAILABLE;
          else filled[field.name] = field.type === 'records' ? options : options[0];
        } catch {
          // Not read: the field stays empty and the person chooses.
        }
      }
      if (cancelled) return;
      setValues(filled);
      setFieldNotes(notes);
      setPrefilling(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [fields, line.key]);

  const caseLine = useMemo(() => ({ ...line, case_revision: fixedRevision }), [line, fixedRevision]);
  const caseRef = resolveCase(caseLine, values);
  // The case the uploads and the start go to, at the revision the last upload returned.
  const [caseId, readRevision] = [caseRef?.case_id, caseRef?.case_revision];
  const sendCase = useMemo(
    () => (caseId !== undefined && readRevision !== undefined ? { case_id: caseId, case_revision: proofRevision ?? readRevision } : null),
    [caseId, proofRevision, readRevision],
  );
  const proofs = Object.values(proof);
  const proofBusy = proofs.some((p) => p.busy);
  const proofHeld = proofBusy || proofs.some((p) => p.failed);

  const show = useCallback((next: Notice | null) => {
    setNotice(next);
    setNoticeSeq((n) => n + 1);
  }, []);

  const setValue = useCallback(
    (name: string, value: FieldValue | undefined) => {
      const cleared = dependentsOf(fields, name);
      setAwaitingChange(false);
      // the "is required" message goes once the field is changed
      setFieldErrors((current) => {
        const field = fields.find((f) => f.name === name);
        return field && current[name] === requiredMessage(field) ? Object.fromEntries(Object.entries(current).filter(([k]) => k !== name)) : current;
      });
      if (name === line.case_field && line.case_scope === 'project') {
        const caseOf = (v: FieldValue | undefined) => (v && typeof v === 'object' && 'case_id' in v ? v.case_id : undefined);
        if (caseOf(values[name]) !== caseOf(value)) {
          // The uploaders are keyed by case, so they start again empty; what was added stays on the old case.
          setProofRevision(undefined);
          setProof({});
          if (Object.values(proof).some((p) => p.count > 0)) setProofMoved(true);
        }
      }
      // a typed-in new client's name is checked by this drawer, so its message goes when the name is edited
      if (isNew(values[name]) || isNew(value)) setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([key]) => key !== name)));
      setValues((current) => {
        const next = { ...current, [name]: value };
        for (const dependent of cleared) delete next[dependent];
        // a field the change hides loses its value, so it is never sent
        for (let changed = true; changed; ) {
          changed = false;
          for (const field of fields) {
            if (next[field.name] !== undefined && !isShown(field, next)) {
              delete next[field.name];
              changed = true;
            }
          }
        }
        return next;
      });
      setFieldNotes((current) => {
        const next = { ...current };
        for (const dependent of [name, ...cleared]) delete next[dependent];
        return next;
      });
    },
    [fields, line.case_field, line.case_scope, proof, values],
  );

  /** An uploader's files changed (added, answered, failed or removed): a change, so a start held after a 422 may go again. */
  const reportProof = useCallback((name: string, state: ProofState) => {
    setProof((current) => ({ ...current, [name]: state }));
    setAwaitingChange(false);
    if (state.ids.length > 0) setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([k]) => k !== name)));
    if (state.count > 0) setProofMoved(false);
    setProofRevision(state.revision);
  }, []);

  /** An upload was refused (403 or 404): the same notice for both. */
  const proofRefused = useCallback(() => show({ kind: 'problem', message: CANT_ADD }), [show]);
  const signOut = useCallback(() => setSignedOut(true), []);

  /** For an upload's 409 and its Try again: re-read the case revision from where it came from, keep every value,
   *  and return it. A project no longer served is cleared with a note, as after a start's 409. */
  const rereadCase = useCallback(async (): Promise<number | undefined> => {
    // No case left to re-read: refuse, so the hook's Try again stops instead of uploading to a dropped case.
    const gone = () => new ApiError(404, 'not_found', 'not_found', 'This case is no longer served.');
    if (line.case_scope === 'fixed') {
      const current = (await fetchLines()).items.find((l) => l.key === line.key);
      if (!current) throw gone();
      setFixedRevision(current.case_revision);
      setProofRevision(current.case_revision);
      return current.case_revision;
    }
    const field = fields.find((f) => f.name === line.case_field);
    const chosen = field ? (values[field.name] as LineOption | undefined) : undefined;
    if (!field || !chosen) throw gone();
    const page = await fetchOptions(line.key, field.name, { parent: parentValue(field, values), q: chosen.label });
    const fresh = page.items.find((option) => option.value === chosen.value);
    if (!fresh || fresh.case_id !== chosen.case_id) {
      setValue(field.name, undefined);
      setFieldNotes((current) => ({ ...current, [field.name]: NO_LONGER_AVAILABLE }));
      throw gone();
    }
    setValues((current) => ({ ...current, [field.name]: fresh }));
    setProofRevision(fresh.case_revision);
    return fresh.case_revision;
  }, [fields, line, setValue, values]);

  /** PMO-0-3: keep every value and re-read the case revision from where it came from. */
  const reloadRevision = useCallback(async () => {
    // The re-read revision is the one to send; the uploaders follow it (StartProof syncs them).
    setProofRevision(undefined);
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
    if (writing.current || prefilling) return;
    if (!(uncertain && sent.current) && proofHeld) return;
    if (!(uncertain && sent.current)) {
      // F-49: a "New client" with no name is not sent; the field says so, as a required field does.
      const nameless = drawn.find((f) => {
        const value = values[f.name];
        return isNew(value) && value.new.name.trim() === '';
      });
      if (nameless) {
        setFieldErrors((current) => ({ ...current, [nameless.name]: `${nameless.label} is required.` }));
        return;
      }
    }
    const ids = Object.fromEntries(Object.entries(proof).map(([name, p]) => [name, p.ids]));
    if (!(uncertain && sent.current)) {
      // A required field left empty is named on the page and nothing is sent.
      const empty = emptyRequired(drawn, values, ids);
      if (empty.length > 0) {
        setFieldErrors(Object.fromEntries(empty.map((f) => [f.name, requiredMessage(f)])));
        setNotice(null);
        setFocus((current) => ({ seq: current.seq + 1, name: empty[0].name }));
        return;
      }
    }
    const body: StartBody | null =
      uncertain && sent.current
        ? sent.current
        : sendCase && { line: line.key, ...sendCase, intake: buildIntake(drawn, values, ids), idempotency_key: key };
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
      if ((response.status === 200 || response.status === 201) && data && typeof data === 'object' && 'work_id' in data) {
        const id = data.work_id;
        if ((typeof id === 'string' && id.trim()) || (typeof id === 'number' && Number.isSafeInteger(id) && id > 0)) {
          return onStarted(String(id));
        }
      }
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
        // A problem for a field this drawer does not render is drawn as its own box; one for Proof sits under it.
        const names = new Set(drawn.filter(fillable).map((f) => f.name));
        const inline = Object.fromEntries(problems.filter((p) => names.has(p.name)).map((p) => [p.name, p.message]));
        const unmatched = problems.filter((p) => !names.has(p.name));
        setFieldErrors(inline);
        setAwaitingChange(true);
        return show({ kind: 'invalid', count: problems.length || 1, unmatched, general: problems.length > 0 ? undefined : apiError.message });
      }
      if (response.status === 409) {
        setKey(newIdempotencyKey());
        if (apiError.code === 'idempotency_conflict') return show({ kind: 'problem', message: apiError.message });
        onConflict?.();
        return await reloadRevision();
      }
      const lead = response.status === 403 || response.status === 404 ? 'You can’t start this here.' : undefined;
      show({ kind: 'problem', lead, message: apiError.message });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [drawn, key, line.key, onConflict, onStarted, prefilling, proof, proofHeld, reloadRevision, sendCase, show, uncertain, values]);

  return {
    fields: drawn,
    values,
    setValue,
    caseRef,
    sendCase,
    proofBusy,
    proofHeld,
    proofMoved,
    reportProof,
    rereadCase,
    proofRefused,
    signOut,
    busy,
    uncertain,
    signedOut,
    notice,
    noticeSeq,
    fieldErrors,
    fieldNotes,
    focus,
    awaitingChange,
    prefilling,
    submit,
  };
}
