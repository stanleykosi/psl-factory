// A fetch stand-in for the assistant page tests: the real contract mocks (assistant.mjs, start-work.mjs) answer in
// process, so a test exercises the page, the mock's scripts and the drawer together. Nothing leaves the process.
import { File as NodeFile } from 'node:buffer';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { createAssistantMock } from '../mock/assistant.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createStartWorkMock } from '../mock/start-work.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

export const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
export const readFixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', name), 'utf8'));

export type Seen = { method: string; path: string; search: string; headers: Headers; body?: Record<string, unknown>; /** An upload (multipart): the file's name and size as the mock read them. */ file?: { name: string; size: number; type: string } };
type Override = (request: Request, url: URL) => Response | undefined | Promise<Response | undefined>;

/** Starts the in-process mocks for a persona. `seen` is every request the page made, in order. */
export function startBridge(persona = 'pm') {
  const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
  const assistant = createAssistantMock({ openapi });
  const startWork = createStartWorkMock(openapi);
  const me = readFixture(`me.${persona}.json`);
  const seen: Seen[] = [];
  const state: { override?: Override } = {};

  const stub = vi.fn(async (request: Request): Promise<Response> => {
    if (isBellFeed(request)) return bellFeed();
    if (isRoleDashboard(request)) return roleDashboard();
    const url = new URL(request.url);
    const multipart = request.headers.get('content-type')?.startsWith('multipart/form-data') ?? false;
    const raw = request.method === 'POST' && !multipart ? await request.clone().text() : '';
    const bytes = multipart ? Buffer.from(await request.clone().arrayBuffer()) : undefined;
    const entry: Seen = { method: request.method, path: url.pathname, search: url.search, headers: request.headers, body: raw ? JSON.parse(raw) : undefined };
    seen.push(entry);
    const custom = await state.override?.(request, url);
    if (custom) return custom;
    const { pathname } = url;
    if (pathname === '/api/v1/me') return json(200, me);
    // PROPOSAL D-161: the image upload and its read-back.
    if (pathname === '/api/v1/assistant/uploads' && request.method === 'POST') {
      const reply = assistant.upload(bytes ?? Buffer.alloc(0), request.headers.get('content-type'), persona, me.assistant_agents ?? []) as [number, unknown];
      const file = (reply[1] as { name?: string; size?: number; content_type?: string });
      if (reply[0] === 200) entry.file = { name: file.name!, size: file.size!, type: file.content_type! };
      return json(...reply);
    }
    if (pathname.startsWith('/api/v1/assistant/uploads/')) {
      const file = assistant.uploadRead(pathname.split('/')[5], persona) as { type: string; bytes: Buffer } | null;
      return file ? new Response(new Uint8Array(file.bytes), { headers: { 'Content-Type': file.type } }) : json(404, { code: 'not_found', message: 'We could not find that record.' });
    }
    if (pathname.startsWith('/api/v1/assistant/')) {
      const parts = pathname.split('/');
      const operationId =
        parts[4] === 'mentions' ? 'E-MENTION-OPTIONS'
        : parts[4] === 'conversations' && parts.length === 5 ? (request.method === 'POST' ? 'E-CONVERSATION-NEW' : 'E-CONVERSATIONS')
        : parts[6] === 'messages' ? 'E-MESSAGE'
        : 'E-CONVERSATION';
      return json(...(assistant.handle({ operationId, url, raw, persona, agents: me.assistant_agents ?? [] }) as [number, unknown]));
    }
    if (pathname === '/api/v1/work' && request.method === 'POST') {
      const drafted = assistant.draftStart(raw, persona) ?? startWork.handle('E-WORK-START', { url, raw, persona });
      return json(...(drafted as [number, unknown]));
    }
    if (pathname === '/api/v1/lines') return json(...(startWork.handle('E-LINES', { url, raw, persona }) as [number, unknown]));
    if (pathname.startsWith('/api/v1/lines/')) return json(...(startWork.handle('E-LINE-OPTIONS', { url, raw, persona }) as [number, unknown]));
    throw new Error(`unexpected request ${request.method} ${pathname}`);
  });

  return {
    stub,
    seen,
    me,
    assistant,
    /** Answer some requests yourself; return undefined to let the mock answer. */
    override: (fn: Override | undefined) => {
      state.override = fn;
    },
    posts: (path?: RegExp) => seen.filter((s) => s.method === 'POST' && (!path || path.test(s.path))),
    gets: (path: RegExp) => seen.filter((s) => s.method === 'GET' && path.test(s.path)),
  };
}

/**
 * jsdom's FormData and File cannot be read back through a Request, so a test that uploads uses Node's (the browser's
 * are the same kind). Call once per test; returns a maker for files of a given size and type.
 */
export async function useNodeUploads() {
  const NodeFormData = Object.getPrototypeOf(await new Response(new URLSearchParams()).formData()).constructor;
  vi.stubGlobal('FormData', NodeFormData);
  let n = 0;
  Object.assign(URL, { createObjectURL: vi.fn(() => `blob:preview-${++n}`), revokeObjectURL: vi.fn() });
  return (name: string, type = 'image/png', size = 3) => new NodeFile([new Uint8Array(size)], name, { type }) as unknown as File;
}
