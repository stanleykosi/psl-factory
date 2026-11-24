'use client';

// F-87: the one sender for the live work item's writes (resume, cancel, background, check what happened, and every line form).
// A write happens only from a press: no timer, effect or loop here ever sends. One write at a time (the shared lock); a failed
// write with an unknown result locks that command until a re-read shows a newer revision. The result is told from the re-read,
// never from the 200/202 alone. Words for errors come from ApiError; the server's own message is shown as given.
import { useCallback, useEffect, useRef, useState } from 'react';

import { liveApi, refreshSession } from '@/api/client';
import { ApiError, errorFromResponse, networkError } from '@/api/errors';
import type { LiveWorkItem } from '@/api/types';
import { STATE_TAGS } from '@/features/work-item/labels';

import { isPanelUrl, type CommandDescriptor } from './adapter';
import { useScopedWriteLock } from './useWriteLock';

export const WORK_COMMAND_TEXT = {
  noVersion: 'We don’t have this item’s current version yet. Reload and try again.',
  unreadable: 'Sent. We couldn’t reload the item; reload the page to see its state.',
  changed: 'This changed while you were working. Showing the latest version.',
  uncertain: 'We couldn’t confirm that this happened. Check the page before trying again.',
  lockedBeside: 'Check the page before trying again.',
  csrf: 'Press the button again.',
  shortly: 'Try again shortly.',
  unavailable: 'This record is unavailable.',
} as const;

/** What the page draws under the controls: success is a status, everything else an alert. */
export type CommandNotice = { kind: 'success' | 'error'; text: string; detail?: string };

type Args = {
  /** The item (or line context) the commands were described from; only its `revision` is read. A new object means a new read landed. */
  item: { revision: number | null; workId?: number; id?: number };
  /** Re-reads GET /work/{id} (and the panels); resolves to the new item, or null when the read failed. */
  reload: () => Promise<LiveWorkItem | null>;
  /** A write answered 401 or 404: the page shows the signed-out or unavailable state. Without it the notice says so. */
  onAccessLost?: (error: ApiError) => void;
};

/** A lookup sends nothing to the client, so an unknown result never locks it. */
const LOOKUPS = new Set(['work.reconcile']);

/** The body as FormData for a multipart command; a file is a part, null and undefined are left out, an object is JSON text. */
export function toFormData(body: Record<string, unknown>): FormData {
  const form = new FormData();
  for (const [name, value] of Object.entries(body)) {
    if (value === null || value === undefined) continue;
    if (value instanceof Blob) form.append(name, value);
    else form.append(name, typeof value === 'object' ? JSON.stringify(value) : String(value));
  }
  return form;
}

/** POST the descriptor's body; resolves to the status, throws ApiError. A stale session token is refreshed once and the press is not repeated. */
async function send(command: CommandDescriptor, inputs: Record<string, unknown>): Promise<number> {
  // The CSRF token goes with every write, so only an API path of this site is ever posted to.
  if (!isPanelUrl(command.url)) throw new ApiError(0, 'invalid', 'refused_before_sending', 'We couldn’t send that. Nothing was changed.');
  const body = command.body(inputs);
  const multipart = command.contentType === 'multipart/form-data';
  let result;
  try {
    // The path is not a typed route here: the descriptor's url comes from the item or the line.
    result = await liveApi.POST(command.url as never, (multipart ? { body: {}, bodySerializer: () => toFormData(body) } : { body }) as never);
  } catch (error) {
    throw error instanceof ApiError ? error : networkError();
  }
  const { response } = result as { response: Response; error?: unknown };
  if (response.ok) {
    if (!(command.successStatuses as number[]).includes(response.status)) throw new ApiError(response.status, 'server', 'unexpected_status', 'Something went wrong.');
    return response.status;
  }
  const error = errorFromResponse(response.status, (result as { error?: unknown }).error);
  if (error.kind === 'csrf') await refreshSession().catch(() => undefined);
  throw error;
}

export function useWorkCommand({ item, reload, onAccessLost }: Args) {
  // Locks live per work item, above the components: they survive History and back, and a failed panel re-read.
  const { pending, locked, unread: unreadAt, begin, end, lock, setUnread: setUnreadAt } = useScopedWriteLock(String(item.workId ?? item.id ?? 'item'));
  const [notice, setNotice] = useState<CommandNotice | null>(null);
  // The send worked but the re-read did not: nothing may be pressed until a read lands (a new `item`).

  // the latest item, so a read that lands while a write runs is not mistaken for the one the write started from
  const latest = useRef(item);
  useEffect(() => {
    latest.current = item;
  });
  const busy = pending !== null || unreadAt === item;
  /** A command locked after an unknown result stays locked while the item's revision is the one it was sent with. */
  const lockKey = (id: string, revision: number | null) => `${id}@${revision}`;
  const lockedReason = (id: string) => (locked.has(lockKey(id, item.revision)) ? WORK_COMMAND_TEXT.lockedBeside : null);

  const run = useCallback(
    async (command: CommandDescriptor, inputs: Record<string, unknown> = {}) => {
      if (command.disabledReason || item.revision === null || busy || locked.has(lockKey(command.id, item.revision))) return;
      if (!begin(command.id)) return;
      setNotice(null);
      const sentRevision = item.revision;
      try {
        await send(command, inputs);
        const fresh = await reload();
        if (!fresh) {
          setUnreadAt(latest.current);
          setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.unreadable });
          return;
        }
        const now = STATE_TAGS[fresh.state]?.text ?? fresh.status_label;
        setNotice({ kind: 'success', text: command.id === 'work.reconcile' ? `Checked. This item is now: ${now}.` : `Done. This item is now: ${now}.` });
      } catch (caught) {
        const error = caught instanceof ApiError ? caught : networkError();
        switch (error.kind) {
          case 'unauthenticated':
          case 'not_found':
            if (onAccessLost) onAccessLost(error);
            else setNotice({ kind: 'error', text: error.kind === 'not_found' ? WORK_COMMAND_TEXT.unavailable : error.message });
            return;
          case 'forbidden':
            setNotice({ kind: 'error', text: 'You can’t do this.', detail: error.message });
            await reload();
            return;
          case 'csrf':
            setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.csrf });
            return;
          case 'stale':
            await reload();
            setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.changed, detail: error.message });
            return;
          case 'invalid':
            setNotice({ kind: 'error', text: error.message, ...(error.fields[0] ? { detail: error.fields[0].message } : {}) });
            await reload();
            return;
          case 'rate_limited':
          case 'read_limited':
            setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.shortly });
            return;
          case 'bad_request':
          case 'too_large':
          case 'unsupported':
            setNotice({ kind: 'error', text: error.message });
            return;
          default:
            if (error.status === 503) {
              setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.shortly });
              return;
            }
            // Network or server: it may or may not have happened. Re-read to show what did; never send again on our own.
            if (!LOOKUPS.has(command.id)) lock(lockKey(command.id, sentRevision));
            setNotice({ kind: 'error', text: WORK_COMMAND_TEXT.uncertain });
            await reload();
        }
      } finally {
        end();
      }
    },
    [begin, busy, end, item, lock, locked, onAccessLost, reload, setUnreadAt],
  );

  return { run, pending, busy, notice, lockedReason, clearNotice: () => setNotice(null) };
}
