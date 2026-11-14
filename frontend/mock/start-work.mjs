// Start work in the contract mock: E-LINES, E-LINE-OPTIONS and E-WORK-START. Local use only.
//
// Lines: fixtures/start-work/lines.<persona>.json. Options: fixtures/start-work/options/<field>.json, filtered by
// the mock-only `_personas` and `_parent` (both stripped before serving), then `q`, paged by an "o:<offset>" cursor.
// A start is checked in order: request schema (422), line granted (403), idempotency replay (same key and body:
// the stored 201; different body: 409), case served to the persona (404), case revision (409), intake (422). Started
// work is kept in memory by idempotency key; reset() clears it.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

export const START_OPERATIONS = ['E-LINES', 'E-LINE-OPTIONS', 'E-WORK-START'];

const dir = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'start-work');
const readJson = (path) => JSON.parse(readFileSync(join(dir, path), 'utf8'));

const PERSONAS = ['finance_lead', 'pm', 'ceo', 'none'];
const LIMITS = [10, 20, 50];
// Fields whose options share a file with another field's name.
const OPTION_FILES = { from_issue: 'issue' };
// The work item each line's 201 answers with (fixtures/work/W-14xx.json, in fixture table order).
const WORK_IDS = {
  invoice: 'W-1401',
  weekly_report: 'W-1402',
  minutes: 'W-1403',
  issue_followup: 'W-1404',
  change_request: 'W-1405',
  emergency_change: 'W-1406',
  escalation: 'W-1407',
  leadership_report: 'W-1408',
};
const KIND_WORDS = { date: 'date', date_range: 'date range', period: 'period', datetime: 'date and time', integer: 'whole number' };

const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow you to start this line.' };
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const REUSED = {
  code: 'idempotency_key_reused',
  message: 'This start was already sent with different details. Close the form and start again.',
};
const INVALID = 'Check the highlighted fields and try again.';

// A malformed segment such as `%` keeps its raw text instead of crashing the mock.
function decodePart(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const strip = (row) => Object.fromEntries(Object.entries(row).filter(([key]) => !key.startsWith('_')));

/** Sorted-key JSON, so two bodies with the same content compare equal whatever their key order. */
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

const isDate = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`));
const SHAPES = {
  date: isDate,
  period: (v) => typeof v === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(v),
  datetime: (v) => typeof v === 'string' && /T.*(Z|[+-]\d{2}:\d{2})$/.test(v) && !Number.isNaN(Date.parse(v)),
  integer: (v) => Number.isInteger(v),
  date_range: (v) =>
    v !== null && typeof v === 'object' && !Array.isArray(v) &&
    Object.keys(v).length > 0 && Object.keys(v).every((k) => (k === 'from' || k === 'to') && isDate(v[k])),
};

function isBlank(value) {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  return false;
}

export function createStartWorkMock(openapi) {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const startOp = Object.values(openapi.paths['/api/v1/work']).find((op) => op?.operationId === 'E-WORK-START');
  const validateStart = ajv.compile(startOp.requestBody.content['application/json'].schema);
  const lines = Object.fromEntries(PERSONAS.map((p) => [p, readJson(`lines.${p}.json`)]));
  const optionCache = new Map();
  // idempotency_key -> {body, response}; in memory only.
  const started = new Map();

  function optionRows(field) {
    const file = OPTION_FILES[field] ?? field;
    if (!optionCache.has(file)) optionCache.set(file, readJson(`options/${file}.json`).items);
    return optionCache.get(file);
  }

  /** Options this persona is served for a field, narrowed by parent; with the mock-only keys still on. */
  function served(persona, field, parent) {
    return optionRows(field.name).filter(
      (row) => row._personas.includes(persona) && (!field.depends_on || row._parent === parent),
    );
  }

  const lineFor = (persona, key) => lines[persona].items.find((line) => line.key === key);
  const optionsField = (line, name) => line.intake.find((f) => f.name === name && f.options_source === 'line_options');

  function options(url, persona) {
    const [, , , , lineKey, , fieldName] = url.pathname.split('/').map(decodePart);
    const line = lineFor(persona, lineKey);
    if (!line) return [404, NOT_FOUND];
    const field = optionsField(line, fieldName);
    if (!field) return [404, NOT_FOUND];
    const query = url.searchParams;
    const asOf = lines[persona].as_of;
    const parent = query.get('parent');
    if (field.depends_on && !parent) return [200, { items: [], as_of: asOf }];
    const q = (query.get('q') ?? '').toLowerCase();
    const rows = served(persona, field, parent).filter((row) => row.label.toLowerCase().includes(q));
    const limit = LIMITS.includes(Number(query.get('limit'))) ? Number(query.get('limit')) : 20;
    const match = /^o:(\d+)$/.exec(query.get('cursor') ?? '');
    const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
    const page = { items: rows.slice(offset, offset + limit).map(strip), as_of: asOf };
    if (offset + limit < rows.length) page.next_cursor = `o:${offset + limit}`;
    return [200, page];
  }

  /** Per-field problems with the intake, as {name, message}. */
  function intakeProblems(line, intake, persona) {
    const fields = [];
    const known = new Map(line.intake.map((f) => [f.name, f]));
    for (const name of Object.keys(intake)) {
      const field = known.get(name);
      if (!field || field.type === 'display') fields.push({ name, message: "This field can't be sent." });
    }
    for (const field of line.intake) {
      if (field.type === 'display') continue;
      const value = intake[field.name];
      if (isBlank(value)) {
        if (field.required) fields.push({ name: field.name, message: `${field.label} is required.` });
        continue;
      }
      if (field.type === 'text' || field.type === 'long_text') {
        if (typeof value !== 'string') fields.push({ name: field.name, message: `Enter ${field.label.toLowerCase()} as text.` });
      } else if (field.type === 'choice') {
        if (!field.options.some((o) => o.value === value)) fields.push({ name: field.name, message: 'Choose one from the list.' });
      } else if (field.type === 'record' || field.type === 'records') {
        const values = field.type === 'records' && Array.isArray(value) ? value : [value];
        const rows = served(persona, field, intake[field.depends_on]);
        const chosen = values.map((v) => rows.find((row) => row.value === v));
        const disabled = chosen.find((row) => row?.disabled_reason);
        if ((field.type === 'record' && Array.isArray(value)) || chosen.some((row) => !row)) {
          fields.push({ name: field.name, message: 'Choose one from the list.' });
        } else if (disabled) fields.push({ name: field.name, message: disabled.disabled_reason });
      } else if (SHAPES[field.type] && !SHAPES[field.type](value)) {
        fields.push({ name: field.name, message: `Enter a valid ${KIND_WORDS[field.type]}.` });
      }
    }
    // Sample stand-in for the validation board's billing-contact message: a name with no matching field.
    if (line.key === 'invoice' && intake.project === 'P-0102') {
      fields.push({
        name: 'billing_contact',
        message: "The client register has no billing contact for Harmattan Bank. Add one in the project's client details.",
      });
    }
    return fields;
  }

  function start(raw, persona) {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return [422, { code: 'invalid', message: INVALID, fields: [{ name: 'body', message: 'Send the start as JSON.' }] }];
    }
    if (!validateStart(body)) {
      const names = [...new Set(validateStart.errors.map(
        (e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body'),
      ))];
      return [422, { code: 'invalid', message: INVALID, fields: names.map((name) => ({ name, message: "This field is missing or can't be sent." })) }];
    }
    const line = lineFor(persona, body.line);
    if (!line) return [403, FORBIDDEN];
    const previous = started.get(body.idempotency_key);
    if (previous) return canonical(previous.body) === canonical(body) ? previous.response : [409, REUSED];

    let caseRevision;
    if (line.case_scope === 'project') {
      const field = optionsField(line, line.case_field);
      const option = field && served(persona, field).find((row) => row.value === body.intake[line.case_field]);
      if (!option?.case_id || option.case_id !== body.case_id) return [404, NOT_FOUND];
      caseRevision = option.case_revision;
    } else if (line.case_scope === 'fixed') {
      if (line.case_id !== body.case_id) return [404, NOT_FOUND];
      caseRevision = line.case_revision;
    } else return [404, NOT_FOUND];
    if (body.case_revision !== caseRevision) return [409, STALE];

    const fields = intakeProblems(line, body.intake, persona);
    if (fields.length > 0) return [422, { code: 'invalid', message: INVALID, fields }];
    const response = [201, { work_id: WORK_IDS[line.key], state: 'processing' }];
    started.set(body.idempotency_key, { body, response });
    return response;
  }

  return {
    started,
    reset: () => started.clear(),
    handle(operationId, { url, raw, persona }) {
      if (operationId === 'E-LINES') return [200, lines[persona]];
      if (operationId === 'E-LINE-OPTIONS') return options(url, persona);
      return start(raw, persona);
    },
  };
}
