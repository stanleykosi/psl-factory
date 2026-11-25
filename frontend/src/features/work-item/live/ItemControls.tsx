'use client';

// F-87: the controls row under the header: one button per control the API lists for this person (check what happened, resume,
// cancel, pause and continue background work). A control the API does not list is not drawn; the server answers 403 or 409.
// Sending, locking and the words for every outcome are useWorkCommand's.
import { useEffect, useMemo, useRef, useState } from 'react';

import type { ApiError } from '@/api/errors';
import type { LiveWorkItem } from '@/api/types';
import { Button, Callout, Dialog, useToastWhen } from '@/components';
import { workItemCommands } from '@/features/workspace/workItemCommands';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { heldMark, readMark, useReleaseMark, writeMark } from './releaseMark';

const RELEASE = 'invoice.release';
const RELEASE_REQUESTED = 'Release requested. The invoice is being sent; this page will update.';
const RELEASE_WAITING = 'Release requested. Waiting for the server.';
const RELEASE_CHECK = 'Check the page before trying again.';

export function ItemControls({ item, reload, onAccessLost }: { item: LiveWorkItem; reload: () => Promise<LiveWorkItem | null>; onAccessLost: (error: ApiError) => void }) {
  const commands = useMemo(() => workItemCommands(item), [item]);
  const send = useWorkCommand({ item, reload, onAccessLost });
  const [confirming, setConfirming] = useState(false);
  const [confirmingRelease, setConfirmingRelease] = useState(false);
  const [lastId, setLastId] = useState<string | null>(null);
  const releasing = useRef(false);
  // the release the page sent, kept across a reload (releaseMark.ts); it holds the button while the server still offers the action
  useReleaseMark(item.id);
  const held = heldMark(item);
  useEffect(() => {
    if (!held && readMark(item.id) !== null) writeMark(item.id, null);
  }, [held, item.id, item.revision, item.actions]);
  // D-151: what a press did is a toast; only a problem stays on the page as a Callout. A release says "requested", never "released".
  const releaseDone = send.notice?.kind === 'success' && lastId === RELEASE;
  useToastWhen(send.notice?.kind === 'success' ? (releaseDone ? RELEASE_REQUESTED : send.notice.text) : null);
  // with nothing listed any more (a release that went through), only a problem the last press had is drawn
  if (commands.length === 0 && send.notice?.kind !== 'error') return null;
  const cancel = commands.find((c) => c.id === 'work.cancel');
  const release = commands.find((c) => c.id === RELEASE);

  // Nothing is sent from here until the person confirms; the mark is written first and cleared only by an answer that says it did not happen.
  const confirmRelease = async () => {
    if (!release || release.disabledReason || item.revision === null || send.busy || releasing.current || heldMark(item)) return;
    releasing.current = true;
    setLastId(RELEASE);
    writeMark(item.id, { revision: item.revision, kind: 'uncertain' });
    try {
      const outcome = await send.run(release);
      if (outcome === 'sent') writeMark(item.id, { revision: item.revision, kind: 'requested' });
      else if (outcome !== 'unknown') writeMark(item.id, null);
    } finally {
      releasing.current = false;
      setConfirmingRelease(false);
    }
  };

  return (
    <>
      {commands.length > 0 && (
        <div className="work-controls" role="group" aria-label="Controls">
          {commands.map((command) => {
            const lockedReason = send.lockedReason(command.id);
            const heldReason = command.id === RELEASE && held ? (held.kind === 'requested' ? RELEASE_WAITING : RELEASE_CHECK) : null;
            const reason = command.disabledReason ?? lockedReason ?? heldReason;
            return (
              <div key={command.id} className="work-control">
                <Button
                  kind={command.id === 'work.cancel' ? 'reject' : 'secondary'}
                  size="sm"
                  disabled={send.busy || reason !== null}
                  busy={send.pending === command.id && lockedReason === null}
                  busyLabel="Working…"
                  reason={reason}
                  onClick={() => (command.id === 'work.cancel' ? setConfirming(true) : command.id === RELEASE ? setConfirmingRelease(true) : void send.run(command))}
                >
                  {command.label}
                </Button>
              </div>
            );
          })}
        </div>
      )}
      {send.notice?.kind === 'error' && (
        <Callout kind="problem" className="work-next">
          {send.notice.text}
          {send.notice.detail && <> {send.notice.detail}</>}
        </Callout>
      )}
      {confirmingRelease && release && (
        <Dialog
          title="Release this invoice?"
          actionLabel="Release invoice"
          cancelLabel="Keep it"
          busy={send.pending === release.id}
          busyLabel="Working…"
          onCancel={() => setConfirmingRelease(false)}
          onAction={() => void confirmRelease()}
        >
          <p>This sends the invoice onward and can’t be undone from here.</p>
        </Dialog>
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
