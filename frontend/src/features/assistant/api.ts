// The five assistant operations. Reads throw ApiError (client.ts `call`); the two writes return an outcome instead, so a
// definitive answer (the server read the request) and an uncertain one (network, 5xx) are never confused: an uncertain
// write is never resent by this code (Conflicts 17). Bodies carry only the typed fields.
import { api, call } from '@/api/client';
import { ApiError, errorFromResponse } from '@/api/errors';
import type { PageSize } from '@/components';

import type { AgentName, Attachment, MentionOptions, MessageBody, MessageResult, NewConversation } from './types';

export const fetchConversations = (limit: PageSize, cursor?: string) =>
  call(api.GET('/api/v1/assistant/conversations', { params: { query: { limit, cursor } } }));

export const fetchConversation = (id: string) =>
  call(api.GET('/api/v1/assistant/conversations/{conversation_id}', { params: { path: { conversation_id: id } } }));

export const fetchMentions = (q: string, signal?: AbortSignal): Promise<MentionOptions> =>
  call(api.GET('/api/v1/assistant/mentions', { params: { query: { q } }, signal }));

export type WriteOutcome<T> =
  | { kind: 'ok'; data: T }
  /** The server answered no (401, 403, 404, 409, 422): nothing was written. */
  | { kind: 'refused'; error: ApiError }
  /** Network failure or 5xx: it may or may not have been written. */
  | { kind: 'unsure' };

async function write<T>(send: () => Promise<{ response: Response; data?: unknown; error?: unknown }>): Promise<WriteOutcome<T>> {
  try {
    const { response, data, error } = await send();
    if (response.ok) return { kind: 'ok', data: data as T };
    if (response.status >= 500) return { kind: 'unsure' };
    return { kind: 'refused', error: errorFromResponse(response.status, error) };
  } catch (thrown) {
    // Thrown before sending (no CSRF token) is a definitive "nothing sent"; anything else may have reached the server.
    if (thrown instanceof ApiError && thrown.kind === 'unauthenticated') return { kind: 'refused', error: thrown };
    return { kind: 'unsure' };
  }
}

export const createConversation = (agent: AgentName) =>
  write<NewConversation>(() => api.POST('/api/v1/assistant/conversations', { body: { agent } }));

export const postMessage = (id: string, body: MessageBody) =>
  write<MessageResult>(() => api.POST('/api/v1/assistant/conversations/{conversation_id}/messages', { params: { path: { conversation_id: id } }, body }));

/** PROPOSAL D-161: the image's address for a thumbnail or a new tab (GET, same session). */
export const uploadHref = (fileId: string) => `/api/v1/assistant/uploads/${encodeURIComponent(fileId)}`;

type UntypedPost = { POST: (path: string, init: { body: FormData; bodySerializer: (body: FormData) => FormData }) => Promise<{ response: Response; data?: unknown; error?: unknown }> };

/** PROPOSAL D-161: one image, multipart, to the proposed endpoint (not in the v7 contract). Like the two writes it is never resent. */
export const uploadImage = (file: File) =>
  write<Attachment>(() => {
    const form = new FormData();
    form.append('file', file);
    return (api as unknown as UntypedPost).POST('/api/v1/assistant/uploads', { body: form, bodySerializer: (body) => body });
  });
