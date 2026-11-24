'use client';

// "Make this a follow-up action": one POST /actions/create with the meeting id. The backend links it to the meeting
// itself, so the link operation is never called. An empty deadline is sent as null and read as "No deadline set".
import { useState } from 'react';

import { Button, DateField, Select, TextArea, TextField } from '@/components';

import { ACTION_DESCRIPTION_MAX, ACTION_REASON_MAX, actionBody, actionProblems, defaultActionReference, type ActionDraft, type MeetingOptions } from './model';
import { FailureNotice } from './FailureNotice';
import type { Failure } from './failure';

const DRAWN = ['description', 'ownerId', 'dueAt', 'reason', 'evidence', 'reference'];

export function ActionForm({ options, lessons, count, taken, busy, failure, revision, meetingId, onCreate }: {
  options: MeetingOptions;
  lessons: string;
  count: number;
  taken: readonly string[];
  busy: boolean;
  failure: Failure | null;
  revision: number;
  meetingId: number;
  onCreate: (body: ReturnType<typeof actionBody>) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<ActionDraft>({ description: lessons.slice(0, ACTION_DESCRIPTION_MAX), ownerId: '', dueAt: '', reason: '', evidenceId: '', reference: defaultActionReference(count) });
  const set = (patch: Partial<ActionDraft>) => setDraft((d) => ({ ...d, ...patch }));
  const problems = actionProblems(draft, taken);
  const server = failure?.kind === 'invalid' ? failure.fields : {};
  const disabled = busy || Object.keys(problems).length > 0;
  const firstProblem = Object.values(problems)[0];
  if (!open) {
    return (
      <span>
        <Button kind="secondary" onClick={() => setOpen(true)}>
          Make this a follow-up action
        </Button>
      </span>
    );
  }
  return (
    <form
      className="retro__stack"
      noValidate
      aria-label="Follow-up action"
      onSubmit={(event) => {
        event.preventDefault();
        if (disabled) return;
        void onCreate(actionBody(draft, revision, meetingId)).then((ok) => {
          if (ok) setOpen(false);
        });
      }}
    >
      <TextArea label="What needs doing" value={draft.description} limit={ACTION_DESCRIPTION_MAX} onChange={(e) => set({ description: e.target.value })} rows={3} error={draft.description.trim() === '' || draft.description.length > ACTION_DESCRIPTION_MAX ? problems.description : server.description} />
      <Select label="Owner" optional placeholder="No owner" value={draft.ownerId} onChange={(ownerId) => set({ ownerId })} error={server.ownerId} options={[{ value: '', label: 'No owner' }, ...options.owners.map((o) => ({ value: String(o.id), label: o.label }))]} />
      <DateField time optional label="Deadline" value={draft.dueAt} onChange={(dueAt) => set({ dueAt })} hint="Leave empty for no deadline." error={server.dueAt} />
      <TextArea label="Why it is needed" value={draft.reason} limit={ACTION_REASON_MAX} onChange={(e) => set({ reason: e.target.value })} rows={2} error={draft.reason.length > ACTION_REASON_MAX ? problems.reason : server.reason} />
      <Select label="Supporting file" placeholder={options.proofs.length === 0 ? 'No files to choose' : 'Choose a file'} value={draft.evidenceId || undefined} onChange={(evidenceId) => set({ evidenceId })} options={options.proofs.map((p) => ({ value: String(p.id), label: p.label }))} disabled={options.proofs.length === 0} error={server.evidence} />
      <TextField label="Reference" value={draft.reference} onChange={(e) => set({ reference: e.target.value })} error={server.reference ?? (draft.reference.trim() !== '' ? problems.reference : undefined)} />
      <FailureNotice failure={failure} drawn={DRAWN} />
      <div className="retro__actions">
        <Button type="submit" busy={busy} busyLabel="Creating…" disabled={disabled} reason={busy ? undefined : firstProblem}>
          Create follow-up action
        </Button>
        <Button kind="secondary" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
