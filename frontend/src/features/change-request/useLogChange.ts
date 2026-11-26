'use client';

// F-112: the "Log a change" drawer's read (GET /projects/{case_id}/ordinary-changes: the proofs and the case revision) and its one
// write (POST the same path, `capture`). One press is one POST: no retry, timer or idempotency key. "Logged" is said only when the list
// is read again and holds the new change. A dropped connection or a 5xx locks the form; "Check the list" only reads.
import { useCallback, useEffect, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { bodyOf, CONTROL, isCaptured, isRegisterRead, type Draft, type LoggedChange, type Register } from './logChange';

export const LOG_TEXT = {
  uncertain: 'We couldn’t confirm that this happened. Check the page before trying again.',
  notFound: 'The change isn’t in the list yet. Nothing here shows it was logged.',
  stale: 'This changed while you were working. Your entries are kept; check them and press Log the change again.',
  forbidden: 'Your role does not allow this.',
  gone: 'This project isn’t available.',
} as const;

export type LogView =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'lost'; why: 'unauthenticated' | 'forbidden' | 'not_found'; message: string }
  | { kind: 'ready'; data: Register }
  /** The re-read holds the change: what it is now, from the list. */
  | { kind: 'done'; data: Register; change: LoggedChange };
export type LogNotice = { kind: 'problem'; message: string } | { kind: 'invalid'; general: string[] } | { kind: 'uncertain' };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

async function readRegister(caseId: string): Promise<Register> {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/ordinary-changes', { params: { path: { case_id: caseId } } }));
  if (!isRegisterRead(data)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  return data;
}

export function useLogChange(caseId: string, reloadList: () => Promise<void>) {
  const [view, setView] = useState<LogView>({ kind: 'loading' });
  const [notice, setNotice] = useState<LogNotice | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const writing = useRef(false);
  /** The reference sent when the result is unknown, so the check can look for it. */
  const sent = useRef<string | null>(null);

  const lostOf = useCallback((error: ApiError): LogView | null => {
    if (error.kind === 'unauthenticated') return { kind: 'lost', why: 'unauthenticated', message: error.message };
    if (error.kind === 'forbidden') return { kind: 'lost', why: 'forbidden', message: error.message || LOG_TEXT.forbidden };
    if (error.kind === 'not_found') return { kind: 'lost', why: 'not_found', message: LOG_TEXT.gone };
    return null;
  }, []);

  const load = useCallback(async () => {
    setView({ kind: 'loading' });
    try {
      setView({ kind: 'ready', data: await readRegister(caseId) });
    } catch (thrown) {
      setView(lostOf(asApiError(thrown)) ?? { kind: 'error' });
    }
  }, [caseId, lostOf]);
  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** After a 201 or an unknown result: read the list again; the change is shown only if it is in the read. */
  const settle = useCallback(
    async (find: (records: LoggedChange[]) => LoggedChange | undefined, missing: LogNotice) => {
      let data: Register;
      try {
        data = await readRegister(caseId);
      } catch {
        setNotice({ kind: 'uncertain' });
        return;
      }
      const change = find(data.records);
      if (change) {
        setView({ kind: 'done', data, change });
        setNotice(null);
        await reloadList();
      } else {
        setView({ kind: 'ready', data });
        setNotice(missing);
      }
    },
    [caseId, reloadList],
  );

  /** "Check the list": a read, never a write. */
  const check = useCallback(async () => {
    if (writing.current) return;
    writing.current = true;
    setBusy(true);
    const mine = sent.current;
    try {
      await settle((records) => records.find((r) => mine !== null && r.reference === mine), { kind: 'problem', message: LOG_TEXT.notFound });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [settle]);

  const submit = useCallback(
    async (data: Register, draft: Draft) => {
      if (writing.current) return;
      writing.current = true;
      setBusy(true);
      setNotice(null);
      setErrors({});
      const body = bodyOf(draft, data.case_revision);
      sent.current = body.reference;
      try {
        let created: unknown;
        try {
          created = await call(liveApi.POST('/api/v1/projects/{case_id}/ordinary-changes', { params: { path: { case_id: caseId }, ...csrfHeader }, body }));
          if (!isCaptured(created)) throw new ApiError(201, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
        } catch (thrown) {
          const error = asApiError(thrown);
          const lost = lostOf(error);
          if (lost) return setView(lost);
          if (error.kind === 'network' || error.kind === 'server' || error.kind === 'read_limited') return setNotice({ kind: 'uncertain' });
          if (error.kind === 'stale') {
            // the server's words, and the proofs and revision read again; the entries stay
            try {
              setView({ kind: 'ready', data: await readRegister(caseId) });
            } catch {
              /* the form keeps the old read; a second press would be refused again */
            }
            return setNotice({ kind: 'problem', message: error.message ? `${error.message} ${LOG_TEXT.stale}` : LOG_TEXT.stale });
          }
          if (error.kind === 'invalid' || error.kind === 'bad_request') {
            const mapped: Record<string, string> = {};
            const general: string[] = [];
            for (const field of error.fields) {
              const control = CONTROL[field.name];
              if (control) mapped[control] = mapped[control] ? `${mapped[control]} ${field.message}` : field.message;
              else general.push(field.message);
            }
            if (error.fields.length === 0) general.push(error.message);
            setErrors(mapped);
            setAttempt((n) => n + 1);
            return setNotice({ kind: 'invalid', general });
          }
          return setNotice({ kind: 'problem', message: error.message });
        }
        const id = (created as { id: number }).id;
        await settle((records) => records.find((r) => r.id === id), { kind: 'problem', message: LOG_TEXT.notFound });
      } finally {
        writing.current = false;
        setBusy(false);
      }
    },
    [caseId, lostOf, settle],
  );

  return { view, notice, errors, setErrors, attempt, busy, load, submit, check };
}
