'use client';

// E-WORK-ASSIGN from the workspace (F-30, contract mock only): set the accountable person. One write at a time,
// guarded synchronously so a double press sends once. The typed body has no idempotency key, so nothing here ever
// resends: after a 5xx or a network failure the item is re-read first, and the form is offered again only if that
// re-read still carries `assign` (no owner yet). Nothing says "Owner set" except a 200.
import { useCallback, useRef, useState } from 'react';

import { api } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import type { paths } from '@/api/schema';

import type { WorkspacePage } from './usePageReload';
import type { SubmitResult } from './useWorkspaceStep';

export type AssignBody = paths['/api/v1/work/{work_id}/assignment']['post']['requestBody']['content']['application/json'];
type FieldMessage = { name: string; message: string };

export type AssignNotice = { kind: 'done'; text: string } | { kind: 'stale'; revision: number | undefined } | { kind: 'unconfirmed' };

export const ASSIGN_TEXT = {
  done: (owner: string) => `Owner set: ${owner}`,
  // F-31: the engagement's PM confirmation (the form opened with the person the response names)
  pmDone: (owner: string) => `PM confirmed: ${owner}`,
  confirm: (role: string) => `Confirm ${role}`,
  unconfirmed: 'We couldn’t confirm the owner was set. Check the page before trying again.',
  unconfirmedHead: 'Not recorded',
  stale: (revision: number | undefined) =>
    revision === undefined ? 'This changed while you were working, and we couldn’t reload it.' : `This changed while you were working. Showing version ${revision}.`,
  noCandidates: 'No one can be chosen yet.',
  open: 'Set an owner',
  submit: 'Set owner',
  tryAgain: 'Try again',
  cancel: 'Cancel',
  owner: 'Owner',
  note: 'Note',
  chooseOwner: 'Choose an owner to continue.',
  needNote: 'Add a note to continue.',
  noteLong: 'Keep the note to 2000 characters.',
  choose: 'Choose an owner',
  kind: { team: 'Team', outside_party: 'Outside party' },
} as const;

async function postAssign(id: string, body: AssignBody) {
  const result = await api.POST('/api/v1/work/{work_id}/assignment', { params: { path: { work_id: id } }, body }).catch((error: unknown) => {
    throw error instanceof ApiError ? error : networkError();
  });
  if (result.response.ok && result.data) return result.data;
  const error = errorFromResponse(result.response.status, result.error);
  const fields = (result.error as { fields?: unknown } | undefined)?.fields;
  throw Object.assign(error, { fields: Array.isArray(fields) ? (fields as FieldMessage[]) : undefined });
}

export function useWorkspaceAssign({ id, revision, page, role }: { id: string; revision: number | undefined; page: WorkspacePage; role?: string }) {
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<AssignNotice | null>(null);
  const writing = useRef(false);

  const submit = useCallback(
    async (request: { person_id: string; note?: string }): Promise<SubmitResult> => {
      if (writing.current || page.refreshFailed || revision === undefined) return { kind: 'kept' };
      writing.current = true;
      setPending(true);
      try {
        const result = await postAssign(id, { expected_revision: revision, ...request });
        setNotice({ kind: 'done', text: role === 'PM' ? ASSIGN_TEXT.pmDone(result.assigned_to) : ASSIGN_TEXT.done(result.assigned_to) });
        await page.reload();
        return { kind: 'done' };
      } catch (error) {
        const apiError = error instanceof ApiError ? error : networkError();
        switch (apiError.kind) {
          case 'unauthenticated':
          case 'forbidden':
          case 'not_found':
            page.onAccessLost(apiError);
            return { kind: 'kept' };
          case 'stale': {
            const item = await page.reload();
            setNotice({ kind: 'stale', revision: item?.workspace?.revision });
            return { kind: 'kept' };
          }
          case 'invalid': {
            const fields: Record<string, string> = {};
            for (const f of (apiError as ApiError & { fields?: FieldMessage[] }).fields ?? []) {
              if (typeof f?.name === 'string' && typeof f.message === 'string') fields[f.name] = f.message;
            }
            return { kind: 'invalid', fields, message: apiError.message };
          }
          default:
            // It may or may not have happened: re-read to see, and never resend on our own.
            setNotice({ kind: 'unconfirmed' });
            await page.reload();
            return { kind: 'kept' };
        }
      } finally {
        writing.current = false;
        setPending(false);
      }
    },
    [id, page, revision, role],
  );

  return { submit, pending, notice, setNotice };
}
