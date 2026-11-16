'use client';

// Dialog (design/system/project/components/Dialog): a centred box only for confirming something hard to undo.
// The title names the action and the subject; the body says what happens and what does not; the footer has
// Cancel and the action named again. Destructive actions use the Reject button; no typed confirmation. Focus
// starts on Cancel; Esc and Cancel close it.
import { useId, useRef, type ReactNode } from 'react';

import { Button } from './Button';
import { useModal } from './internal';
import { Layer } from './Overlay';

export function Dialog({ title, children, actionLabel, onAction, onCancel, destructive = false, busy = false, busyLabel, cancelLabel = 'Cancel' }: {
  title: string;
  children: ReactNode;
  actionLabel: string;
  onAction: () => void;
  onCancel: () => void;
  destructive?: boolean;
  busy?: boolean;
  busyLabel?: string;
  cancelLabel?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const bodyId = useId();
  const onKeyDown = useModal(panel, onCancel, cancel);
  return (
    <Layer kind="center">
      {/* Esc and the Tab loop are handled for the whole surface. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div ref={panel} className="psl-dialog cmp-panel" role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={bodyId} tabIndex={-1} onKeyDown={onKeyDown}>
        <div className="psl-dialog__head">
          <h2 id={titleId}>{title}</h2>
        </div>
        <div className="psl-dialog__body" id={bodyId}>
          {children}
        </div>
        <div className="psl-dialog__foot">
          <Button ref={cancel} kind="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button kind={destructive ? 'reject' : 'primary'} busy={busy} busyLabel={busyLabel} onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      </div>
    </Layer>
  );
}
