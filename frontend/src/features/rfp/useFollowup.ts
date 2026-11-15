'use client';

// The drafted RFP follow-up (D-RFP-OUTCOME r2): sent only by a person's press on Send (INV-AGENT). No load, reload,
// timer or effect calls E-RFP-FOLLOWUP; only `send`, which a click handler calls. One request at a time (a ref
// guard, so a double press makes one request). The idempotency key is made once per (version, text) and kept for
// any repeat press of the same version and text; a new version or new text gets a new key. Nothing resends: a 409
// reloads and shows the current draft under the person's text, and a network or server error reloads once and
// leaves the next send to a new, deliberate press (with the same key). An effect_uncertain draft has no Send until
// the backend reconciles it (INV-RESEND).
import { useCallback, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import type { ResponseWorkItem } from '@/features/response';

import { sendFollowup } from './api';
import type { Followup, FollowupBody, FollowupReply } from './contract';

export type FollowupNotice =
  | { kind: 'stale' }
  | { kind: 'problem'; message: string }
  | { kind: 'uncertain' }
  /** Uncertain and the reload failed too: every follow-up control stays off; Try again only reads. */
  | { kind: 'unconfirmed'; checking: boolean };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'not_found']);

type Key = { version: number; body: string; key: string };

/** `reload` re-reads the item for the page (it replaces the page on access loss) and returns it, or the read's error. */
export function useFollowup(item: ResponseWorkItem, followup: Followup, reload: () => Promise<ResponseWorkItem | ApiError>) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const [notice, setNotice] = useState<FollowupNotice | null>(null);
  const [busy, setBusy] = useState(false);
  /** The status the last 200 returned, shown until the reload brings the draft's own. */
  const [replied, setReplied] = useState<FollowupReply['status'] | null>(null);
  /** A 403 removes Send whatever the reloaded draft says. */
  const [refused, setRefused] = useState(false);
  const sending = useRef(false);
  const lastKey = useRef<Key | null>(null);

  const edit = useCallback(() => {
    setText(followup.body);
    setEditing(true);
  }, [followup.body]);

  /** Leave the edit box and go back to the drafted text, which is what Send then sends. */
  const useDraft = useCallback(() => setEditing(false), []);

  /** An open edit box with nothing in it: Send stays off rather than sending the original draft unseen. */
  const blank = editing && text.trim() === '';

  /** The edited text, only when it differs from the draft and is not blank. */
  const edited = editing && text.trim() !== '' && text !== followup.body ? text : undefined;

  const keyFor = (version: number, body: string) => {
    const last = lastKey.current;
    if (last && last.version === version && last.body === body) return last.key;
    const next = { version, body, key: crypto.randomUUID() };
    lastKey.current = next;
    return next.key;
  };

  const send = useCallback(async () => {
    if (sending.current || blank || refused || followup.status !== 'drafted' || !followup.can_send || notice?.kind === 'unconfirmed') return;
    sending.current = true;
    setBusy(true);
    setNotice(null);
    const body: FollowupBody = { expected_revision: item.revision, version: followup.version, idempotency_key: keyFor(followup.version, edited ?? '') };
    if (edited !== undefined) body.body = edited;
    try {
      let reply: FollowupReply;
      try {
        reply = await sendFollowup(item.id, body);
      } catch (error) {
        const apiError = asApiError(error);
        if (ACCESS_LOST.has(apiError.kind)) {
          await reload();
          return;
        }
        if (apiError.kind === 'invalid') return setNotice({ kind: 'problem', message: apiError.message });
        if (apiError.kind === 'forbidden') {
          setRefused(true);
          setNotice({ kind: 'problem', message: apiError.message });
          await reload();
          return;
        }
        if (apiError.kind === 'stale') {
          const next = await reload();
          if (!(next instanceof ApiError)) setNotice({ kind: 'stale' });
          return;
        }
        setNotice({ kind: 'uncertain' });
        const next = await reload();
        if (next instanceof ApiError && !ACCESS_LOST.has(next.kind) && next.kind !== 'forbidden') setNotice({ kind: 'unconfirmed', checking: false });
        return;
      }
      setReplied(reply.status);
      setEditing(false);
      await reload();
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }, [blank, refused, followup, notice, item, edited, reload]);

  /** "Check again" or "Try again": one read, never a send. */
  const check = useCallback(async () => {
    if (notice?.kind === 'unconfirmed') setNotice({ kind: 'unconfirmed', checking: true });
    const next = await reload();
    if (next instanceof ApiError) {
      if (!ACCESS_LOST.has(next.kind) && next.kind !== 'forbidden') setNotice({ kind: 'unconfirmed', checking: false });
      return;
    }
    if (notice?.kind === 'unconfirmed') setNotice({ kind: 'uncertain' });
  }, [notice, reload]);

  return { editing, edit, useDraft, blank, text, setText, edited, notice, busy, replied, refused, send, check };
}
