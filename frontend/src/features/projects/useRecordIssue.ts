'use client';

// F-137: the "Record an issue" drawer's read (GET /projects/{case_id}/issues: the owners, the proofs and the case revision) and its one
// write (POST the same path). One press is one POST: no retry, timer or idempotency key. "Recorded" is said only when the register is
// read again and holds the new issue. A dropped connection or a 5xx locks the form; "Check the register" only reads.
import { useCallback, useEffect, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { bodyOf, CONTROL, isCaptured, isIssuesRead, type Draft, type IssuesRead, type RegisterIssue } from './recordIssue';

export const RECORD_TEXT = {
  uncertain: 'We couldn’t confirm that this happened. Check the page before trying again.',
  notFound: 'The issue isn’t in the register yet. Nothing here shows it was recorded.',
  stale: 'This changed while you were working. Your entries are kept; check them and press Record again.',
  forbidden: 'Your role does not allow this.',
  gone: 'This project isn’t available.',
} as const;

export type RecordView =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'lost'; why: 'unauthenticated' | 'forbidden' | 'not_found'; message: string }
  | { kind: 'ready'; data: IssuesRead }
  /** The re-read holds the issue: what it is now, from the register. */
  | { kind: 'done'; data: IssuesRead; issue: RegisterIssue };
export type RecordNotice = { kind: 'problem'; message: string } | { kind: 'invalid'; general: string[] } | { kind: 'uncertain' };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

async function readIssues(caseId: string): Promise<IssuesRead> {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/issues', { params: { path: { case_id: caseId } } }));
  if (!isIssuesRead(data)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  return data;
}

export function useRecordIssue(caseId: string, reloadList: () => Promise<void>) {
  const [view, setView] = useState<RecordView>({ kind: 'loading' });
  const [notice, setNotice] = useState<RecordNotice | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const writing = useRef(false);
  /** The reference sent when the result is unknown, so the check can look for it. */
  const sent = useRef<{ reference: string; title: string } | null>(null);

  const lostOf = useCallback((error: ApiError): RecordView | null => {
    if (error.kind === 'unauthenticated') return { kind: 'lost', why: 'unauthenticated', message: error.message };
    if (error.kind === 'forbidden') return { kind: 'lost', why: 'forbidden', message: error.message || RECORD_TEXT.forbidden };
    if (error.kind === 'not_found') return { kind: 'lost', why: 'not_found', message: RECORD_TEXT.gone };
    return null;
  }, []);

  const load = useCallback(async () => {
    setView({ kind: 'loading' });
    try {
      setView({ kind: 'ready', data: await readIssues(caseId) });
    } catch (thrown) {
      const error = asApiError(thrown);
      setView(lostOf(error) ?? { kind: 'error' });
    }
  }, [caseId, lostOf]);
  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** After a 201 or an unknown result: read the register again; the issue is shown only if it is in the read. */
  const settle = useCallback(
    async (find: (issues: RegisterIssue[]) => RegisterIssue | undefined, missing: RecordNotice) => {
      let data: IssuesRead;
      try {
        data = await readIssues(caseId);
      } catch {
        setNotice(missing.kind === 'uncertain' ? missing : { kind: 'uncertain' });
        return;
      }
      const issue = find(data.issues);
      if (issue) {
        setView({ kind: 'done', data, issue });
        setNotice(null);
        await reloadList();
      } else {
        setView({ kind: 'ready', data });
        setNotice(missing);
      }
    },
    [caseId, reloadList],
  );

  /** "Check the register": a read, never a write. */
  const check = useCallback(async () => {
    if (writing.current) return;
    writing.current = true;
    setBusy(true);
    const mine = sent.current;
    try {
      await settle((issues) => issues.find((i) => mine && i.reference === mine.reference && i.title === mine.title), { kind: 'problem', message: RECORD_TEXT.notFound });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [settle]);

  const submit = useCallback(
    async (data: IssuesRead, draft: Draft) => {
      if (writing.current) return;
      writing.current = true;
      setBusy(true);
      setNotice(null);
      setErrors({});
      const body = bodyOf(draft, data.case_revision);
      sent.current = { reference: body.reference, title: body.title };
      try {
        let created: unknown;
        try {
          created = await call(liveApi.POST('/api/v1/projects/{case_id}/issues', { params: { path: { case_id: caseId }, ...csrfHeader }, body }));
          if (!isCaptured(created)) throw new ApiError(201, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
        } catch (thrown) {
          const error = asApiError(thrown);
          const lost = lostOf(error);
          if (lost) return setView(lost);
          if (error.kind === 'network' || error.kind === 'server' || error.kind === 'read_limited') {
            return setNotice({ kind: 'uncertain' });
          }
          if (error.kind === 'stale') {
            // the server's words, and the choices and revision read again; the entries stay
            try {
              setView({ kind: 'ready', data: await readIssues(caseId) });
            } catch {
              /* the form keeps the old read; a second press would be refused again */
            }
            return setNotice({ kind: 'problem', message: error.message ? `${error.message} ${RECORD_TEXT.stale}` : RECORD_TEXT.stale });
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
        const id = (created as { issue_id: number }).issue_id;
        await settle((issues) => issues.find((i) => i.id === id), { kind: 'problem', message: RECORD_TEXT.notFound });
      } finally {
        writing.current = false;
        setBusy(false);
      }
    },
    [caseId, lostOf, settle],
  );

  return { view, notice, errors, setErrors, attempt, busy, load, submit, check };
}
