// F-85: the per-line adapter (shared; lanes A and B add one adapter per line on this). A work item's `panels[]` entry
// ({ key, url }) names a line panel. The adapter registered for that key reads the panel's own route and turns the readback
// into the Section objects the workspace renderer already draws (Sections.tsx). Commands are DESCRIBED here (route, revision
// tokens, idempotency key), never sent: sending is added by the feature that wires a write.
//   - An adapter never invents text its readback does not carry; unknown or null values stay unknown ("Not recorded"), never 0.
//   - A null token stays null in a command body (unknown, not 0); a line without a key field has no key in its body.
import type { ComponentType } from 'react';

import { call, liveApi } from '@/api/client';
import { newIdempotencyKey } from '@/features/start-work/intake';

import type { Section } from './labels';

/** One entry of GET /work/{id} panels[]. */
export type PanelRef = { key: string; url: string };

/** What every adapter reads from: the loaded live work item. Revisions may be null (unknown). */
export type LineContext = { workId: number; caseId: string; revision: number | null; caseRevision: number | null };

/** What an adapter's `Extra` draws from: the panel's readback and the item context. */
export type LineExtraProps<Readback = unknown> = { readback: Readback; ctx: LineContext };

export type LineAdapter<Readback = unknown> = {
  /** The panels[].key it handles, e.g. 'weekly-report'. */
  key: string;
  /** GET ref.url through liveApi and call(); throws ApiError. */
  read(ref: PanelRef): Promise<Readback>;
  sections(readback: Readback, ctx: LineContext): Section[];
  /** Commands are described, not sent. */
  commands?(readback: Readback, ctx: LineContext): CommandDescriptor[];
  /** Read-only parts the section kinds cannot draw (a link, a control that reads more); drawn under the sections. */
  Extra?: ComponentType<LineExtraProps<Readback>>;
};

export type CommandTokens = {
  expected_revision?: number | null;
  case_revision?: number | null;
  action_revision?: number | null;
  task_revision?: number | null;
  revision?: number | null;
};

/** One typed command on a line's own resource. */
export type CommandDescriptor = {
  /** Stable, '<line>.<action>', e.g. 'weekly-report.correct'. */
  id: string;
  /** Button words. */
  label: string;
  method: 'POST';
  /** The line's own route. */
  url: string;
  tokens: CommandTokens;
  /** The key field the line's body carries, and the uuid made once per attempt; null field: the line has none. */
  idempotency: { field: 'operation' | 'operation_key' | 'key' | null; value: string | null };
  /** `{ action, ...tokens, [key field]: key, ...inputs }`. */
  body(inputs: Record<string, unknown>): Record<string, unknown>;
  /** From the readback (e.g. can_correct false), never invented. */
  disabledReason?: string;
  /** Live commands answer 200, 201 or 202. */
  successStatuses: (200 | 201 | 202)[];
};

type CommandSpec = Pick<CommandDescriptor, 'id' | 'label' | 'url' | 'tokens' | 'disabledReason' | 'successStatuses'> & { keyField?: NonNullable<CommandDescriptor['idempotency']['field']> };

/** Builds a descriptor; the action in the body is the part of the id after the dot. The key is made here, once. */
export function makeCommand(spec: CommandSpec): CommandDescriptor {
  const { keyField, ...rest } = spec;
  const action = spec.id.slice(spec.id.indexOf('.') + 1);
  const idempotency = keyField ? { field: keyField, value: newIdempotencyKey() } : { field: null, value: null };
  return {
    ...rest,
    method: 'POST',
    idempotency,
    body: (inputs) => ({
      action,
      ...spec.tokens,
      ...(idempotency.field ? { [idempotency.field]: idempotency.value } : {}),
      ...inputs,
    }),
  };
}

/** A panel url is read only when it is an API path of this site; anything else is refused before a request. */
export const isPanelUrl = (url: string) => /^\/api\/v1\/[A-Za-z0-9._~/-]+$/.test(url) && !url.includes('..') && !url.includes('//');

/** GET a panel's own route (the one reading helper adapters share). */
export function readPanel<T>(ref: PanelRef): Promise<T> {
  if (!isPanelUrl(ref.url)) return Promise.reject(new Error('Not a panel route.'));
  // The path is not a typed route here: panel urls come from the work item response.
  return call(liveApi.GET(ref.url as never, {} as never)) as Promise<T>;
}

const registry = new Map<string, LineAdapter>();

export function registerLineAdapter(a: LineAdapter): void {
  registry.set(a.key, a);
}

export function adapterFor(key: string): LineAdapter | undefined {
  return registry.get(key);
}
