// SCR-08 document review on the live document-review contract (documents_preview, documents_report_controls,
// documents_decide). Pure functions only. Every value is shown as the response sends it: nothing is computed from
// the findings or the status text, and a part the response lacks is left out. Section text is plain text; nothing
// here produces markup.
import type { operations } from '@/api/live-schema';

export type LiveDocument = operations['documents_preview']['responses'][200]['content']['application/json'];
export type Verdict = 'approve' | 'return';
/** What the publication read gives this page: the status word and the sentences that say why a decision is blocked. */
export type Publication = { review_status: string | null; findings: string[] };

export const NOTE_MAX = 4000;

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
export const textOf = (value: unknown): string | undefined => (typeof value === 'string' && value.trim() !== '' ? value : undefined);

/** A 200 body that is not a document preview (a misrouted response) is a load failure. */
export function isDocument(body: unknown): body is LiveDocument {
  if (!isObject(body)) return false;
  return (
    typeof body.title === 'string' &&
    Number.isInteger(body.version) &&
    Number.isInteger(body.revision) &&
    typeof body.audience === 'string' &&
    typeof body.current === 'boolean' &&
    Array.isArray(body.decisions) &&
    Array.isArray(body.preview) &&
    body.preview.every((s) => isObject(s) && typeof s.field === 'string' && typeof s.text === 'string')
  );
}

/** The publication read, or null when it is not usable (the page then shows no status tag and no blockers). */
export function publicationOf(body: unknown): Publication | null {
  if (!isObject(body) || !Array.isArray(body.findings)) return null;
  const status = body.review_status;
  if (status !== null && typeof status !== 'string') return null;
  return { review_status: status, findings: body.findings.filter((f): f is string => typeof f === 'string' && f.trim() !== '') };
}

/** The `version_id` in the URL: 1 to 9223372036854775807 written without a sign, a leading zero or a decimal point. */
export const isVersionId = (value: string): boolean => /^[1-9]\d{0,18}$/.test(value) && (value.length < 19 || value <= '9223372036854775807');

/** The verdicts the response offers that this page draws; any other (reject) is not a control. */
export const verdictsOf = (doc: LiveDocument): Verdict[] => (['approve', 'return'] as const).filter((v) => doc.decisions.includes(v));

/** Paragraphs split on blank lines; plain text only. */
export const paragraphsOf = (text: string): string[] => text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);

/** The note rule, one for every verdict: 1 to NOTE_MAX characters, not blank after trimming. */
export function noteProblem(note: string): string | null {
  if (note.length > NOTE_MAX) return `Keep the note to ${NOTE_MAX} characters or fewer.`;
  if (note.trim() === '') return 'Add a note to record your decision.';
  return null;
}

export const documentHref = (caseId: string, versionId: number | string) => `/projects/${encodeURIComponent(caseId)}/documents/${versionId}`;

/**
 * The review page a Documents-tab row opens: only when the row's own `api_url` is exactly the document-review path of
 * this project (no other case, path, host or suffix). Anything else is not a link.
 */
export function reviewHrefOf(caseId: string, apiUrl: unknown): string | undefined {
  if (typeof apiUrl !== 'string') return undefined;
  const prefix = `/api/v1/projects/${caseId}/document-reviews/`;
  if (!apiUrl.startsWith(prefix)) return undefined;
  const id = apiUrl.slice(prefix.length);
  return isVersionId(id) ? documentHref(caseId, id) : undefined;
}
