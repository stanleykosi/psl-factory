// F-99: the costing sheet (SCR-27) on the live work item: GET /work/{id}/bid-pricing, plus the project's costing read for the rule
// used. Turns them into the Section objects the workspace renderer draws and describes the writes. Presentation only: who may act
// comes from the response's flags and the server's answer, never from a rule here. A value the response does not give reads
// Unknown or Not recorded, never 0; amounts are shown exactly as given, with the unit the response names.
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import { makeCommand, type CommandDescriptor } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Pricing = Get<'/api/v1/work/{work_id}/bid-pricing'>;
export type Costing = Get<'/api/v1/projects/{case_id}/costing'>;
export type Readback = { pricing: Pricing; costing: Costing | null };
export type Approval = Pricing['approvals'][number];

export const UNKNOWN = 'Unknown';
export const NOT_RECORDED = 'Not recorded';
export const NO_TOKEN = 'We don’t have this costing’s current version yet. Reload and try again.';
export const NOT_CURRENT = 'This costing has been replaced, so it can’t be decided any more.';
export const NO_REVISION = 'There is no costing version to decide yet.';

const TAGS: Record<Approval['status_code'], { label: string; tone: 'person' | 'uncertain' | 'verified' | 'neutral' | 'stopped' }> = {
  approved: { label: 'Approved', tone: 'verified' },
  recorded: { label: 'Recorded', tone: 'verified' },
  pending: { label: 'Waiting', tone: 'person' },
  review_needed: { label: 'Needs review', tone: 'uncertain' },
  returned: { label: 'Returned', tone: 'stopped' },
  rejected: { label: 'Refused', tone: 'stopped' },
  withdrawn: { label: 'Withdrawn', tone: 'neutral' },
};

/** A key such as "pm_share" in plain words, when the response gives no display name. */
export const keyWords = (key: string) => {
  const text = key.replaceAll(/[_-]+/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Figure';
};
/** An amount as given with its unit; null is unknown, never 0. */
export const amountText = (value: string | null, unit: string) => (value === null ? UNKNOWN : unit ? `${value} ${unit}` : value);

/** The approval the sheet waits on now: the first not yet settled, and only when every one before it is. */
export function nextApproval(approvals: Approval[]): Approval | null {
  const i = approvals.findIndex((a) => a.status_code !== 'approved' && a.status_code !== 'recorded');
  if (i === -1) return null;
  const a = approvals[i]!;
  return a.status_code === 'pending' || a.status_code === 'review_needed' ? a : null;
}

export function costingSections({ pricing: p, costing }: Readback): Section[] {
  const out: Section[] = [];
  const held: string[] = [];
  if (!p.current) held.push('This is not the current costing; a newer one has replaced it.');
  if (p.estimate_missing) held.push('The engineering estimate is missing.');
  if (p.security_estimate_missing) held.push('The security estimate is missing.');
  if (held.length > 0) out.push({ key: 'finding', kind: 'text', title: 'Why it is held', items: held.map((text, i) => ({ id: String(i), text })) });
  if (p.costing_note) out.push({ key: 'note', kind: 'text', title: 'About these figures', items: [{ id: 'note', text: p.costing_note }] });

  out.push({
    key: 'inputs',
    kind: 'table',
    title: 'What the costing is built from',
    columns: [
      { key: 'input', label: 'Input', kind: 'text' },
      { key: 'version', label: 'Version', kind: 'text' },
    ],
    items: p.inputs.map((x, i): Item => ({ id: String(i), cells: [{ column: 'input', text: x.label }, { column: 'version', text: x.version === null ? NOT_RECORDED : String(x.version) }] })),
  });

  out.push(
    p.amounts.length > 0
      ? {
          key: 'amounts',
          kind: 'table',
          title: 'Calculated figures',
          columns: [
            { key: 'figure', label: 'Figure', kind: 'text' },
            { key: 'amount', label: 'Amount', kind: 'text' },
          ],
          items: p.amounts.map((a): Item => ({ id: a.key, cells: [{ column: 'figure', text: keyWords(a.key) }, { column: 'amount', text: amountText(a.value, a.unit) }] })),
        }
      : { key: 'amounts', kind: 'text', title: 'Calculated figures', items: [{ id: 'none', text: 'No calculated amounts are available yet.' }] },
  );

  const rules = costing?.rules ?? [];
  if (rules.length > 0) {
    out.push({
      key: 'rule',
      kind: 'facts',
      title: 'Costing rule used',
      items: rules.map((r): Item => ({ id: String(r.id), label: r.reference || 'Rule', value: `Version ${r.version}` })),
    });
  }

  out.push({
    key: 'approvals',
    kind: 'table',
    title: 'Approvals',
    columns: [
      { key: 'who', label: 'Approval', kind: 'text' },
      { key: 'state', label: 'State', kind: 'tag' },
      { key: 'when', label: 'Recorded', kind: 'text' },
    ],
    items: p.approvals.map((a, i): Item => {
      const tag = TAGS[a.status_code] ?? { label: a.status, tone: 'neutral' as const };
      return { id: String(i), cells: [{ column: 'who', text: a.label }, { column: 'state', tag }, { column: 'when', text: a.recorded_at ? formatDayTime(a.recorded_at) : 'Not yet' }] };
    }),
  });

  if (p.adjustment_targets.length > 0) {
    out.push({
      key: 'targets',
      kind: 'facts',
      title: 'What may be adjusted',
      items: p.adjustment_targets.map((t): Item => ({ id: t.key, label: t.label, value: `Up to ${t.max_absolute_value}${p.adjustment_currency ? ` ${p.adjustment_currency}` : ''}` })),
    });
  }
  if (p.finance_pending) {
    const f = p.finance_pending;
    out.push({
      key: 'pending',
      kind: 'text',
      title: 'Price change waiting for a decision',
      items: [{ id: 'pending', text: `${f.target}: from ${f.before} to ${f.after}. Reason: ${f.reason}`, detail: formatDayTime(f.at) }],
    });
  }
  if (p.finance_last_decision) {
    const f = p.finance_last_decision;
    out.push({
      key: 'last',
      kind: 'text',
      title: 'Last price change decision',
      items: [{ id: 'last', text: `${f.status === 'approved' ? 'Approved' : 'Returned'}. Reason: ${f.reason}`, detail: formatDayTime(f.at) }],
    });
  }
  return out;
}

const VERDICTS = [
  ['approve', 'Approve'],
  ['return', 'Return with a note'],
  ['reject', 'Refuse'],
] as const;

/** The writes: the approval on the step waiting now (POST /work/{id}/reviews, kind bid, subject commercial) and the price change
 *  writes of POST /work/{id}/bid-pricing. Each is described always; a reason is set when it can't be sent. */
export function costingCommands({ pricing: p }: Readback, ctx: { workId: number }): CommandDescriptor[] {
  const tokens = { expected_revision: p.expected_revision, case_revision: p.case_revision };
  const missing = tokens.expected_revision == null || tokens.case_revision == null;
  const step = nextApproval(p.approvals);
  const out: CommandDescriptor[] = [];
  for (const [verdict, label] of VERDICTS) {
    out.push(
      makeCommand({
        id: `costing.${verdict}`,
        label,
        url: `/api/v1/work/${ctx.workId}/reviews`,
        tokens,
        action: null,
        fixed: { kind: 'bid', subject: 'commercial', target_id: p.commercial_revision_id, role: step?.role ?? null, verdict, evidence_id: null },
        ...(!p.current ? { disabledReason: NOT_CURRENT } : p.commercial_revision_id === null ? { disabledReason: NO_REVISION } : !step ? { disabledReason: 'No approval is waiting.' } : missing ? { disabledReason: NO_TOKEN } : {}),
        successStatuses: [200],
      }),
    );
  }
  const url = `/api/v1/work/${ctx.workId}/bid-pricing`;
  const price = (id: string, label: string, reason: string | null, action: string | null = null, fixed?: Record<string, unknown>) =>
    makeCommand({ id, label, url, tokens, action, ...(fixed ? { fixed } : {}), ...(reason ? { disabledReason: reason } : missing ? { disabledReason: NO_TOKEN } : {}), successStatuses: [200] });
  out.push(price('costing.adjust', 'Propose the change', p.can_propose && p.adjustment_targets.length > 0 ? null : 'You can’t propose a price change here.'));
  const pending = p.finance_pending;
  const hold = p.can_decide && pending ? null : 'No price change is waiting for you.';
  out.push(price('costing.change-approve', 'Approve the change', hold, 'approve', { proposal_id: pending?.id ?? null }));
  out.push(price('costing.change-return', 'Return the change', hold, 'return', { proposal_id: pending?.id ?? null }));
  return out;
}
