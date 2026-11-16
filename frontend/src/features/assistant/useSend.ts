'use client';

// The composer's state and the two writes (E-CONVERSATION-NEW, E-MESSAGE). One press is one request: a synchronous
// lock ignores a second press while one is in flight. The typed bodies have no idempotency key (Conflicts 17,
// G-SCR05-3), so nothing is ever resent automatically. After a network error or 5xx the conversation is read again:
// if a new person message is there it is shown and not sent again; if not, "Try again" waits for the person.
import { useCallback, useRef, useState } from 'react';

import { fetchConversation, createConversation, postMessage } from './api';
import { CHANGED, SEND_UNSURE, TEXT_LIMIT, TOO_LONG } from './labels';
import type { AgentName, Conversation, MentionOption, MessageBody } from './types';

export type Chip = Pick<MentionOption, 'kind' | 'id' | 'label'>;
export const chipKey = (chip: Pick<Chip, 'kind' | 'id'>) => `${chip.kind}:${chip.id}`;
/** "@" for a project or person, "#" for a work item or document (the boards' marks). */
export const chipLabel = (chip: Chip) => `${chip.kind === 'project' || chip.kind === 'person' ? '@' : '#'}${chip.label}`;

const personMessages = (conversation: Conversation) => conversation.messages.filter((m) => m.role === 'person').length;

export function useSend({ agent, conversationId, personCount = 0, reload, listChanged, onSent }: {
  agent: AgentName;
  /** Set in a thread; absent on the home, where the first send makes the conversation. */
  conversationId?: string;
  /** How many of the person's messages the thread shows now: a lost send is found by a new one appearing. */
  personCount?: number;
  /** Re-reads the open thread (the thread's own hook). */
  reload?: () => Promise<Conversation | undefined>;
  /** The list should be read again. */
  listChanged: () => void;
  /** The home only: the message was sent (or found already sent) in this new conversation. */
  onSent?: (conversationId: string) => void;
}) {
  const [text, setText] = useState('');
  const [chips, setChips] = useState<Chip[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [unsure, setUnsure] = useState(false);
  const [notice, setNotice] = useState<string>();
  const [signedOut, setSignedOut] = useState(false);
  const writing = useRef(false);
  // The conversation made by this composer's first send, so a "Try again" never makes a second one.
  const created = useRef<string | undefined>(undefined);

  const trimmed = text.trim();
  const tooLong = text.length > TEXT_LIMIT;
  const canSend = trimmed !== '' && !tooLong;

  const addChip = useCallback((chip: Chip) => setChips((all) => (all.some((c) => chipKey(c) === chipKey(chip)) ? all : [...all, chip])), []);
  const removeChip = useCallback((key: string) => setChips((all) => all.filter((c) => chipKey(c) !== key)), []);

  const send = useCallback(async () => {
    if (writing.current || !canSend) return;
    writing.current = true;
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    setUnsure(false);
    try {
      let id = conversationId ?? created.current;
      if (!id) {
        const made = await createConversation(agent);
        if (made.kind === 'refused') {
          if (made.error.kind === 'unauthenticated') return setSignedOut(true);
          return setError(made.error.message);
        }
        if (made.kind === 'unsure') {
          listChanged();
          setUnsure(true);
          return setError(SEND_UNSURE);
        }
        id = made.data.conversation_id;
        created.current = id;
      }
      const body: MessageBody = { text: trimmed, ...(chips.length > 0 ? { mentions: chips.map(({ kind, id: mentioned }) => ({ kind, id: mentioned })) } : {}) };
      const sent = await postMessage(id, body);
      const done = () => {
        setText('');
        setChips([]);
        created.current = undefined;
        listChanged();
      };
      if (sent.kind === 'ok') {
        done();
        if (conversationId) await reload?.();
        else onSent?.(id);
        return;
      }
      if (sent.kind === 'refused') {
        const { kind, message } = sent.error;
        if (kind === 'unauthenticated') return setSignedOut(true);
        if (kind === 'stale') {
          await reload?.();
          return setNotice(CHANGED);
        }
        return setError(message);
      }
      // Uncertain: read it again. If a new person message of theirs is there (the count went up), it was sent.
      const latest = conversationId ? await reload?.() : await fetchConversation(id).catch(() => undefined);
      listChanged();
      if (latest && personMessages(latest) > personCount) {
        done();
        if (!conversationId) onSent?.(id);
        return;
      }
      setUnsure(true);
      setError(SEND_UNSURE);
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [agent, canSend, chips, conversationId, listChanged, onSent, personCount, reload, trimmed]);

  return { text, setText, chips, addChip, removeChip, busy, canSend, error: tooLong ? TOO_LONG : error, unsure, notice, signedOut, send };
}
