// F-92: from the values to exactly the schema's keys, and from a server field name to a control.
import type { FieldValue, Values } from '../intake';
import type { Missing, StartContext } from '../lines';
import type { StartBody } from '../types';
import { activeFields, type EngineField, type Plan } from './plan';

export type Picked = { value: string; label: string };

export const textOf = (value: unknown) => (typeof value === 'string' ? value.trim() : '');
export const pickedId = (value: FieldValue | undefined): number | null => {
  const id = value && typeof value === 'object' && 'value' in value ? Number.parseInt(String(value.value), 10) : Number.NaN;
  return Number.isSafeInteger(id) ? id : null;
};
/** The chosen file: read by its shape (name, size, slice), as no other field value has all three. */
export const fileOf = (value: FieldValue | undefined): File | null =>
  value && typeof value === 'object' && 'name' in value && 'size' in value && typeof (value as File).slice === 'function' ? (value as File) : null;

/** The value to send for one control, or `undefined` for "not sent". An empty nullable sends null. */
export function sentValue(field: EngineField, value: FieldValue | undefined): string | number | null | undefined {
  const sent = field.kind === 'record' ? pickedId(value) : textOf(value) || null;
  if (sent !== null) return sent;
  return field.omit ? undefined : null;
}

const setPath = (target: Record<string, unknown>, path: string, value: unknown) => {
  const keys = path.split('.');
  let at = target;
  for (const key of keys.slice(0, -1)) at = (at[key] ??= {}) as Record<string, unknown>;
  at[keys[keys.length - 1]] = value;
};

/** `POST /work`'s body: `line`, `case_id`, `case_revision`, `idempotency_key`, `intake` and, when the schema has it, `reference`. */
export function jsonBody(key: string, plan: Plan, values: Values, ctx: StartContext): StartBody {
  const intake: Record<string, unknown> = {};
  for (const { path, value } of plan.consts) setPath(intake, path, value);
  for (const field of activeFields(plan, values)) {
    const value = sentValue(field, values[field.name]);
    if (value !== undefined) setPath(intake, field.path, value);
  }
  return {
    line: key,
    case_id: ctx.caseId,
    case_revision: ctx.caseRevision,
    idempotency_key: ctx.idempotencyKey,
    intake,
    ...(plan.reference ? { reference: textOf(values.reference) } : {}),
  } as StartBody;
}

/** The required controls left empty, in the order drawn. */
export function missingOf(plan: Plan, values: Values): Missing[] {
  const out: Missing[] = [];
  for (const field of activeFields(plan, values)) if (field.required && sentValue(field, values[field.name]) == null) out.push({ name: field.name, label: field.label });
  if (plan.upload && !fileOf(values[plan.upload.name])) out.push({ name: plan.upload.name, label: plan.upload.label });
  if (plan.reference && !textOf(values.reference)) out.push({ name: 'reference', label: 'Reference' });
  return out;
}

/** A 422 `fields[].name` to the control it belongs to: 'project', 'general', a control name, or undefined (drawn as its own box). */
export function targetOf(plan: Plan, serverName: string): string | undefined {
  if (serverName === 'case_id' || serverName === 'case_revision') return 'project';
  if (serverName === 'line' || serverName === 'idempotency_key') return 'general';
  if (serverName === 'reference') return plan.reference ? 'reference' : undefined;
  const names = [...plan.fields.map((f) => ({ name: f.name, paths: [f.name, f.path] })), ...(plan.upload ? [{ name: plan.upload.name, paths: [plan.upload.name] }] : [])];
  const bare = serverName.startsWith('intake.') ? serverName.slice('intake.'.length) : serverName;
  const exact = names.find((n) => n.paths.includes(serverName) || n.paths.includes(bare));
  if (exact) return exact.name;
  // A name that is a prefix of a control (`intake.inputs`) is shown on the first of them.
  return names.find((n) => n.paths.some((p) => p.startsWith(`${bare}.`)))?.name;
}
