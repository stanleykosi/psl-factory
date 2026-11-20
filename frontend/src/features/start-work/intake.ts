// Start work intake, pure: which fields this release renders, the submitted value per kind (D-START-INTAKE),
// the case a start goes to, and which fields a parent clears. Nothing here checks business rules: the
// server's 422 is the only source of field errors, and a case is only ever taken from the line or the chosen option.
import type { Field, Line, LineOption, StartBody } from './types';

export type RangeValue = { from: string; to: string };
/** A client that is not in the list yet (F-49, overlay `allow_new`): sent as {new: {name}}. */
export type NewValue = { new: { name: string } };
export type FieldValue = string | RangeValue | LineOption | LineOption[] | NewValue;
export type Values = Record<string, FieldValue | undefined>;
export type CaseRef = Pick<StartBody, 'case_id' | 'case_revision'>;

/** Kinds this release renders. Money (and any kind not listed) is not handled yet (F-47C). */
const KINDS = new Set([
  'text',
  'long_text',
  'date',
  'date_range',
  'period',
  'datetime',
  'integer',
  'choice',
  'record',
  'records',
  'display',
  'evidence',
]);

/** The fields rendered, in the order returned; any unhandled kind is left out and never sent. */
export function shownFields(line: Line): Field[] {
  return line.intake.filter((field) => KINDS.has(field.type));
}

/** True for a field the person can fill in this drawer, so a 422 for it is drawn under it. */
export function fillable(field: Field): boolean {
  return KINDS.has(field.type);
}

/** True for an evidence field proof can be uploaded to: it names its evidence_kind and is not restricted. */
export function uploadable(field: Field): boolean {
  return field.type === 'evidence' && Boolean(field.evidence_kind) && !field.restricted;
}

/** False when this drawer can't start the line: another start route, a required unhandled field (or a required
 *  proof nobody can upload here), or no case to start on. */
export function startableHere(line: Line): boolean {
  if (line.start_via !== undefined && line.start_via !== 'work_start') return false;
  if (line.intake.some((field) => field.required && !KINDS.has(field.type))) return false;
  if (line.intake.some((field) => field.required && field.type === 'evidence' && !uploadable(field))) return false;
  if (line.case_scope === 'project') {
    return line.intake.some((field) => field.name === line.case_field && field.type === 'record');
  }
  if (line.case_scope === 'fixed') return line.case_id !== undefined && line.case_revision !== undefined;
  return false;
}

const isOption = (value: FieldValue | undefined): value is LineOption =>
  typeof value === 'object' && value !== null && !Array.isArray(value) && 'value' in value;

export const isNew = (value: FieldValue | undefined): value is NewValue =>
  typeof value === 'object' && value !== null && !Array.isArray(value) && 'new' in value;

/** The case: from the option chosen in case_field (project) or from the line (fixed); null when it doesn't resolve. */
export function resolveCase(line: Line, values: Values): CaseRef | null {
  if (line.case_scope === 'fixed') {
    return line.case_id !== undefined && line.case_revision !== undefined
      ? { case_id: line.case_id, case_revision: line.case_revision }
      : null;
  }
  if (line.case_scope !== 'project' || !line.case_field) return null;
  const chosen = values[line.case_field];
  if (!isOption(chosen) || chosen.case_id === undefined || chosen.case_revision === undefined) return null;
  return { case_id: chosen.case_id, case_revision: chosen.case_revision };
}

/** True when an option is chosen in case_field but it carries no case: that project can't be started on from here. */
export function caseOptionUnusable(line: Line, values: Values): boolean {
  if (line.case_scope !== 'project' || !line.case_field) return false;
  const chosen = values[line.case_field];
  return isOption(chosen) && resolveCase(line, values) === null;
}

/** Every field that depends on `name`, transitively. */
export function dependentsOf(fields: Field[], name: string): string[] {
  const found: string[] = [];
  const queue = [name];
  while (queue.length > 0) {
    const parent = queue.shift()!;
    for (const field of fields) {
      if (field.depends_on === parent && !found.includes(field.name)) {
        found.push(field.name);
        queue.push(field.name);
      }
    }
  }
  return found;
}

/** The parent value sent to E-LINE-OPTIONS: the chosen option's value in the field named by depends_on. */
export function parentValue(field: Field, values: Values): string | undefined {
  if (!field.depends_on) return undefined;
  const parent = values[field.depends_on];
  if (isOption(parent)) return parent.value;
  return typeof parent === 'string' && parent !== '' ? parent : undefined;
}

/** The submitted value for one field, or undefined when it is not sent. */
function submitted(field: Field, value: FieldValue | undefined): unknown {
  if (value === undefined) return undefined;
  switch (field.type) {
    case 'text':
    case 'long_text': {
      const text = typeof value === 'string' ? value.trim() : '';
      return text === '' ? undefined : text;
    }
    case 'date':
    case 'period':
    case 'choice':
      return typeof value === 'string' && value !== '' ? value : undefined;
    case 'date_range': {
      if (typeof value !== 'object' || !('from' in value)) return undefined;
      const range: Partial<RangeValue> = {};
      if (value.from) range.from = value.from;
      if (value.to) range.to = value.to;
      return Object.keys(range).length > 0 ? range : undefined;
    }
    case 'datetime': {
      if (typeof value !== 'string' || value === '') return undefined;
      const time = new Date(value);
      return Number.isNaN(time.getTime()) ? undefined : time.toISOString();
    }
    case 'integer': {
      if (typeof value !== 'string' || !/^-?\d+$/.test(value.trim())) return undefined;
      const number = Number(value.trim());
      return Number.isSafeInteger(number) ? number : undefined;
    }
    case 'record':
      if (isNew(value)) return value.new.name.trim() === '' ? undefined : { new: { name: value.new.name.trim() } };
      return isOption(value) ? value.value : undefined;
    case 'records':
      return Array.isArray(value) && value.length > 0 ? value.map((option) => option.value) : undefined;
    default:
      return undefined;
  }
}

/** The required fields left empty, in the order drawn: nothing is sent while any is (the server's 422 is for the rest).
 *  A field is empty when it would add nothing to the body; evidence counts the confirmed ids. */
export function emptyRequired(fields: Field[], values: Values, proof: Record<string, string[]> = {}): Field[] {
  return fields.filter((field) => {
    if (!field.required || !KINDS.has(field.type) || field.type === 'display') return false;
    if (field.type === 'evidence') return uploadable(field) && (proof[field.name] ?? []).length === 0;
    return submitted(field, values[field.name]) === undefined;
  });
}

/** intake: only the fields the person filled, keyed by Field.name; display fields and unhandled kinds are never sent.
 *  An evidence field sends the evidence_ids whose upload the backend confirmed (`proof`, by field name, in upload
 *  order): the last one, or all of them when the field is `multiple`. */
export function buildIntake(fields: Field[], values: Values, proof: Record<string, string[]> = {}): Record<string, unknown> {
  const intake: Record<string, unknown> = {};
  for (const field of fields) {
    if (!KINDS.has(field.type) || field.type === 'display') continue;
    if (field.type === 'evidence') {
      const ids = uploadable(field) ? (proof[field.name] ?? []) : [];
      if (ids.length > 0) intake[field.name] = field.multiple ? ids : ids[ids.length - 1];
      continue;
    }
    const value = submitted(field, values[field.name]);
    if (value !== undefined) intake[field.name] = value;
  }
  return intake;
}

/** A new idempotency key, made when a line's drawer opens and after a definitive 409 or 422. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
