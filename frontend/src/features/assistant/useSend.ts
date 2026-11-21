'use client';

// The composer's state and the two writes (E-CONVERSATION-NEW, E-MESSAGE). One press is one request: a synchronous
// lock ignores a second press while one is in flight, and the button stays busy until the agent has replied (D-160).
// The message shows in the thread at once, as `pending` in the frame; a refused send takes it back out and puts the
// text, chips and images back in the composer. Images (PROPOSAL D-161) upload one request each, when chosen. The typed bodies have no idempotency key (Conflicts 17,
// G-SCR05-3), so nothing is ever resent automatically. After a network error or 5xx the conversation is read again:
// if a new person message is there it is shown and not sent again; if not, "Try again" waits for the person.
import { useCallback, useEffect, useRef, useState } from 'react';

import { useAssistant } from './AssistantContext';
import { fetchConversation, createConversation, postMessage, uploadImage } from './api';
import { CHANGED, IMAGE_UNSURE, SEND_UNSURE, TEXT_LIMIT, TOO_LONG } from './labels';
import { personMessages } from './pending';
import type { AgentName, Conversation, MentionOption, MessageBody } from './types';

export type Chip = Pick<MentionOption, 'kind' | 'id' | 'label'>;
export const chipKey = (chip: Pick<Chip, 'kind' | 'id'>) => `${chip.kind}:${chip.id}`;
/** "@" for a project or person, "#" for a work item or document (the boards' marks). */
export const chipLabel = (chip: Chip) => `${chip.kind === 'project' || chip.kind === 'person' ? '@' : '#'}${chip.label}`;

/** A chosen image: `src` is a local preview; `fileId` is the upload's answer. */
export type ImageItem = { id: string; name: string; src: string; state: 'uploading' | 'ready' | 'error'; error?: string; fileId?: string };
export type SentImage = Pick<ImageItem, 'id' | 'name' | 'src'>;

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
  const { pending, setPending } = useAssistant();
  const [text, setText] = useState('');
  const [chips, setChips] = useState<Chip[]>([]);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [error, setError] = useState<string>();
  const [unsure, setUnsure] = useState(false);
  const [notice, setNotice] = useState<string>();
  const [signedOut, setSignedOut] = useState(false);
  const writing = useRef(false);
  const counter = useRef(0);
  // The conversation made by this composer's first send, so a "Try again" never makes a second one.
  const created = useRef<string | undefined>(undefined);
  // Busy from the press until the agent has replied: the message is the frame's `pending`, for this conversation.
  // On the home it is this composer's own press (`started`): the home is left for the thread as soon as the message is confirmed.
  const [started, setStarted] = useState(false);
  const busy = pending !== undefined && (conversationId ? pending.conversationId === conversationId : started);

  const trimmed = text.trim();
  const tooLong = text.length > TEXT_LIMIT;
  // Words or images, every image uploaded: one still uploading or refused holds the send until it is sent on or removed.
  const canSend = (trimmed !== '' || images.length > 0) && !tooLong && images.every((image) => image.state === 'ready');

  const addChip = useCallback((chip: Chip) => setChips((all) => (all.some((c) => chipKey(c) === chipKey(chip)) ? all : [...all, chip])), []);
  const removeChip = useCallback((key: string) => setChips((all) => all.filter((c) => chipKey(c) !== key)), []);

  const patchImage = useCallback((id: string, patch: Partial<ImageItem>) => setImages((all) => all.map((image) => (image.id === id ? { ...image, ...patch } : image))), []);
  const attach = useCallback((files: File[]) => {
    const added = files.map((file) => ({ file, item: { id: `i${counter.current++}`, name: file.name, src: URL.createObjectURL(file), state: 'uploading' as const } }));
    setImages((all) => [...all, ...added.map(({ item }) => item)]);
    for (const { file, item } of added) {
      void uploadImage(file).then((done) => {
        if (done.kind === 'ok') return patchImage(item.id, { state: 'ready', fileId: done.data.file_id });
        // Never resent: a refused one says why; one that may have gone through is for the person to attach again.
        patchImage(item.id, { state: 'error', error: done.kind === 'refused' ? done.error.message : IMAGE_UNSURE });
      });
    }
  }, [patchImage]);
  const removeImage = useCallback((id: string) => setImages((all) => all.filter((image) => image.id !== id)), []);
  // Previews of images that were never sent are let go with the composer; a sent image's preview stays for the thread.
  const live = useRef(images);
  useEffect(() => {
    live.current = images;
  });
  useEffect(() => () => live.current.forEach((image) => URL.revokeObjectURL(image.src)), []);

  const send = useCallback(async () => {
    if (writing.current || busy || !canSend) return;
    writing.current = true;
    setError(undefined);
    setNotice(undefined);
    setUnsure(false);
    // The message goes into the thread and the composer empties now (D-160); a refusal puts it all back.
    const sent = { text: trimmed, chips, images };
    setPending({ agent, conversationId: conversationId ?? created.current, text: sent.text, chips: sent.chips.map(chipLabel), images: sent.images.map(({ id, name, src }) => ({ id, name, src })), at: new Date().toISOString(), base: personCount, phase: 'sending' });
    setText('');
    setChips([]);
    setImages([]);
    if (!conversationId) setStarted(true);
    const restore = () => {
      setPending(undefined);
      setStarted(false);
      setText((now) => (now === '' ? sent.text : `${sent.text}\n${now}`));
      setChips((now) => [...sent.chips, ...now.filter((c) => !sent.chips.some((s) => chipKey(s) === chipKey(c)))]);
      setImages((now) => [...sent.images, ...now]);
    };
    const confirmed = (id: string) => {
      created.current = undefined;
      setPending((now) => now && { ...now, conversationId: id, phase: 'waiting' });
      listChanged();
    };
    try {
      let id = conversationId ?? created.current;
      if (!id) {
        const made = await createConversation(agent);
        if (made.kind === 'refused') {
          restore();
          if (made.error.kind === 'unauthenticated') return setSignedOut(true);
          return setError(made.error.message);
        }
        if (made.kind === 'unsure') {
          restore();
          listChanged();
          setUnsure(true);
          return setError(SEND_UNSURE);
        }
        id = made.data.conversation_id;
        created.current = id;
      }
      const body: MessageBody = {
        text: sent.text,
        ...(sent.chips.length > 0 ? { mentions: sent.chips.map(({ kind, id: mentioned }) => ({ kind, id: mentioned })) } : {}),
        ...(sent.images.length > 0 ? { attachments: images.map((image) => ({ file_id: image.fileId! })) } : {}),
      };
      const result = await postMessage(id, body);
      if (result.kind === 'ok') {
        confirmed(id);
        if (conversationId) await reload?.();
        else onSent?.(id);
        return;
      }
      if (result.kind === 'refused') {
        const { kind, message } = result.error;
        restore();
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
        confirmed(id);
        if (!conversationId) onSent?.(id);
        return;
      }
      restore();
      setUnsure(true);
      setError(SEND_UNSURE);
    } finally {
      writing.current = false;
    }
  }, [agent, busy, canSend, chips, conversationId, images, listChanged, onSent, personCount, reload, setPending, trimmed]);

  return { text, setText, chips, addChip, removeChip, images, attach, removeImage, busy, started, canSend, error: tooLong ? TOO_LONG : error, unsure, notice, signedOut, send };
}
