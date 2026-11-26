'use client';

// F-114: one press button for the go-live forms. It is disabled while any write runs or is locked, says why beside itself, and sends
// nothing itself: the caller's `onPress` calls `send.run` once. Sending, the press lock and error words are useWorkCommand's.
import { Button } from '@/components';
import type { CommandDescriptor } from '@/features/workspace/adapter';
import type { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { IDS } from './goLiveModel';

export type Send = ReturnType<typeof useWorkCommand>;
const LOCKED = 'Check the page before trying again.';

/** The reason this control may not be pressed, or null: the descriptor's own, a lock on this or any go-live write, then the form's. */
export const pressReason = (send: Send, command: CommandDescriptor, held: string | null) =>
  command.disabledReason ?? send.lockedReason(command.id) ?? (IDS.some((id) => send.lockedReason(id) !== null) ? LOCKED : null) ?? held;

export function Press({ send, command, label, held, onPress, kind = 'primary' }: { send: Send; command: CommandDescriptor; label: string; held: string | null; onPress: () => void; kind?: 'primary' | 'secondary' }) {
  const reason = pressReason(send, command, held);
  return (
    <Button kind={kind} disabled={send.busy || reason !== null} busy={send.pending === command.id} busyLabel="Working…" reason={reason} onClick={onPress}>
      {label}
    </Button>
  );
}
