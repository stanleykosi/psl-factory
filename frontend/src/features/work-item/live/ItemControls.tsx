'use client';

// F-87: the controls row under the header: one button per control the API lists for this person (check what happened, resume,
// cancel, pause and continue background work). A control the API does not list is not drawn; the server answers 403 or 409.
// Sending, locking and the words for every outcome are useWorkCommand's.
import { useMemo, useState } from 'react';

import type { ApiError } from '@/api/errors';
import type { LiveWorkItem } from '@/api/types';
import { Button, Callout, Dialog, useToastWhen } from '@/components';
import { workItemCommands } from '@/features/workspace/workItemCommands';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

export function ItemControls({ item, reload, onAccessLost }: { item: LiveWorkItem; reload: () => Promise<LiveWorkItem | null>; onAccessLost: (error: ApiError) => void }) {
  const commands = useMemo(() => workItemCommands(item), [item]);
  const send = useWorkCommand({ item, reload, onAccessLost });
  const [confirming, setConfirming] = useState(false);
  // D-151: what a press did is a toast; only a problem stays on the page as a Callout
  useToastWhen(send.notice?.kind === 'success' ? send.notice.text : null);
  if (commands.length === 0) return null;
  const cancel = commands.find((c) => c.id === 'work.cancel');

  return (
    <>
      <div className="work-controls" role="group" aria-label="Controls">
        {commands.map((command) => {
          const lockedReason = send.lockedReason(command.id);
          const reason = command.disabledReason ?? lockedReason;
          return (
            <div key={command.id} className="work-control">
              <Button
                kind="secondary"
                size="sm"
                disabled={send.busy || reason !== null}
                busy={send.pending === command.id}
                busyLabel="Working…"
                reason={reason}
                onClick={() => (command.id === 'work.cancel' ? setConfirming(true) : void send.run(command))}
              >
                {command.label}
              </Button>
            </div>
          );
        })}
      </div>
      {send.notice?.kind === 'error' && (
        <Callout kind="problem" className="work-next">
          {send.notice.text}
          {send.notice.detail && <> {send.notice.detail}</>}
        </Callout>
      )}
      {confirming && cancel && (
        <Dialog
          title="Cancel this work?"
          actionLabel="Cancel this work"
          cancelLabel="Keep it"
          destructive
          busy={send.pending === cancel.id}
          busyLabel="Working…"
          onCancel={() => setConfirming(false)}
          onAction={() => {
            if (send.busy) return;
            void send.run(cancel).then(() => setConfirming(false));
          }}
        >
          <p>This stops the work. It can’t be started again from here.</p>
        </Dialog>
      )}
    </>
  );
}
