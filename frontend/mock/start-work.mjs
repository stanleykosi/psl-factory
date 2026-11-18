// Start work in the contract mock: E-LINES, E-LINE-OPTIONS, E-WORK-START and the start-work proof uploads
// (E-EVIDENCE-UPLOAD, FE-M2A-PROOF). Local use only.
//
// Lines: fixtures/start-work/lines.<persona>.json. Options: fixtures/start-work/options/<field>.json, filtered by
// the mock-only `_personas` and `_parent` (both stripped before serving), then `q`, paged by an "o:<offset>" cursor.
// A start is checked in order: request schema (422), line granted (403), idempotency replay (same key and body:
// the stored 201; different body: 409), case served to the persona (404), case revision (409), intake (422). Started
// work is kept in memory by idempotency key; reset() clears it.
//
// Proof: an upload whose `kind` is the evidence_kind of a line served to the persona comes here (server.mjs routes
// it). Checked in order: request schema (422), a case that line starts on (its fixed case, or a project option
// served to the persona; else 404), case revision (409), content (422: empty, or the backend-stated sample "EXE
// files can't be used as proof."). Success moves the case revision on by one and returns EV-SW-<case_id>-<n>. Case
// revisions live in one map ("<persona>:<case_id>", from the fixtures) that E-LINES, E-LINE-OPTIONS and E-WORK-START
// read, so a re-read after a 409 sees the current one. A start's evidence value must be an id issued here on the
// same case for the same persona. The mock-only cookie psl_mock_start_work picks an uncertain fixture, used once
// per reset: `upload_uncertain` applies the next upload and answers 500; `start_uncertain` applies the next start
// (stored under its key, so a replay answers its 201) and answers 500.
import { createHash } from 'node:crypto';
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
const OPTION_FILES = { from_issue: 'issue', status_cites: 'records', risks_cites: 'records', timeline_cites: 'records', next_steps_cites: 'records' };
// F-21, F-23: the weekly report's cite fields and the minutes' action owner are step fields of the work item, not intake fields; the mock lists this week's records for them.
const STEP_RECORD_FIELDS = { weekly_report: ['status_cites', 'risks_cites', 'timeline_cites', 'next_steps_cites'], minutes: ['owner'] };
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
  income_schedules: 'W-4401',
  ledger_sources: 'W-4402',
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
const LOST = { code: 'mock_lost', message: 'The mock applied this and dropped the reply.' };
const NOT_ON_RECORD = "That proof isn't on this record. Add it again.";
const UNCERTAIN = ['upload_uncertain', 'start_uncertain'];

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
  const uploadOp = Object.values(openapi.paths['/api/v1/cases/{case_id}/evidence']).find((op) => op?.operationId === 'E-EVIDENCE-UPLOAD');
  const validateUpload = ajv.compile(uploadOp.requestBody.content['application/json'].schema);
  const lines = Object.fromEntries(PERSONAS.map((p) => [p, readJson(`lines.${p}.json`)]));
  const optionCache = new Map();
  // idempotency_key -> {body, response}; in memory only.
  const started = new Map();
  // "<persona>:<case_id>" -> the case revision once an upload moved it on; the fixture value until then.
  const revisions = new Map();
  // "<persona>:<case_id>" -> the evidence ids issued on that case.
  const issued = new Map();
  // "<persona> <fixture>": the uncertain fixtures already used since the last reset.
  const used = new Set();

  const revisionOf = (persona, caseId, base) => revisions.get(`${persona}:${caseId}`) ?? base;
  /** One uncertain fixture, once per reset: true the first time the cookie names it for this persona. */
  function uncertainOnce(persona, cookies, name) {
    if (cookies?.psl_mock_start_work !== name || !UNCERTAIN.includes(name) || used.has(`${persona} ${name}`)) return false;
    used.add(`${persona} ${name}`);
    return true;
  }

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

  const lineFor = (persona, key) => lines[persona]?.items.find((line) => line.key === key);
  /** E-LINES as served now: a fixed case carries its current revision. */
  const servedLines = (persona) => ({
    ...lines[persona],
    items: lines[persona].items.map((line) =>
      line.case_scope === 'fixed' && line.case_id !== undefined && line.case_revision !== undefined
        ? { ...line, case_revision: revisionOf(persona, line.case_id, line.case_revision) }
        : line,
    ),
  });
  const withRevision = (persona, row) =>
    row.case_id !== undefined && row.case_revision !== undefined ? { ...row, case_revision: revisionOf(persona, row.case_id, row.case_revision) } : row;
  const optionsField = (line, name) =>
    line.intake.find((f) => f.name === name && f.options_source === 'line_options') ??
    (STEP_RECORD_FIELDS[line.key]?.includes(name) ? { name, type: 'records', options_source: 'line_options' } : undefined);

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
    const page = { items: rows.slice(offset, offset + limit).map((row) => strip(withRevision(persona, row))), as_of: asOf };
    if (offset + limit < rows.length) page.next_cursor = `o:${offset + limit}`;
    return [200, page];
  }

  /** Per-field problems with the intake, as {name, message}. */
  function intakeProblems(line, intake, persona, caseId) {
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
      } else if (field.type === 'evidence') {
        const ids = field.multiple && Array.isArray(value) ? value : [value];
        const mine = issued.get(`${persona}:${caseId}`);
        if ((!field.multiple && Array.isArray(value)) || !field.evidence_kind || !ids.every((id) => typeof id === 'string' && mine?.get(id) === field.evidence_kind)) {
          fields.push({ name: field.name, message: NOT_ON_RECORD });
        }
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

  /** The fixture revision of a case this line starts on for this persona, or undefined when it doesn't start there. */
  function caseBase(line, persona, caseId, intake) {
    if (line.case_scope === 'fixed') return line.case_id === caseId ? line.case_revision : undefined;
    if (line.case_scope !== 'project') return undefined;
    const field = optionsField(line, line.case_field);
    const rows = field ? served(persona, field) : [];
    const option = intake ? rows.find((row) => row.value === intake[line.case_field]) : rows.find((row) => row.case_id === caseId);
    return option?.case_id === caseId ? option.case_revision : undefined;
  }

  /** The evidence kinds of the lines served to this persona. */
  const kindsFor = (persona) => (lines[persona]?.items ?? []).flatMap((line) => line.intake.filter((f) => f.type === 'evidence' && f.evidence_kind).map((f) => f.evidence_kind));

  /** True when an upload belongs to start work: its kind is the evidence_kind of a line served to the persona. */
  function ownsUpload(raw, persona) {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return false;
    }
    return typeof body?.kind === 'string' && kindsFor(persona).includes(body.kind);
  }

  function upload(url, raw, persona, cookies) {
    const caseId = decodePart(url.pathname.split('/')[4] ?? '');
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return [422, { code: 'invalid', message: INVALID }];
    }
    if (!validateUpload(body)) return [422, { code: 'invalid', message: INVALID }];
    const line = lines[persona].items.find(
      (l) => l.intake.some((f) => f.type === 'evidence' && f.evidence_kind === body.kind) && caseBase(l, persona, caseId) !== undefined,
    );
    if (!line) return [404, NOT_FOUND];
    const current = revisionOf(persona, caseId, caseBase(line, persona, caseId));
    if (body.case_revision !== current) return [409, STALE];
    const bytes = /^[A-Za-z0-9+/]+={0,2}$/.test(body.content_base64) ? Buffer.from(body.content_base64, 'base64') : Buffer.alloc(0);
    if (bytes.length === 0) return [422, { code: 'invalid', message: 'This file is empty. Choose another file.' }];
    if (/\.exe$/i.test(body.filename.trim())) return [422, { code: 'invalid', message: "EXE files can't be used as proof." }];
    const key = `${persona}:${caseId}`;
    const ids = issued.get(key) ?? new Map();
    const evidenceId = `EV-SW-${caseId}-${ids.size + 1}`;
    ids.set(evidenceId, body.kind);
    issued.set(key, ids);
    revisions.set(key, current + 1);
    if (uncertainOnce(persona, cookies, 'upload_uncertain')) return [500, LOST];
    return [200, { evidence_id: evidenceId, sha256: createHash('sha256').update(bytes).digest('hex'), case_revision: current + 1 }];
  }

  function start(raw, persona, cookies) {
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

    const base = caseBase(line, persona, body.case_id, line.case_scope === 'project' ? body.intake : undefined);
    if (base === undefined) return [404, NOT_FOUND];
    if (body.case_revision !== revisionOf(persona, body.case_id, base)) return [409, STALE];

    const fields = intakeProblems(line, body.intake, persona, body.case_id);
    if (fields.length > 0) return [422, { code: 'invalid', message: INVALID, fields }];
    const response = [201, { work_id: WORK_IDS[line.key], state: 'processing' }];
    started.set(body.idempotency_key, { body, response });
    if (uncertainOnce(persona, cookies, 'start_uncertain')) return [500, LOST];
    return response;
  }

  return {
    started,
    issued,
    ownsUpload,
    reset: () => {
      started.clear();
      revisions.clear();
      issued.clear();
      used.clear();
    },
    handle(operationId, { url, raw, persona, cookies }) {
      if (operationId === 'E-LINES') return [200, servedLines(persona)];
      if (operationId === 'E-LINE-OPTIONS') return options(url, persona);
      if (operationId === 'E-EVIDENCE-UPLOAD') return upload(url, raw, persona, cookies);
      return start(raw, persona, cookies);
    },
  };
}
