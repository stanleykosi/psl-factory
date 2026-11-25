'use client';

// F-97: the engagement's own controls (the adapter's `Actions` slot): confirm the project manager, record the details, register,
// and check again. Which of them is offered is the response's `actions`; the choices (managers, roles, sources) are the response's
// own lists. Sending, locking and error words are useWorkCommand's, and the result is told from the re-read, never the 201.
import { useState } from 'react';

import { Button, Callout, Checkbox, Select, TextArea, TextField, useToastWhen, type SelectOption } from '@/components';
import type { CommandDescriptor, LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { proofLabel, type Engagement, type Readback } from './model';

const REASON_LIMIT = 2000;
const VALUE_LIMIT = 120;
const LOCKED = 'Check the page before trying again.';
const DONE: Record<string, string> = {
  'engagement.assign': 'The project manager is recorded.',
  'engagement.details': 'The details are recorded.',
  'engagement.register': 'The engagement is registered.',
  'engagement.reassess': 'The check is recorded.',
};

const options = (values: string[]): SelectOption[] => values.map((v) => ({ value: v, label: v }));

export function EngagementActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const e: Engagement = readback.engagement;
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [last, setLast] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  const [tried, setTried] = useState<string | null>(null);

  const byId = (id: string) => commands.find((c) => c.id === id);
  const field = (name: string, fallback = '') => form[name] ?? fallback;
  const set = (name: string) => (value: string) => setForm({ ...form, [name]: value });
  const proofs: SelectOption[] = e.source_proofs.map((p) => ({ value: String(p.id), label: proofLabel(p) }));
  const managers: SelectOption[] = e.managers.map((m) => ({ value: String(m.id), label: m.name }));
  const locked = commands.some((c) => send.lockedReason(c.id) !== null);

  const press = async (command: CommandDescriptor, inputs: Record<string, unknown>) => {
    setLast(command.id);
    await send.run(command, inputs);
  };
  const button = (c: CommandDescriptor, label: string, onClick: () => void, held: string | null) => {
    const reason = held ?? c.disabledReason ?? send.lockedReason(c.id) ?? (locked ? LOCKED : null);
    return (
      <Button key={c.id} kind="primary" disabled={send.busy || reason !== null} busy={send.pending === c.id && !send.lockedReason(c.id)} busyLabel="Working…" reason={reason} onClick={onClick}>
        {label}
      </Button>
    );
  };
  const missing = (...pairs: [string, boolean][]) => {
    const first = pairs.find(([, ok]) => !ok);
    return first ? first[0] : null;
  };
  const shown = (id: string, ...problems: (string | null)[]) => (tried === id ? (problems.find(Boolean) ?? undefined) : undefined);

  const done = send.notice?.kind === 'success' ? send.notice.text.replace(/^Done\./, DONE[last ?? ''] ?? 'Recorded.') : null;
  useToastWhen(done);

  const assign = byId('engagement.assign');
  const details = byId('engagement.details');
  const register = byId('engagement.register');
  const reassess = byId('engagement.reassess');
  const open = (c: CommandDescriptor | undefined, action: Engagement['actions'][number]) => (c && e.actions.includes(action) ? c : null);

  const a = open(assign, 'assign');
  const d = open(details, 'details');
  const r = open(register, 'register');
  const x = open(reassess, 'reassess');

  return (
    <div className="wr-actions">
      {a && (
        <section className="wr-block" aria-label="Confirm the project manager">
          <h3 className="wr-head">Confirm the project manager</h3>
          <Select label="Project manager" placeholder="Choose a person" options={managers} value={field('pm') || undefined} onChange={set('pm')} error={shown('assign', field('pm') ? null : 'Choose the project manager.')} />
          <Select label="Role" placeholder="Choose a role" options={options(e.assignment_roles)} value={field('assign_role') || undefined} onChange={set('assign_role')} error={shown('assign', field('assign_role') ? null : 'Choose the role.')} />
          <Select label="Source for this choice" placeholder="Choose a source" options={proofs} value={field('assign_proof') || undefined} onChange={set('assign_proof')} error={shown('assign', field('assign_proof') ? null : 'Choose a source.')} />
          <div className="wr-buttons">
            {button(a, a.label, () => {
              setTried('assign');
              if (!field('pm') || !field('assign_role') || !field('assign_proof')) return;
              void press(a, { pm_id: Number(field('pm')), role: field('assign_role'), evidence_id: Number(field('assign_proof')) });
            }, null)}
          </div>
        </section>
      )}
      {d && (
        <section className="wr-block" aria-label="Record the details">
          <h3 className="wr-head">Record the plan and contact details</h3>
          <TextField label="Reference" value={field('reference', e.capture?.reference ?? '')} maxLength={VALUE_LIMIT} onChange={(ev) => set('reference')(ev.target.value)} error={shown('details', field('reference', e.capture?.reference ?? '').trim() ? null : 'Add the reference.')} />
          <Select label="Source you checked" placeholder="Choose a source" options={proofs} value={field('details_proof') || undefined} onChange={set('details_proof')} error={shown('details', field('details_proof') ? null : 'Choose the source you checked.')} />
          <Select label="Plan" placeholder="Choose the plan" options={proofs} value={field('plan') || undefined} onChange={set('plan')} error={shown('details', field('plan') ? null : 'Choose the plan.')} />
          <TextField label="Planned start" optional type="date" value={field('start')} onChange={(ev) => set('start')(ev.target.value)} />
          <p className="wr-line">The client contact can’t be chosen here yet, so none is recorded with these details.</p>
          <Checkbox label="I checked the captured details and the source" checked={checked} onChange={(ev) => setChecked(ev.target.checked)} error={shown('details', checked ? null : 'Tick to confirm you checked them.')} />
          <div className="wr-buttons">
            {button(d, d.label, () => {
              setTried('details');
              const reference = field('reference', e.capture?.reference ?? '').trim();
              if (!reference || !field('details_proof') || !field('plan') || !checked || !e.capture) return;
              void press(d, { capture_id: e.capture.id, reference, plan_id: Number(field('plan')), checked: true, planned_start: field('start') || null, contact_id: null, evidence_id: Number(field('details_proof')) });
            }, missing(['There is no captured request to attach the details to.', e.capture !== null]))}
          </div>
        </section>
      )}
      {r && (
        <section className="wr-block" aria-label="Register the engagement">
          <h3 className="wr-head">Register the engagement</h3>
          <TextField label="Official project identifier" hint="As the registry writes it" value={field('value')} maxLength={VALUE_LIMIT} onChange={(ev) => set('value')(ev.target.value)} error={shown('register', field('value').trim() ? null : 'Add the identifier.')} />
          <Select label="Role" placeholder="Choose a role" options={options(e.registration_roles)} value={field('reg_role') || undefined} onChange={set('reg_role')} error={shown('register', field('reg_role') ? null : 'Choose the role.')} />
          <Select label="Source for the registration" placeholder="Choose a source" options={proofs} value={field('reg_proof') || undefined} onChange={set('reg_proof')} error={shown('register', field('reg_proof') ? null : 'Choose a source.')} />
          <div className="wr-buttons">
            {button(r, r.label, () => {
              setTried('register');
              if (!e.details || !field('value').trim() || !field('reg_role') || !field('reg_proof')) return;
              void press(r, { role: field('reg_role'), value: field('value').trim(), plan_id: e.details.plan_id, details_id: e.details.id, evidence_id: Number(field('reg_proof')) });
            }, missing(['Record the details first.', e.details !== null]))}
          </div>
        </section>
      )}
      {x && (
        <section className="wr-block" aria-label="Check again">
          <h3 className="wr-head">Check again after a change</h3>
          <TextArea label="Why" limit={REASON_LIMIT} value={field('reason')} error={shown('reassess', field('reason').trim() ? null : 'Say why you are checking again.')} onChange={(ev) => set('reason')(ev.target.value)} />
          <div className="wr-buttons">
            {button(x, x.label, () => {
              setTried('reassess');
              if (!field('reason').trim()) return;
              void press(x, { capture_id: e.capture?.id ?? null, reason: field('reason') });
            }, null)}
          </div>
        </section>
      )}
      {send.notice?.kind === 'error' && (
        <Callout kind="problem">
          {send.notice.text}
          {send.notice.detail && <> {send.notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
