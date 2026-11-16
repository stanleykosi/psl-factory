'use client';

// PhoneActionBar (design/system/project/components/PhoneActionBar, CMP-11): the footer for a decision on a phone.
// Approve full width (54px), Return and Reject side by side (50px), and one line on what approving does not do.
// Submitting: the pressed action is busy and the others wait; disabled always says why.
import { Button } from './Button';

export type Decision = 'approve' | 'return' | 'reject';

export function PhoneActionBar({ approveLabel, returnLabel = 'Return', rejectLabel = 'Reject', onDecide, doesNot, submitting, disabledReason }: {
  /** "Approve v3": names what is approved. */
  approveLabel: string;
  returnLabel?: string;
  rejectLabel?: string;
  onDecide: (decision: Decision) => void;
  /** "Approving does not send the invoice." */
  doesNot: string;
  /** The decision being recorded. */
  submitting?: Decision;
  /** Why nobody can decide here now. */
  disabledReason?: string;
}) {
  const disabled = Boolean(disabledReason) || submitting !== undefined;
  const line = submitting ? 'Recording your decision…' : (disabledReason ?? doesNot);
  return (
    <div className="psl-actionbar">
      <Button size="xl" block busy={submitting === 'approve'} busyLabel="Approving…" disabled={disabled && submitting !== 'approve'} onClick={() => onDecide('approve')}>
        {approveLabel}
      </Button>
      <div className="psl-actionbar__pair">
        <Button kind="secondary" size="lg" busy={submitting === 'return'} busyLabel="Returning…" disabled={disabled && submitting !== 'return'} onClick={() => onDecide('return')}>
          {returnLabel}
        </Button>
        <Button kind="reject" size="lg" busy={submitting === 'reject'} busyLabel="Rejecting…" disabled={disabled && submitting !== 'reject'} onClick={() => onDecide('reject')}>
          {rejectLabel}
        </Button>
      </div>
      <span className="psl-doesnt" role={submitting ? 'status' : undefined}>
        {line}
      </span>
    </div>
  );
}
