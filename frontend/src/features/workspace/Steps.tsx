'use client';

// Step controls (PROPOSAL D-LINE-WORKSPACE): only the steps in `workspace.steps`, only with a numeric
// `workspace.revision`, placed by `applies_to`. A step with `task_id` is a decision: a link to the F-16 decision
// page, never a write from here. An unavailable step shows its reason and sends nothing.
import Link from 'next/link';
import { useId, type ReactNode, type Ref } from 'react';

import type { WorkItem } from '@/api/types';
import { Button, buttonClass } from '@/components';
import { cannotActCopy } from '@/features/decide/DecideStates';

import type { Step } from './labels';
import { stepKind } from './StepForm';
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

// Frontend-owned neutral sentence (F-32): a decision step whose task the response does not carry.
const NO_TASK = 'This decision isn’t open to you here.';

type ControlProps = {
  workId: string;
  step: Step;
  /** The item's tasks: a decision step is a link only when its task is here with `you_can_act` (F-32). */
  tasks?: WorkItem['tasks'];
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

export function StepControl({ workId, step, tasks, off, pending, none, onPress, controlRef, describedBy, label }: ControlProps) {
  const reasonId = useId();
  const text = pending ? `${step.label}…` : (label ?? step.label);
  if (step.disabled_reason) {
    return (
      <span className="ws-control">
        <Button kind={stepKind(step)} aria-disabled="true" aria-describedby={reasonId} ref={controlRef}>
          {step.label}
        </Button>
        <span id={reasonId} className="psl-reason">
          {step.disabled_reason}
        </span>
      </span>
    );
  }
  if (step.task_id) {
    // F-32: authority is the task's `you_can_act` as the backend returned it; a missing task is unavailable too.
    const task = tasks?.find((t) => t.id === step.task_id);
    if (!task?.you_can_act) {
      // F-40: a task with no decision block (a handover reply) still says whose it is when the reason is the role
      const named = task?.decision || (task?.cannot_act_reason === 'not_your_role' && task.required_role);
      const reason = task && named ? cannotActCopy(task.cannot_act_reason, task as Parameters<typeof cannotActCopy>[1]).heading : NO_TASK;
      return (
        <span className="ws-control">
          <Button kind={stepKind(step)} aria-disabled="true" aria-describedby={[describedBy, reasonId].filter(Boolean).join(' ')} ref={controlRef}>
            {step.label}
          </Button>
          <span id={reasonId} className="psl-reason">
            {reason}
          </span>
        </span>
      );
    }
    // INV-RESEND: a decision link follows the page lock. While a write is in flight, after an uncertain send or after
    // a failed refresh it is an unavailable control with no href, so nothing can be approved again from here.
    if (off) {
      return (
        <span className="ws-control">
          <Button kind={stepKind(step)} aria-disabled="true" aria-describedby={describedBy} ref={controlRef}>
            {step.label}
          </Button>
        </span>
      );
    }
    // A decision is taken on the decision page (claim and decide there); this sends nothing.
    const href = `/work/${encodeURIComponent(workId)}/decide?task=${encodeURIComponent(step.task_id)}`;
    return (
      <span className="ws-control">
        <Link className={buttonClass(stepKind(step))} href={href} aria-describedby={[describedBy, step.claim_required && reasonId].filter(Boolean).join(' ') || undefined}>
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
    <Button
      ref={controlRef}
      kind={stepKind(step)}
      busy={pending}
      busyLabel={text}
      aria-disabled={inert || undefined}
      aria-describedby={describedBy}
      onClick={() => {
        if (!inert) onPress();
      }}
    >
      {text}
    </Button>
  );
}

/** The workspace-scope row: each step's consequence above the buttons, as the boards' decide panels draw it. */
export function StepRow({ steps, children, hint }: { steps: Step[]; children: (step: Step, describedBy: string | undefined) => ReactNode; hint?: string }) {
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
      {hint && <p className="psl-reason ws-hint">{hint}</p>}
    </div>
  );
}
