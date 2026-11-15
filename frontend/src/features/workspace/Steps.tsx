'use client';

// Step controls (PROPOSAL D-LINE-WORKSPACE): only the steps in `workspace.steps`, only with a numeric
// `workspace.revision`, placed by `applies_to`. A step with `task_id` is a decision: a link to the F-16 decision
// page, never a write from here. An unavailable step shows its reason and sends nothing.
import Link from 'next/link';
import { useId, type ReactNode, type Ref } from 'react';

import type { Step } from './labels';
import { stepClass } from './StepForm';
import { STEP_TEXT } from './useWorkspaceStep';

/** "Approving sends this exact version to Lagoon Health." plus "This sends to the client." when the sentence doesn't already say it sends. */
export function Consequence({ step, id }: { step: Step; id?: string }) {
  const says = step.consequence !== undefined && /\bsend/i.test(step.consequence);
  const extra = step.sends && !says ? STEP_TEXT.sends : undefined;
  if (!step.consequence && !extra) return null;
  return (
    <p id={id} className="ws-consequence">
      {[step.consequence, extra].filter(Boolean).join(' ')}
    </p>
  );
}

type ControlProps = {
  workId: string;
  step: Step;
  /** Another write is in flight, the page is locked or the refresh failed: pressing does nothing. */
  off: boolean;
  pending: boolean;
  /** `items` steps: nothing checked yet. */
  none?: boolean;
  onPress: () => void;
  controlRef?: Ref<HTMLButtonElement>;
  describedBy?: string;
  label?: string;
};

export function StepControl({ workId, step, off, pending, none, onPress, controlRef, describedBy, label }: ControlProps) {
  const reasonId = useId();
  const text = pending ? `${step.label}…` : (label ?? step.label);
  if (step.disabled_reason) {
    return (
      <span className="ws-control">
        <button type="button" className={stepClass(step)} aria-disabled="true" aria-describedby={reasonId} ref={controlRef}>
          {step.label}
        </button>
        <span id={reasonId} className="psl-reason">
          {step.disabled_reason}
        </span>
      </span>
    );
  }
  if (step.task_id) {
    // A decision is taken on the decision page (claim and decide there); this sends nothing.
    const href = `/work/${encodeURIComponent(workId)}/decide?task=${encodeURIComponent(step.task_id)}`;
    return (
      <span className="ws-control">
        <Link className={stepClass(step)} href={href} aria-describedby={[describedBy, step.claim_required && reasonId].filter(Boolean).join(' ') || undefined}>
          {step.label}
        </Link>
        {step.claim_required && (
          <span id={reasonId} className="psl-reason">
            {STEP_TEXT.claim}
          </span>
        )}
      </span>
    );
  }
  const inert = off || pending || none === true;
  return (
    <button
      type="button"
      ref={controlRef}
      className={stepClass(step)}
      aria-disabled={inert || undefined}
      aria-describedby={describedBy}
      onClick={() => {
        if (!inert) onPress();
      }}
    >
      {text}
    </button>
  );
}

/** The workspace-scope row: each step's consequence above the buttons, as the boards' decide panels draw it. */
export function StepRow({ steps, children }: { steps: Step[]; children: (step: Step, describedBy: string | undefined) => ReactNode }) {
  const base = useId();
  if (steps.length === 0) return null;
  return (
    <div className="ws-steps">
      {steps.map((step, i) => (
        <Consequence key={step.key} step={step} id={`${base}-${i}`} />
      ))}
      <div className="ws-steps__buttons">
        {steps.map((step, i) => {
          const has = Boolean(step.consequence) || step.sends === true;
          return <span key={step.key}>{children(step, has ? `${base}-${i}` : undefined)}</span>;
        })}
      </div>
    </div>
  );
}
