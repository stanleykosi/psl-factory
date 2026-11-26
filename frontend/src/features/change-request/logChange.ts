// F-112 "Log a change" on the Registers tab's Changes register: the limits the contract states, the response check for
// GET /projects/{case_id}/ordinary-changes, the form's checks and the `capture` body. Pure functions only. The categories are the
// contract's two; the proof is one the read lists; nothing about who may log a change is decided here. Standard-procedure preapproval and
// matching (`preapprove`, `bind_standard`) are not part of this form.
import type { Register } from './changeModel';

export type { Register };
export type LoggedChange = Register['records'][number];

export const LIMITS = { reference: 160, module: 160, description: 4000, reason: 4000 } as const;
export const CATEGORIES = ['Normal', 'Standard'] as const;

export type Draft = { reference: string; category: string | undefined; module: string; description: string; reason: string; evidence: string | undefined };
export const EMPTY_DRAFT: Draft = { reference: '', category: undefined, module: '', description: '', reason: '', evidence: undefined };

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isId = (value: unknown) => Number.isInteger(value) && (value as number) >= 1;

/** A 200 that is not the change list (a revision, records, proofs, procedures and a finding) is a load failure. */
export function isRegisterRead(body: unknown): body is Register {
  return (
    isObject(body) &&
    isId(body.case_revision) &&
    Array.isArray(body.records) &&
    body.records.every((r) => isObject(r) && isId(r.id) && isId(r.version_id) && typeof r.reference === 'string' && typeof r.module === 'string' && typeof r.description === 'string' && (r.category === 'Standard' || r.category === 'Normal')) &&
    Array.isArray(body.evidence) &&
    body.evidence.every((e) => isObject(e) && isId(e.id) && isId(e.version) && typeof e.kind === 'string') &&
    Array.isArray(body.catalogue) &&
    typeof body.catalogue_finding === 'string'
  );
}

/** A 201 that names the new change and the new case revision. */
export const isCaptured = (body: unknown): body is { id: number; case_revision: number } => isObject(body) && isId(body.id) && isId(body.case_revision);

export const proofLabel = (p: { id: number; version: number; kind: string }) => `${p.kind.replaceAll('_', ' ')} · version ${p.version} · no. ${p.id}`;

const TEXT: { name: 'reference' | 'module' | 'description' | 'reason'; label: string }[] = [
  { name: 'reference', label: 'a reference' },
  { name: 'module', label: 'a module' },
  { name: 'description', label: 'a description' },
  { name: 'reason', label: 'the reason' },
];

/** What is missing or too long, by control name, in the order drawn. Every field is required. */
export function problemsOf(draft: Draft, data: Register): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { name, label } of TEXT) {
    const value = draft[name].trim();
    if (!value) out[name] = `Add ${label} to continue.`;
    else if (value.length > LIMITS[name]) out[name] = `Use ${LIMITS[name]} characters or fewer.`;
  }
  if (!draft.category || !(CATEGORIES as readonly string[]).includes(draft.category)) out.category = 'Choose the category to continue.';
  if (!draft.evidence || !data.evidence.some((e) => String(e.id) === draft.evidence)) out.evidence = 'Choose the proof to continue.';
  return out;
}

/** The POST body. The proof id is the chosen listed one; the revision is the read's. */
export function bodyOf(draft: Draft, caseRevision: number) {
  return {
    action: 'capture' as const,
    case_revision: caseRevision,
    reference: draft.reference.trim(),
    category: draft.category === 'Standard' ? ('Standard' as const) : ('Normal' as const),
    module: draft.module.trim(),
    description: draft.description.trim(),
    reason: draft.reason.trim(),
    evidence_id: Number.parseInt(draft.evidence ?? '', 10),
  };
}

/** The server's field names to the controls that draw them. */
export const CONTROL: Record<string, string> = { reference: 'reference', category: 'category', module: 'module', description: 'description', reason: 'reason', evidence_id: 'evidence' };
