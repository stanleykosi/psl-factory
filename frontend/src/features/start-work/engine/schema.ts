// F-92: reads the `request_schema` that `GET /lines` serves for a line (the OpenAPI file types it only as `object`, so this is its
// small hand-typed shape). Nothing here is a business rule: every leaf, its nullability, its values and its lengths come from the
// served schema; the line's config adds only labels, order, parents and where a record's choices come from.
export type JsonSchema = {
  type?: string;
  anyOf?: JsonSchema[];
  enum?: unknown[];
  const?: unknown;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  maxLength?: number;
};

/** One leaf of the schema's `intake`, by its dotted path. */
export type Leaf =
  | { path: string; kind: 'integer'; nullable: boolean; optional: boolean }
  | { path: string; kind: 'text'; nullable: boolean; optional: boolean; maxLength?: number }
  | { path: string; kind: 'choice'; nullable: boolean; optional: boolean; values: string[] }
  | { path: string; kind: 'const'; nullable: false; optional: false; value: unknown };

const isNull = (schema: JsonSchema) => schema.type === 'null';

/** The leaves under `schema`, or `undefined` when any part is a shape the engine cannot draw (an array, a boolean, a free value). */
function walk(schema: JsonSchema, path: string, optional: boolean, skip: string[], out: Leaf[]): boolean {
  if (skip.includes(path)) return true;
  if ('const' in schema) {
    out.push({ path, kind: 'const', nullable: false, optional: false, value: schema.const });
    return true;
  }
  if (schema.enum) {
    const nullable = schema.enum.includes(null);
    const values = schema.enum.filter((v) => v !== null);
    if (values.length === 0 || !values.every((v) => typeof v === 'string')) return false;
    out.push({ path, kind: 'choice', nullable, optional, values: values as string[] });
    return true;
  }
  if (schema.anyOf) {
    const [first, ...rest] = schema.anyOf.filter((s) => !isNull(s));
    if (!first || rest.length > 0 || schema.anyOf.length !== 2) return false;
    const before = out.length;
    if (!walk(first, path, optional, skip, out) || out.length !== before + 1) return false;
    const leaf = out[before];
    if (leaf.kind === 'const') return false;
    out[before] = { ...leaf, nullable: true };
    return true;
  }
  if (schema.type === 'integer') out.push({ path, kind: 'integer', nullable: false, optional });
  else if (schema.type === 'string') out.push({ path, kind: 'text', nullable: false, optional, maxLength: schema.maxLength });
  else if (schema.type === 'object' && schema.properties) {
    const required = schema.required ?? [];
    for (const [key, child] of Object.entries(schema.properties)) {
      if (!walk(child, path ? `${path}.${key}` : key, !required.includes(key), skip, out)) return false;
    }
  } else return false;
  return true;
}

/** The leaves of `schema.properties.intake`, or `'unsupported'`. A path in `skip` is left out whole (whatever its shape). */
export function leavesOf(requestSchema: unknown, skip: string[] = []): Leaf[] | 'unsupported' {
  const intake = (requestSchema as JsonSchema | null | undefined)?.properties?.intake;
  if (!intake) return 'unsupported';
  const out: Leaf[] = [];
  return walk(intake, '', false, skip, out) ? out : 'unsupported';
}

/** The `reference` text the schema asks for, or null when the server derives it (no `reference` property). */
export function referenceOf(requestSchema: unknown): { maxLength?: number } | null {
  const reference = (requestSchema as JsonSchema | null | undefined)?.properties?.reference;
  return reference?.type === 'string' ? { maxLength: reference.maxLength } : null;
}
