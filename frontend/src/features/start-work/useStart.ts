'use client';

// SCR-04 start. One `POST /work` per press with CSRF, the project's revision and one idempotency key. The key is made
// when the form opens and reused for every resend of the same body. A double press sends one request (a synchronous
// guard). An uncertain result (500, 503, network, the timeout, or a 2xx with no work id) locks the form until "Check
// again", which resends the same body with the same key. A definitive 409, 422 or 429 means nothing was recorded: the
// form unlocks and the next press uses a new key. Nothing is ever resent by itself.
import { useCallback, useMemo, useRef, useState } from 'react';

import { csrfHeader, liveApi, refreshSession } from '@/api/client';
import { ApiError, errorFromResponse } from '@/api/errors';

import { newIdempotencyKey, type FieldValue, type Values } from './intake';
import { RECORD_UNAVAILABLE } from './labels';
import type { LineForm } from './lines';
import type { FieldProblem, Project, StartBody } from './types';
import { fetchProjects, START_TIMEOUT_MS } from './useStartWork';

export const PROJECT_REQUIRED = 'Project is required.';
export const REFRESH_SESSION = 'Refresh your session and try again.';
export const NOT_CONFIRMED = 'Not confirmed. Check before trying again.';
export const RATE_LIMITED = 'Try again shortly.';
export const ROLE_REFUSED = 'Your role doesn’t let you start this line.';

export type Notice =
  /** `unmatched`: 422 problems naming no control, drawn as their own boxes; `general`: messages with no control. */
  | { kind: 'invalid'; unmatched: FieldProblem[]; general: string[] }
  | { kind: 'stale'; message?: string }
  | { kind: 'problem'; message: string }
  | { kind: 'uncertain' };

/** The control a problem is drawn under, by the line's table; the case names belong to the shell's project box. */
export function mapProblems(form: Pick<LineForm, 'target'>, problems: FieldProblem[]) {
  const errors: Record<string, string> = {};
  const unmatched: FieldProblem[] = [];
  const general: string[] = [];
  for (const problem of problems) {
    const control = form.target(problem.name);
    if (control === undefined) unmatched.push(problem);
    else if (control === 'general') general.push(problem.message);
    else errors[control] = errors[control] ? `${errors[control]} ${problem.message}` : problem.message;
  }
  return { errors, unmatched, general };
}

/** A work id the server answered, or null. */
const workIdOf = (data: unknown): number | null => {
  const id = data && typeof data === 'object' ? (data as { work_id?: unknown }).work_id : undefined;
  return typeof id === 'number' && Number.isSafeInteger(id) && id > 0 ? id : null;
};

export function useStart(form: LineForm, onStarted: (workId: string) => void, onConflict?: () => void) {
  const [values, setValues] = useState<Values>({});
  const [project, setProject] = useState<Project | null>(null);
  const [key, setKey] = useState(newIdempotencyKey);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Bumped when a press finds required fields empty or the server names fields, so the summary takes focus.
  const [attempt, setAttempt] = useState(0);
  // One write at a time, checked synchronously so a double press cannot send two starts.
  const writing = useRef(false);
  // The exact body last sent; "Check again" resends it unchanged with the same key.
  const sent = useRef<StartBody | null>(null);

  const clearError = useCallback((name: string) => setErrors((current) => (name in current ? Object.fromEntries(Object.entries(current).filter(([k]) => k !== name)) : current)), []);

  const setValue = useCallback(
    (name: string, value: FieldValue | undefined) => {
      setValues((current) => ({ ...current, [name]: value }));
      clearError(name);
    },
    [clearError],
  );

  const chooseProject = useCallback(
    (next: Project | null) => {
      if (project?.case_id !== next?.case_id) {
        // What was added to the old case (source records, uploads) does not follow the person to another.
        setValues((v) => Object.fromEntries(Object.entries(v).filter(([name]) => !form.projectBound?.includes(name))));
      }
      setProject(next);
      clearError('project');
    },
    [clearError, form.projectBound, project],
  );

  /** A 409: nothing was recorded. Keep every value, read the project's revision again from the same title search. */
  const rereadRevision = useCallback(
    async (current: Project) => {
      try {
        const page = await fetchProjects(form.key, current.title);
        const fresh = page.items.find((p) => p.case_id === current.case_id);
        if (fresh) setProject(fresh);
      } catch {
        // The notice still shows; the next press sends what was last read and answers again.
      }
    },
    [form.key],
  );

  const submit = useCallback(async () => {
    if (writing.current) return;
    let body: StartBody | null = uncertain ? sent.current : null;
    if (!body) {
      const missing = [...(project ? [] : [{ name: 'project', label: 'Project' }]), ...form.missing(values)];
      if (missing.length > 0) {
        setErrors(Object.fromEntries(missing.map((m) => [m.name, `${m.label} is required.`])));
        setNotice(null);
        setAttempt((n) => n + 1);
        return;
      }
      if (!project) return;
      body = form.buildBody(values, { caseId: project.case_id, caseRevision: project.case_revision, idempotencyKey: key });
    }
    writing.current = true;
    sent.current = body;
    setBusy(true);
    try {
      let response: Response;
      let data: unknown;
      let error: unknown;
      try {
        ({ response, data, error } = await liveApi.POST('/api/v1/work', { params: csrfHeader, body, signal: AbortSignal.timeout(START_TIMEOUT_MS) }));
      } catch (thrown) {
        // Thrown before sending (no CSRF token): nothing was sent. Anything else may have reached the server.
        if (thrown instanceof ApiError && thrown.kind === 'unauthenticated') return setSignedOut(true);
        setUncertain(true);
        return setNotice({ kind: 'uncertain' });
      }
      if (response.ok) {
        const id = workIdOf(data);
        if (id !== null) return onStarted(String(id));
        setUncertain(true);
        return setNotice({ kind: 'uncertain' });
      }
      if (response.status >= 500) {
        setUncertain(true);
        return setNotice({ kind: 'uncertain' });
      }
      // A definitive answer: nothing was recorded, so unlock the form.
      setUncertain(false);
      sent.current = null;
      const apiError = errorFromResponse(response.status, error);
      const serverMessage = (error as { message?: unknown } | undefined)?.message;
      const said = typeof serverMessage === 'string' && serverMessage ? serverMessage : apiError.message;
      setErrors({});
      switch (apiError.kind) {
        case 'unauthenticated':
          return setSignedOut(true);
        case 'csrf':
          // The token was stale; the session is read again once and the form stays as it is.
          await refreshSession().catch(() => undefined);
          return setNotice({ kind: 'problem', message: REFRESH_SESSION });
        case 'forbidden':
          return setNotice({ kind: 'problem', message: `${ROLE_REFUSED}${apiError.code === 'unexpected_response' ? '' : ` ${said}`}` });
        case 'not_found':
          return setNotice({ kind: 'problem', message: RECORD_UNAVAILABLE });
        case 'stale':
          setKey(newIdempotencyKey());
          onConflict?.();
          if (project) await rereadRevision(project);
          return setNotice({ kind: 'stale', message: said });
        case 'rate_limited':
          setKey(newIdempotencyKey());
          return setNotice({ kind: 'problem', message: RATE_LIMITED });
        case 'invalid': {
          setKey(newIdempotencyKey());
          const mapped = mapProblems(form, apiError.fields);
          setErrors(mapped.errors);
          setAttempt((n) => n + 1);
          return setNotice({ kind: 'invalid', unmatched: mapped.unmatched, general: apiError.fields.length === 0 ? [said] : mapped.general });
        }
        case 'too_large':
        case 'unsupported':
          return setNotice({ kind: 'problem', message: said });
        default:
          return setNotice({ kind: 'problem', message: apiError.message });
      }
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [form, key, onConflict, onStarted, project, rereadRevision, uncertain, values]);

  const problems = useMemo(
    () => Object.entries(errors).map(([name, message]) => ({ fieldId: `sw-field-${name}`, message })),
    [errors],
  );

  return { values, setValue, project, chooseProject, busy, uncertain, signedOut, notice, errors, problems, attempt, submit };
}
