// F-92: a line's served `request_schema` plus its config, resolved into the controls to draw, or 'unsupported'.
import type { EngineConfig, Source } from './config';
import { leavesOf, referenceOf, type Leaf } from './schema';

export type EngineField = {
  /** The control's name: the schema path without the config's `strip`. */
  name: string;
  /** The schema path under `intake`. */
  path: string;
  label: string;
  help?: string;
  kind: 'record' | 'choice' | 'text';
  /** Not nullable, and in the schema's `required`: checked before sending. */
  required: boolean;
  nullable: boolean;
  /** Not in the schema's `required`: omitted when empty (otherwise empty sends null). */
  omit: boolean;
  values: string[];
  maxLength?: number;
  /** A date text (`format: date`): drawn and sent as YYYY-MM-DD. */
  date?: boolean;
  valueLabels?: Record<string, string>;
  /** F-94: drawn and sent only when the `mode` control has this value. */
  mode?: string;
  parent?: string;
  source?: Source;
};

export type Plan = {
  fields: EngineField[];
  /** Constants the schema fixes; sent as served, never drawn. */
  consts: { path: string; value: unknown }[];
  /** The `reference` text, or null when the schema has none (the server derives it). */
  reference: { maxLength?: number } | null;
  /** The notes file control, when the line takes one. */
  upload: { name: string; label: string } | null;
};

const nameOf = (config: EngineConfig, path: string) => (config.strip && path.startsWith(config.strip) ? path.slice(config.strip.length) : path);

function fieldOf(config: EngineConfig, leaf: Exclude<Leaf, { kind: 'const' }>): EngineField | null {
  const name = nameOf(config, leaf.path);
  const words = config.labels[name];
  if (!words) return null;
  const base = { name, path: leaf.path, label: words.label, help: words.help, nullable: leaf.nullable, omit: leaf.optional, parent: config.parents?.[name], mode: leaf.when, valueLabels: words.valueLabels };
  const required = !leaf.nullable && !leaf.optional;
  if (leaf.kind === 'integer') {
    const source = config.sources[name];
    return source ? { ...base, kind: 'record', required, values: [], source } : null;
  }
  if (leaf.kind === 'choice') return { ...base, kind: 'choice', required, values: leaf.values };
  return { ...base, kind: 'text', required, values: [], maxLength: leaf.maxLength, date: leaf.format === 'date' };
}

export function planOf(config: EngineConfig, requestSchema: unknown): Plan | 'unsupported' {
  const leaves = leavesOf(requestSchema, config.skip);
  if (leaves === 'unsupported') return 'unsupported';
  const found: EngineField[] = [];
  const consts: Plan['consts'] = [];
  for (const leaf of leaves) {
    if (leaf.kind === 'const') {
      consts.push({ path: leaf.path, value: leaf.value });
      continue;
    }
    const field = fieldOf(config, leaf);
    // A leaf the config cannot draw (a required id with no source, a text it has no words for) is never half-drawn.
    if (!field) return 'unsupported';
    found.push(field);
  }
  const order = Object.keys(config.labels);
  const fields = found.sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name));
  if (!config.needs.every((name) => fields.some((f) => f.name === name))) return 'unsupported';
  if (fields.some((f) => f.parent && !fields.some((p) => p.name === f.parent))) return 'unsupported';
  return { fields, consts, reference: referenceOf(requestSchema), upload: config.upload ? { name: config.upload.name, label: config.upload.label } : null };
}

/** The controls in play: every one for a line with no modes, otherwise the `mode` control and the ones of the chosen mode. */
export function activeFields(plan: Plan, values: Record<string, unknown>): EngineField[] {
  return plan.fields.filter((f) => f.mode === undefined || f.mode === values.mode);
}
