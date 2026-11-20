// F-49: a line's intake field may carry `show_when: {field, equals[]}` (a mock overlay, G-23-2): the field is drawn
// only while the named field holds one of the listed values. A condition that is malformed is treated as absent.
// Also the second overlay, `allow_new` (G-23-1), read the same careful way.
import type { FieldValue, Values } from './intake';
import type { Field } from './types';

type Overlay = Field & { show_when?: unknown; allow_new?: unknown };

/** The condition on a field, or undefined when it has none or it is malformed. */
export function readShowWhen(field: Field): { field: string; equals: string[] } | undefined {
  const raw = (field as Overlay).show_when;
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  const { field: name, equals } = raw as Record<string, unknown>;
  if (typeof name !== 'string' || name === '' || !Array.isArray(equals) || equals.length === 0) return undefined;
  if (!equals.every((v) => typeof v === 'string' && v !== '')) return undefined;
  return { field: name, equals: equals as string[] };
}

const text = (value: FieldValue | undefined) => (typeof value === 'string' ? value : undefined);

/** True when the field is drawn (and sent) for the values as they stand. */
export function isShown(field: Field, values: Values): boolean {
  const condition = readShowWhen(field);
  if (!condition) return true;
  const current = text(values[condition.field]);
  return current !== undefined && condition.equals.includes(current);
}

/** The fields drawn now, in the order returned. */
export function shownNow(fields: Field[], values: Values): Field[] {
  return fields.filter((field) => isShown(field, values));
}

/** True when a record field may end with "New client" (the overlay `allow_new`). */
export function allowsNew(field: Field): boolean {
  return (field as Overlay).allow_new === true;
}
