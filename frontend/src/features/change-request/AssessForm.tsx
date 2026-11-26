'use client';

// F-112: "Record an assessment" for one team the read lists in `assessors`. The team's assessment is recorded on its behalf (the teams do
// not sign in). The four yes/no questions have no answer ahead: "Not known" is a choice and is sent as null, never as No. The proof is
// chosen from the case's recorded proofs; no file is uploaded here. One press is one request (ChangeActions owns the send).
import { useState } from 'react';

import { Button, Disclosure, Select, TextArea, TextField, type SelectOption } from '@/components';
import type { CommandDescriptor } from '@/features/workspace/adapter';

import { assessHeld, assessInputs, EFFORT_LIMIT, emptyOutputs, NOTE_LIMIT, OUTPUT_KEYS, proofLabel, TEXT, type AssessChoice, type Change, type Choice, type Team } from './changeModel';

const YES_NO: SelectOption[] = [
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
  { value: 'unknown', label: 'Not known' },
];
const QUESTIONS = [
  ['cost', 'Changes the cost'],
  ['timeline', 'Changes the timeline'],
  ['clientFacing', 'The client will see it'],
  ['production', 'Affects production'],
] as const;
const OUTPUT_LABELS: Record<(typeof OUTPUT_KEYS)[number], string> = {
  discipline: 'Discipline note',
  timeline: 'Timeline note',
  cost_resource: 'Cost and resource note',
  risk: 'Risk note',
  dependency: 'Dependency note',
};

const blank = (team: Team): AssessChoice => ({ team, note: '', effort: '', cost: undefined, timeline: undefined, clientFacing: undefined, production: undefined, scope: '', outputs: emptyOutputs(), evidence: undefined });

type Props = {
  team: Team;
  change: Change;
  command: CommandDescriptor | undefined;
  /** Why no write may be sent now (a lock, a read in progress, a write running), or null. */
  blocked: string | null;
  busy: boolean;
  pending: boolean;
  /** Sends once; resolves true when the write was accepted. */
  send: (inputs: Record<string, unknown>) => Promise<boolean>;
};

export function AssessForm({ team, change, command, blocked, busy, pending, send }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<AssessChoice>(() => blank(team));
  if (!command) return null;
  const set = (patch: Partial<AssessChoice>) => setDraft((d) => ({ ...d, ...patch }));
  const proofs: SelectOption[] = change.evidence.map((p) => ({ value: String(p.id), label: proofLabel(p) }));
  const own = assessHeld(change, draft);
  const reason = command.disabledReason ?? blocked ?? own;

  if (!open) {
    return (
      <section className="wr-block" aria-label={`${team} assessment`}>
        <h3 className="wr-head">{team}</h3>
        <div className="wr-buttons">
          <Button kind="secondary" disabled={command.disabledReason !== undefined} reason={command.disabledReason ?? null} onClick={() => setOpen(true)}>
            Record an assessment
          </Button>
        </div>
      </section>
    );
  }
  return (
    <section className="wr-block" aria-label={`${team} assessment`}>
      <h3 className="wr-head">Record an assessment · {team}</h3>
      <p className="wr-line">{team} doesn’t sign in. You record its assessment with proof.</p>
      <TextArea label="Assessment" limit={NOTE_LIMIT} value={draft.note} onChange={(e) => set({ note: e.target.value })} />
      <TextField label="Effort in person-days" optional maxLength={EFFORT_LIMIT} value={draft.effort} onChange={(e) => set({ effort: e.target.value })} />
      {QUESTIONS.map(([key, label]) => (
        <Select key={key} label={label} placeholder="Choose" options={YES_NO} value={draft[key] as Choice} onChange={(v) => set({ [key]: v } as Partial<AssessChoice>)} />
      ))}
      {proofs.length === 0 ? <p className="wr-line">{TEXT.noProof}</p> : <Select label="Proof" placeholder="Choose the proof" options={proofs} value={draft.evidence} onChange={(evidence) => set({ evidence })} />}
      <Disclosure summary="More detail (optional)">
        <div className="wr-block">
          <TextArea label="Scope items, one per line" optional limit={NOTE_LIMIT} value={draft.scope} onChange={(e) => set({ scope: e.target.value })} />
          {OUTPUT_KEYS.map((k) => (
            <TextArea key={k} label={OUTPUT_LABELS[k]} optional limit={NOTE_LIMIT} value={draft.outputs[k]} onChange={(e) => set({ outputs: { ...draft.outputs, [k]: e.target.value } })} />
          ))}
        </div>
      </Disclosure>
      <div className="wr-buttons">
        <Button
          disabled={busy || reason !== null}
          busy={pending}
          busyLabel="Working…"
          reason={reason}
          onClick={() => {
            if (reason !== null) return;
            void send(assessInputs(draft)).then((accepted) => {
              if (accepted) {
                setOpen(false);
                setDraft(blank(team));
              }
            });
          }}
        >
          Record assessment
        </Button>
        <Button kind="secondary" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </section>
  );
}

