// "Record an issue" (F-137) on the live Registers tab: the limits the contract states, the response check for
// GET /projects/{case_id}/issues, the form's checks and the POST body. Pure functions only; no severity list, owner rule or
// required field is invented here: the owners and proofs are the ones the read serves.
import type { operations } from '@/api/live-schema';

type ReadOperation = operations['issues_register'];
export type IssuesRead = ReadOperation['responses'][200]['content']['application/json'];
export type RegisterIssue = IssuesRead['issues'][number];
export type RecordBody = NonNullable<operations['issues_capture']['requestBody']>['content']['application/json'];

/** The contract's limits (maxLength), shown as counts and checked before sending. */
export const LIMITS = { reference: 160, title: 240, kind: 100, next_action: 1000, note: 4000 } as const;
/** The contract's severity enum, in its order; severity may also be left unset (null). */
export const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'] as const;

export type Draft = { reference: string; title: string; kind: string; owner: string | undefined; next_action: string; evidence: string | undefined; note: string; severity: string | undefined };
export const EMPTY_DRAFT: Draft = { reference: '', title: '', kind: '', owner: undefined, next_action: '', evidence: undefined, note: '', severity: undefined };

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isId = (value: unknown) => Number.isInteger(value) && (value as number) >= 1;

/** A 200 that is not the issues read (a revision, issues, owners and proofs) is a load failure. */
export function isIssuesRead(body: unknown): body is IssuesRead {
  return (
    isObject(body) &&
    isId(body.case_revision) &&
    Array.isArray(body.issues) &&
    body.issues.every((i) => isObject(i) && isId(i.id) && typeof i.reference === 'string' && typeof i.title === 'string' && typeof i.status === 'string') &&
    Array.isArray(body.owners) &&
    body.owners.every((o) => isObject(o) && isId(o.id) && typeof o.name === 'string') &&
    Array.isArray(body.proofs) &&
    body.proofs.every((p) => isObject(p) && isId(p.id) && isId(p.version) && typeof p.kind === 'string')
  );
}

/** A 201 that names the new issue. */
export const isCaptured = (body: unknown): body is { issue_id: number; state_id: number; case_revision: number } => isObject(body) && isId(body.issue_id) && isId(body.state_id) && isId(body.case_revision);

/** The proof as the person reads it: its kind as served and its version. */
export const proofLabel = (proof: { id: number; version: number; kind: string }) => `${proof.kind.replace(/_/g, ' ')} · version ${proof.version} · no. ${proof.id}`;

const TEXT: { name: keyof typeof LIMITS; label: string }[] = [
  { name: 'reference', label: 'a reference' },
  { name: 'title', label: 'a title' },
  { name: 'kind', label: 'a kind' },
  { name: 'next_action', label: 'the next action' },
  { name: 'note', label: 'a note' },
];

/** What is missing or too long, by control name, in the order drawn. */
export function problemsOf(draft: Draft): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { name, label } of TEXT) {
    const value = draft[name].trim();
    if (!value) out[name] = `Add ${label} to continue.`;
    else if (value.length > LIMITS[name]) out[name] = `Use ${LIMITS[name]} characters or fewer.`;
  }
  if (!draft.owner) out.owner = 'Choose the responsible owner to continue.';
  if (!draft.evidence) out.evidence = 'Choose the evidence to continue.';
  return out;
}

/** The POST body; the owner and proof ids are the chosen served ones. `external_links` is required by the contract and is sent empty. */
export function bodyOf(draft: Draft, caseRevision: number): RecordBody {
  return {
    case_revision: caseRevision,
    reference: draft.reference.trim(),
    title: draft.title.trim(),
    kind: draft.kind.trim(),
    owner_id: Number.parseInt(draft.owner ?? '', 10),
    next_action: draft.next_action.trim(),
    evidence_id: Number.parseInt(draft.evidence ?? '', 10),
    note: draft.note.trim(),
    severity: (SEVERITIES as readonly string[]).includes(draft.severity ?? '') ? (draft.severity as (typeof SEVERITIES)[number]) : null,
    external_links: [],
  };
}

/** The server's field names to the controls that draw them. */
export const CONTROL: Record<string, string> = { reference: 'reference', title: 'title', kind: 'kind', owner_id: 'owner', next_action: 'next_action', evidence_id: 'evidence', note: 'note', severity: 'severity' };
