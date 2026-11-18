'use client';

// E-WORK-STEP from the workspace (PROPOSAL D-LINE-WORKSPACE, contract mock only). One write at a time per page,
// guarded synchronously so a double click sends once. One idempotency key per attempt: made when a form opens or
// on the first press, kept for a manual Try again, renewed only after done, a definitive 409 or 422, or a new
// form. Nothing here ever retries a write on its own (no timers, no effects that send). The backend's promise
// for the key (same key, same result, no second send) is not built; the page trusts none of it.
import { useCallback, useRef, useState } from 'react';

import { api } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import { newIdempotencyKey } from '@/features/start-work/intake';
import type { paths } from '@/api/schema';

import type { Step } from './labels';
import type { WorkspacePage } from './usePageReload';

export type StepBody = paths['/api/v1/work/{work_id}/steps']['post']['requestBody']['content']['application/json'];

export type StepNotice =
  | { kind: 'done'; text: string; label?: string }
  | { kind: 'queued'; text: string }
  | { kind: 'uncertain'; message?: string }
  | { kind: 'stale'; revision: number | undefined }
  | { kind: 'forbidden' }
  | { kind: 'problem'; text: string }
  | { kind: 'failed'; sends: boolean; attempt: string; label: string };

/** What a submit tells its form: field messages and a message for the top of the form, or a closed form. */
export type SubmitResult =
  | { kind: 'done' }
  | { kind: 'invalid'; fields: Record<string, string>; message?: string }
  | { kind: 'kept' };

export type Attempt = { token: string; step: Step; itemIds?: string[] };

export const STEP_TEXT = {
  done: (label: string) => `Done: ${label}.`,
  queued: 'This step is queued.',
  uncertainNoReconcile: 'We are checking what happened. Nothing was sent again.',
  stale: (revision: number | undefined) =>
    revision === undefined ? 'This changed while you were working, and we couldn’t reload it.' : `This changed while you were working. Showing version ${revision}.`,
  forbidden: 'You can’t take that step.',
  failed: 'We couldn’t confirm this step. Check the page before trying again.',
  sends: 'This sends to the client.',
  claim: 'Claim it first',
  confirmFirst: 'Confirm what happened first.',
  confirmFirstByOther: 'Someone with reconcile access needs to confirm what happened first.',
  decide: 'Decide',
  next: 'Next',
} as const;

export type StepResult = paths['/api/v1/work/{work_id}/steps']['post']['responses'][200]['content']['application/json'];
type FieldMessage = { name: string; message: string };

/** The write, through the shared client (CSRF from there). A 422's named fields are kept, which `call` drops. */
async function postStep(id: string, body: StepBody): Promise<StepResult> {
  const result = await api.POST('/api/v1/work/{work_id}/steps', { params: { path: { work_id: id } }, body }).catch((error: unknown) => {
    throw error instanceof ApiError ? error : networkError();
  });
  if (result.response.ok && result.data) return result.data;
  const error = errorFromResponse(result.response.status, result.error);
  const fields = (result.error as { fields?: unknown } | undefined)?.fields;
  throw Object.assign(error, { fields: Array.isArray(fields) ? (fields as FieldMessage[]) : undefined });
}

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

type Args = {
  id: string;
  revision: number | undefined;
  page: WorkspacePage;
  /** The item itself is waiting for someone to confirm what happened: no step may send, whoever looks at it. */
  awaitingReconcile: boolean;
};

export function useWorkspaceStep({ id, revision, page, awaitingReconcile }: Args) {
  const [pending, setPending] = useState<string | null>(null);
  const [notice, setNotice] = useState<StepNotice | null>(null);
  // INV-RESEND: an uncertain effect turns every step off; a failed step that sends stays off. The press itself locks at once; the item's own state keeps it locked.
  const [pressLocked, setAllLocked] = useState(false);
  // ...and it stays off after a reload, because the item itself says it is awaiting reconcile.
  const allLocked = pressLocked || awaitingReconcile;
  const [locked, setLocked] = useState<ReadonlySet<string>>(() => new Set());
  const writing = useRef(false);
  const key = useRef<{ token: string; key: string } | null>(null);

  /** A new attempt: a fresh key (a form opening, or after done, 409 or 422). */
  const renew = useCallback((token: string) => {
    key.current = { token, key: newIdempotencyKey() };
  }, []);
  const keyFor = (token: string) => {
    if (key.current?.token !== token) renew(token);
    return key.current!.key;
  };
  const drop = () => {
    key.current = null;
  };

  const submit = useCallback(
    async (attempt: Attempt, extra: Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'> = {}): Promise<SubmitResult> => {
      if (writing.current || allLocked || locked.has(attempt.step.key) || page.refreshFailed || revision === undefined) return { kind: 'kept' };
      writing.current = true;
      setPending(attempt.token);
      const { step } = attempt;
      const body: StepBody = { expected_revision: revision, step: step.key, idempotency_key: keyFor(attempt.token), ...extra };
      if (attempt.itemIds) body.item_ids = attempt.itemIds;
      try {
        const result = await postStep(id, body);
        drop();
        if (result.outcome === 'effect_uncertain') {
          setAllLocked(true);
          setNotice({ kind: 'uncertain', message: result.message });
          await page.reload();
          return { kind: 'done' };
        }
        // F-41 TECH-1-1: a done or queued notice is told only once the re-read has landed, never from the 200 alone
        await page.reload();
        if (result.outcome === 'queued') {
          setNotice({ kind: 'queued', text: `Waiting: ${result.message ?? STEP_TEXT.queued}` });
        } else {
          // a returned message that doesn't name the step gets the step's name beside it
          setNotice(result.message ? { kind: 'done', text: result.message, label: result.message.includes(step.label) || /^done\b/i.test(result.message) ? undefined : step.label } : { kind: 'done', text: STEP_TEXT.done(step.label) });
        }
        return { kind: 'done' };
      } catch (error) {
        const apiError = asApiError(error);
        switch (apiError.kind) {
          case 'unauthenticated':
          case 'not_found':
            page.onAccessLost(apiError);
            return { kind: 'kept' };
          case 'forbidden':
            drop();
            setNotice({ kind: 'forbidden' });
            await page.reload();
            return { kind: 'done' };
          case 'stale': {
            drop();
            const item = await page.reload();
            setNotice({ kind: 'stale', revision: item?.workspace?.revision });
            return { kind: 'kept' };
          }
          case 'invalid': {
            drop();
            const fields: Record<string, string> = {};
            for (const f of (apiError as ApiError & { fields?: FieldMessage[] }).fields ?? []) {
              if (typeof f?.name === 'string' && typeof f.message === 'string') fields[f.name] = f.message;
            }
            return { kind: 'invalid', fields, message: apiError.message };
          }
          default: {
            // Network or server: it may or may not have happened. Reload to show what did; never resend on our own.
            if (step.sends) {
              drop();
              setLocked((current) => new Set(current).add(step.key));
            }
            setNotice({ kind: 'failed', sends: step.sends === true, attempt: attempt.token, label: step.label });
            await page.reload();
            return { kind: 'kept' };
          }
        }
      } finally {
        writing.current = false;
        setPending(null);
      }
    },
    // keyFor and drop only touch the ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allLocked, id, locked, page, revision],
  );

  return { submit, renew, pending, notice, setNotice, allLocked, locked, writing };
}
