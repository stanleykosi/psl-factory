// A fetch stand-in for the assistant page tests: the real contract mocks (assistant.mjs, start-work.mjs) answer in
// process, so a test exercises the page, the mock's scripts and the drawer together. Nothing leaves the process.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { createAssistantMock } from '../mock/assistant.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createStartWorkMock } from '../mock/start-work.mjs';
import { bellFeed, isBellFeed } from './bell-feed';

export const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
export const readFixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', name), 'utf8'));

export type Seen = { method: string; path: string; search: string; headers: Headers; body?: Record<string, unknown> };
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
    const url = new URL(request.url);
    const raw = request.method === 'POST' ? await request.clone().text() : '';
    seen.push({ method: request.method, path: url.pathname, search: url.search, headers: request.headers, body: raw ? JSON.parse(raw) : undefined });
    const custom = await state.override?.(request, url);
    if (custom) return custom;
    const { pathname } = url;
    if (pathname === '/api/v1/me') return json(200, me);
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
