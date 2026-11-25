// F-92: the minutes start. The notes file goes with the start, as multipart, to the project's minutes route; it is not uploaded
// to `/cases/{id}/files` first (that route's upload id is not one the minutes body can cite).
import { csrfHeader, liveApi } from '@/api/client';

import type { Values } from '../intake';
import type { StartContext } from '../lines';
import { START_TIMEOUT_MS } from '../useStartWork';
import { fileOf, sentValue, textOf } from './body';
import type { Plan } from './plan';

/** What is sent for minutes: the project and the parts, already built so "Check again" resends the same file and key. */
export type MinutesPrepared = { caseId: string; form: FormData };

export const isMinutes = (prepared: unknown): prepared is MinutesPrepared => typeof prepared === 'object' && prepared !== null && 'form' in prepared;

/** Parts: case_revision, idempotency_key, reference, template_id, audience, notes_file, and meeting_version_id only when chosen. `background` is not sent. */
export function minutesParts(plan: Plan, values: Values, ctx: StartContext): MinutesPrepared {
  const form = new FormData();
  form.append('case_revision', String(ctx.caseRevision));
  form.append('idempotency_key', ctx.idempotencyKey);
  form.append('reference', textOf(values.reference));
  for (const field of plan.fields) {
    const value = sentValue(field, values[field.name]);
    if (value !== null && value !== undefined) form.append(field.name, String(value));
  }
  const file = plan.upload ? fileOf(values[plan.upload.name]) : null;
  if (file && plan.upload) form.append(plan.upload.name, file);
  return { caseId: ctx.caseId, form };
}

export function sendMinutes({ caseId, form }: MinutesPrepared) {
  return liveApi.POST('/api/v1/projects/{case_id}/minutes/intake', {
    params: { path: { case_id: caseId }, ...csrfHeader },
    // The body is multipart; the browser sets its Content-Type with the boundary.
    body: {} as never,
    bodySerializer: () => form,
    signal: AbortSignal.timeout(START_TIMEOUT_MS),
  });
}
