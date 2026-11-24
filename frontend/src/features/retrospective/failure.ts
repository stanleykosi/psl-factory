// What the person is told after a failed write, and which field it belongs to. Pure: no client, no state.
import { ApiError } from '@/api/errors';

/** What the person is told after a failed write, and which field it belongs to. */
export type Failure = { kind: 'stale' | 'csrf' | 'forbidden' | 'gone' | 'retry' | 'invalid' | 'unconfirmed' | 'notsaved' | 'signed_out'; message: string; fields: Record<string, string> };

const FIELD_OF: Record<string, string> = { reference: 'reference', occurred_at: 'occurredAt', summary: 'boxes', evidence_id: 'evidence', description: 'description', reason: 'reason', due_at: 'dueAt', owner_id: 'ownerId' };

export function failureOf(error: ApiError): Failure {
  const none = {};
  if (error.kind === 'unauthenticated') return { kind: 'signed_out', message: 'You are signed out.', fields: none };
  if (error.kind === 'stale') return { kind: 'stale', message: 'This changed while you were editing. Reload and try again.', fields: none };
  if (error.kind === 'csrf') return { kind: 'csrf', message: 'Press Save again.', fields: none };
  if (error.kind === 'forbidden') return { kind: 'forbidden', message: "You can't record a retrospective on this project.", fields: none };
  if (error.kind === 'not_found') return { kind: 'gone', message: 'This record is unavailable.', fields: none };
  if (error.kind === 'rate_limited') return { kind: 'retry', message: 'Try again shortly.', fields: none };
  if (error.kind === 'invalid') {
    const fields: Record<string, string> = {};
    // A field the page has no control for is kept under `other`, so a form can still say it.
    for (const f of error.fields) {
      const key = FIELD_OF[f.name] ?? 'other';
      fields[key] = fields[key] && key === 'other' ? `${fields[key]} ${f.message}` : f.message;
    }
    if (error.code === 'invalid_evidence') fields.evidence = error.message;
    return { kind: 'invalid', message: error.message, fields };
  }
  return { kind: 'unconfirmed', message: "We couldn't confirm it saved. Checking what was recorded.", fields: none };
}

/**
 * The words for a 422 that no control carries: messages of fields this form does not draw, else the API's own message
 * when it named no field at all. Null when every named field has its control (nothing is left to say above the button).
 */
export function generalMessage(failure: Failure | null, drawn: readonly string[]): string | null {
  if (failure?.kind !== 'invalid') return null;
  const loose = Object.entries(failure.fields).filter(([key]) => !drawn.includes(key)).map(([, message]) => message);
  if (loose.length > 0) return loose.join(' ');
  return Object.keys(failure.fields).length === 0 ? failure.message : null;
}
