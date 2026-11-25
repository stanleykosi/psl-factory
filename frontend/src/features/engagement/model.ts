// F-97: the engagement panel (SCR-41) on the live work item. Turns GET /work/{id}/engagement and the project's engagement-intake
// into the Section objects the workspace renderer draws, and describes the four writes. Presentation only: which step is open comes
// from the response's `actions`, never from a rule here. A value the response does not give reads Unknown or Not recorded, never 0.
import type { paths } from '@/api/live-schema';
import { makeCommand, type CommandDescriptor } from '@/features/workspace/adapter';
import type { Cell, Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Engagement = Get<'/api/v1/work/{work_id}/engagement'>;
export type EngagementIntake = Get<'/api/v1/projects/{case_id}/engagement-intake'>;
export type Readback = { engagement: Engagement; intake: EngagementIntake | null };
export type Proof = Engagement['source_proofs'][number];

export const NOT_RECORDED = 'Not recorded';
export const NO_TOKEN = 'We don’t have this engagement’s current version yet. Reload and try again.';

const ROUTES: Record<string, string> = {
  A: 'Route A · converted from a won bid',
  B: 'Route B · direct engagement, backed by evidence on the same case',
  C: 'Route C · needs Product intake evidence',
};
const PARTS: Record<string, string> = { scope: 'Scope', price: 'Price', plan: 'Plan' };
const KINDS: Record<string, string> = { engagement_source: 'Engagement source', product_input: 'Product input', rfp_outcome: 'RFP outcome' };

/** A kind code in plain words ("engagement_source" reads Engagement source). */
export const kindWords = (kind: string) => KINDS[kind] ?? (kind ? kind.charAt(0).toUpperCase() + kind.slice(1).replaceAll('_', ' ') : 'Record');
export const proofLabel = (p: Proof) => `${kindWords(p.kind)}, version ${p.version} (record ${p.id})`;

const text = (column: string, value: string | null | undefined): Cell => ({ column, text: value ?? '' });
const CASE_URL = /^\/api\/v1\/projects\/([0-9a-f-]{36})$/;

export function engagementSections({ engagement: e, intake }: Readback): Section[] {
  const out: Section[] = [];
  if (e.capture) {
    const won = e.capture.rfp_disposition_id !== null;
    out.push({
      key: 'route',
      kind: 'facts',
      title: 'Where it came from',
      items: [
        { id: 'route', label: 'Route', value: ROUTES[e.capture.route] ?? `Route ${e.capture.route}` },
        { id: 'reference', label: 'Reference', value: e.capture.reference || NOT_RECORDED },
        { id: 'won', label: 'Won bid decision', value: won ? 'Recorded' : e.capture.route === 'A' ? NOT_RECORDED : 'Not from a bid' },
      ],
    });
  } else {
    out.push({ key: 'route', kind: 'text', title: 'Where it came from', items: [{ id: 'none', text: 'No original request has been captured yet.' }] });
  }
  if (e.finding) out.push({ key: 'finding', kind: 'text', title: 'Why it is held', items: [{ id: 'finding', text: e.finding }] });

  const open = (action: Engagement['actions'][number], done: boolean): Item['status'] => (done ? 'done' : e.actions.includes(action) ? 'next' : 'not_yet');
  out.push({
    key: 'steps',
    kind: 'checklist',
    title: 'Engagement steps',
    items: [
      { id: 'assign', label: 'Confirm the project manager', status: open('assign', e.assignment_id !== null) },
      { id: 'details', label: 'Record the plan and contact details', status: open('details', e.details !== null) },
      { id: 'register', label: 'Register the engagement', status: open('register', e.registration_id !== null) },
    ],
  });

  if (e.details) {
    out.push({
      key: 'details',
      kind: 'facts',
      title: 'Details recorded',
      items: [
        { id: 'reference', label: 'Reference', value: e.details.reference },
        { id: 'start', label: 'Planned start', value: e.details.planned_start ?? NOT_RECORDED },
        { id: 'contact', label: 'Client contact', value: e.details.contact_id === null ? NOT_RECORDED : 'Recorded' },
      ],
    });
  }

  if (e.packet_sources.length > 0) {
    out.push({
      key: 'packet',
      kind: 'table',
      title: 'What was agreed',
      columns: [
        { key: 'part', label: 'Part', kind: 'text' },
        { key: 'source', label: 'Source', kind: 'text' },
        { key: 'state', label: 'On file', kind: 'tag' },
      ],
      items: e.packet_sources.map(
        (s): Item => ({
          id: s.key,
          cells: [text('part', PARTS[s.key] ?? s.key), text('source', s.label), { column: 'state', tag: s.evidence_id === null ? { label: 'Not on file', tone: 'neutral' } : { label: 'On file', tone: 'verified' } }],
        }),
      ),
    });
  }

  const caseId = CASE_URL.exec(e.project.url)?.[1];
  const links: Item[] = [];
  if (caseId) links.push({ id: 'project', cells: [text('what', 'Project'), { column: 'link', link: { label: e.project.label, case_id: caseId } }] });
  if (e.planning_work_id !== null) {
    links.push({ id: 'planning', cells: [text('what', 'Planning'), { column: 'link', link: { label: e.planning?.label ?? 'Project planning', work_id: String(e.planning_work_id) } }] });
  }
  if (links.length > 0) {
    out.push({
      key: 'links',
      kind: 'table',
      title: 'What registering created',
      columns: [
        { key: 'what', label: 'Record', kind: 'text' },
        { key: 'link', label: 'Open', kind: 'reference' },
      ],
      items: links,
    });
  }
  out.push({
    key: 'handoff',
    kind: 'facts',
    title: 'Registration and planning handoff',
    items: [
      { id: 'registered', label: 'Engagement', ...(e.registration_id === null ? { value: 'Not registered yet' } : { tag: { label: 'Registered', tone: 'verified' as const } }) },
      { id: 'handoff', label: 'Planning handoff', ...(e.planning_receipt_id === null ? { value: 'Not handed off yet' } : { tag: { label: 'Receipt recorded', tone: 'verified' as const } }) },
    ],
  });

  if (intake && intake.sources.length > 0) {
    out.push({
      key: 'sources',
      kind: 'text',
      title: 'Sources on file for this engagement',
      items: intake.sources.map((s) => ({ id: String(s.id), text: proofLabel(s) })),
    });
  }
  return out;
}

/** The four writes of POST /work/{id}/engagement, described from the response. A step the response does not list stays described but is not drawn. */
export function engagementCommands(e: Engagement, ctx: { workId: number }): CommandDescriptor[] {
  const tokens = { expected_revision: e.expected_revision, case_revision: e.case_revision };
  const missing = e.expected_revision == null || e.case_revision == null;
  const url = `/api/v1/work/${ctx.workId}/engagement`;
  const listed = (action: Engagement['actions'][number], label: string, keyed: boolean) =>
    makeCommand({
      id: `engagement.${action}`,
      label,
      url,
      tokens,
      ...(keyed ? { keyField: 'key' as const } : {}),
      ...(!e.actions.includes(action) ? { disabledReason: 'This step isn’t open now.' } : missing ? { disabledReason: NO_TOKEN } : {}),
      successStatuses: [201],
    });
  return [listed('assign', 'Confirm the project manager', true), listed('details', 'Record the details', true), listed('register', 'Register the engagement', true), listed('reassess', 'Check again', false)];
}
