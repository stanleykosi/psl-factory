// F-85: the per-line adapter (shared; lanes A and B add one adapter per line on this). A work item's `panels[]` entry
// ({ key, url }) names a line panel. The adapter registered for that key reads the panel's own route and turns the readback
// into the Section objects the workspace renderer already draws (Sections.tsx). Commands are DESCRIBED here (route, revision
// tokens, idempotency key), never sent: they are sent by `useWorkCommand` (one sender for every write: press lock, uncertain
// lock, CSRF handling, re-read; JSON or multipart).
//   - An adapter never invents text its readback does not carry; unknown or null values stay unknown ("Not recorded"), never 0.
//   - A null token stays null in a command body (unknown, not 0); a line without a key field has no key in its body.
//
// THE WRITE-FORM SLOT (F-87). A line draws its write controls by registering an `Actions` component. The work item page renders
// it under that panel's sections, inside the panel's own error boundary, with `{ readback, ctx, commands, reload }`:
// `commands` is what `adapter.commands(readback, ctx)` describes, `ctx.state` is the work item's served state (read only: offer a
// control only in the states the server reports, and let the server answer 409/422), and `reload()` re-reads the panel and the
// work item and resolves to the new item (null when the read failed). A line without `Actions` draws exactly as before.
//
//   function Actions({ commands, reload, ctx, onAccessLost }: LineActionsProps<Readback>) {
//     const send = useWorkCommand({ item: ctx, reload, onAccessLost });
//     const restart = commands.find((c) => c.id === 'ledger.restart');
//     return restart && <Button disabled={send.busy || !!restart.disabledReason} onClick={() => void send.run(restart, { note })}>{restart.label}</Button>;
//     // ...and draw send.notice (a Callout) and send.lockedReason(restart.id) beside the button.
//   }
//   registerLineAdapter({ key: 'ledger', read, sections, commands, Actions });
//
// A command whose body carries files says `contentType: 'multipart/form-data'` (see makeCommand); `useWorkCommand` then sends
// FormData built from `body(inputs)`: a Blob/File value is a file part, a null or undefined value is left out, other values
// are sent as text and an object as JSON text.
import type { ComponentType } from 'react';

import { call, liveApi } from '@/api/client';
import type { ApiError } from '@/api/errors';
import type { LiveWorkItem } from '@/api/types';
import { newIdempotencyKey } from '@/features/start-work/intake';

import type { Section } from './labels';

/** One entry of GET /work/{id} panels[]. */
export type PanelRef = { key: string; url: string };

/** What every adapter reads from: the loaded live work item. Revisions may be null (unknown); `state` is the item's served state. */
export type LineContext = { workId: number; caseId: string; revision: number | null; caseRevision: number | null; state?: LiveWorkItem['state'] };

/** What a line's `Actions` receives. `reload()` re-reads the panel and the work item; it resolves to the new item, or null when the read failed. */
export type LineActionsProps<Readback = unknown> = {
  readback: Readback;
  ctx: LineContext;
  commands: CommandDescriptor[];
  reload: () => Promise<LiveWorkItem | null>;
  /** Pass to useWorkCommand: a write answered 401 or 404, so the page shows the signed-out or unavailable state. */
  onAccessLost: (error: ApiError) => void;
};

export type LineAdapter<Readback = unknown> = {
  /** The panels[].key it handles, e.g. 'weekly-report'. */
  key: string;
  /** GET ref.url through liveApi and call(); throws ApiError. `ctx` is the loaded item (an adapter that does not need it ignores it). */
  read(ref: PanelRef, ctx?: LineContext): Promise<Readback>;
  sections(readback: Readback, ctx: LineContext): Section[];
  /** Commands are described, not sent. */
  commands?(readback: Readback, ctx: LineContext): CommandDescriptor[];
  /** The line's write controls, drawn under its sections (see the slot note above). */
  Actions?: ComponentType<LineActionsProps<Readback>>;
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
  /** `{ ...inputs, action, ...tokens, [key field]: key }`: the descriptor's own fields win over inputs. */
  body(inputs: Record<string, unknown>): Record<string, unknown>;
  /** From the readback (e.g. can_correct false), never invented. */
  disabledReason?: string;
  /** The body's encoding; JSON when absent. */
  contentType?: 'application/json' | 'multipart/form-data';
  /** Live commands answer 200, 201 or 202. */
  successStatuses: (200 | 201 | 202)[];
};

type CommandSpec = Pick<CommandDescriptor, 'id' | 'label' | 'url' | 'tokens' | 'disabledReason' | 'successStatuses' | 'contentType'> & {
  keyField?: NonNullable<CommandDescriptor['idempotency']['field']>;
  /** The body's `action`; default the part of the id after the dot, `null` for a body that has none. */
  action?: string | null;
  /** Fixed body members merged in (e.g. `kind: 'document'`); the tokens still win. */
  fixed?: Record<string, unknown>;
};

/** Builds a descriptor; the action in the body is the part of the id after the dot. The key is made here, once. */
export function makeCommand(spec: CommandSpec): CommandDescriptor {
  const { keyField, action: given, fixed, ...rest } = spec;
  const action = given === undefined ? spec.id.slice(spec.id.indexOf('.') + 1) : given;
  const idempotency = keyField ? { field: keyField, value: newIdempotencyKey() } : { field: null, value: null };
  return {
    ...rest,
    method: 'POST',
    idempotency,
    body: (inputs) => {
      const body = {
        ...inputs,
        ...fixed,
        ...(action === null ? {} : { action }),
        ...spec.tokens,
        ...(idempotency.field ? { [idempotency.field]: idempotency.value } : {}),
      };
      // a body with no action has none, whatever the inputs say
      if (action === null) delete body.action;
      return body;
    },
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
