// Start work in the contract mock: E-LINES, E-LINE-OPTIONS, E-WORK-START and the start-work proof uploads
// (E-EVIDENCE-UPLOAD, FE-M2A-PROOF). Local use only.
//
// Lines: fixtures/start-work/lines.<persona>.json. Options: fixtures/start-work/options/<field>.json, filtered by
// the mock-only `_personas` and `_parent` (both stripped before serving), then `q`, paged by an "o:<offset>" cursor.
// A start is checked in order: request schema (422), line granted (403), idempotency replay (same key and body:
// the stored 201; different body: 409), case served to the persona (404), case revision (409), intake (422). Started
// work is kept in memory by idempotency key; reset() clears it.
//
// Proof: an upload whose `kind` is the evidence_kind of a line served to the persona, on a case that line starts on,
// comes here (server.mjs routes it; any other upload keeps its F-09 or F-11 owner). Checked in order: request
// schema (422), a case that line starts on (its fixed case, or a project option served to the persona; else 404),
// case revision (409), content (422: empty, or the backend-stated sample "EXE files can't be used as proof."). Success moves the case revision on by one and returns EV-SW-<case_id>-<n>. Case
// revisions live in one map ("<persona>:<case_id>", from the fixtures) that E-LINES, E-LINE-OPTIONS and E-WORK-START
// read, so a re-read after a 409 sees the current one. A start's evidence value must be an id issued here on the
// same case for the same persona. The mock-only cookie psl_mock_start_work picks an uncertain fixture, used once
// per reset (F-51: `start_hold` is not one of them; it holds every forecast start): `upload_uncertain` applies the next upload and answers 500; `start_uncertain` applies the next start
// (stored under its key, so a replay answers its 201) and answers 500.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { demoProjects, optionRow as demoOptionRow, resetDemoProjects } from './demo-projects.mjs';

export const START_OPERATIONS = ['E-LINES', 'E-LINE-OPTIONS', 'E-WORK-START'];

const dir = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'start-work');
const readJson = (path) => JSON.parse(readFileSync(join(dir, path), 'utf8'));

const PERSONAS = ['finance_lead', 'pm', 'ceo', 'none', 'pmo_lead', 'hr', 'hr_lead'];
const LIMITS = [10, 20, 50];
// Fields whose options share a file with another field's name.
const OPTION_FILES = { from_issue: 'issue', status_cites: 'records', risks_cites: 'records', timeline_cites: 'records', next_steps_cites: 'records' };
// F-21, F-23: the weekly report's cite fields and the minutes' action owner are step fields of the work item, not intake fields; the mock lists this week's records for them.
const STEP_RECORD_FIELDS = { weekly_report: ['status_cites', 'risks_cites', 'timeline_cites', 'next_steps_cites'], minutes: ['owner'] };
// The work item each line's 201 answers with (fixtures/work/W-14xx.json, in fixture table order).
export const WORK_IDS = {
  invoice: 'W-1401',
  weekly_report: 'W-1402',
  minutes: 'W-1403',
  issue_followup: 'W-1404',
  change_request: 'W-1405',
  emergency_change: 'W-1406',
  escalation: 'W-1407',
  leadership_report: 'W-1408',
  income_schedules: 'W-4401',
  // F-45: the ledger start lands on the ledger source's investigating page (W-4201, spec Lanes); W-4402 stays as a fixture
  ledger_sources: 'W-4201',
  // F-49: the logged RFP's work item (fixtures/work/W-3351.json), Unassigned for F-36's assign panel
  rfp_intake: 'W-3351',
  // F-51: the F-42 fixed asset schedule and the F-43 cash forecast
  fixed_assets: 'W-3901',
  cash_forecast: 'W-4001',
  // F-55: the HR stand-in line (fixtures/work/W-4611.json)
  hr_staff_list: 'W-4611',
};
// F-51: what a forecast start answers with under the cookie value start_hold (F-43's "preparer not set" item).
const HELD_FORECAST = { work_id: 'W-4006', state: 'setup_needed' };
// F-49: the state a start answers with; every other line answers processing.
const START_STATES = { rfp_intake: 'owner_needed' };
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
const HOLD_COOKIE = 'start_hold';
// F-49 (G-23-1): the mock-only cookie psl_mock_rfp=new_client serves `allow_new` on the RFP line's client field.
const NEW_CLIENT_COOKIE = 'psl_mock_rfp';

// F-49: the RFPs logged since the last reset, by work id, for the Unassigned list (work-list.mjs).
const logged = new Map();
/** The RFPs a start has logged, as {work_id, reference, client}. */
export const loggedRfps = () => [...logged.values()];

const isNewClient = (v) => v !== null && typeof v === 'object' && !Array.isArray(v) && 'new' in v && v.new !== null && typeof v.new === 'object';

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
  logged.clear();
  const optionCache = new Map();
  // idempotency_key -> {body, response}; in memory only.
  const started = new Map();
  // "<persona>:<case_id>" -> the case revision once an upload moved it on; the fixture value until then.
  const revisions = new Map();
  // "<persona>:<case_id>" -> the evidence ids issued on that case.
  const issued = new Map();
  // "<persona> <fixture>": the uncertain fixtures already used since the last reset.
  const used = new Set();
  // F-49: "<client>|<reference>" of every RFP logged since the last reset.
  const refs = new Set();

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
    // D-164: the projects won demo RFPs created join every project picker, newest first
    const won = field.name === 'project' ? demoProjects().map(demoOptionRow).reverse() : [];
    return [...won, ...optionRows(field.name)].filter(
      (row) => row._personas.includes(persona) && (!field.depends_on || row._parent === parent),
    );
  }

  /** The mock overlay `allow_new` (G-23-1): only the RFP line's client field, only with the cookie. */
  const allowsNew = (line, cookies) => line.key === 'rfp_intake' && cookies?.[NEW_CLIENT_COOKIE] === 'new_client';
  const lineFor = (persona, key) => lines[persona]?.items.find((line) => line.key === key);
  /** E-LINES as served now: a fixed case carries its current revision. */
  const servedLines = (persona, cookies) => ({
    ...lines[persona],
    items: lines[persona].items.map((line) => {
      const fixed =
        line.case_scope === 'fixed' && line.case_id !== undefined && line.case_revision !== undefined
          ? { ...line, case_revision: revisionOf(persona, line.case_id, line.case_revision) }
          : line;
      return allowsNew(fixed, cookies)
        ? { ...fixed, intake: fixed.intake.map((f) => (f.name === 'client' ? { ...f, allow_new: true } : f)) }
        : fixed;
    }),
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
  function intakeProblems(line, intake, persona, caseId, cookies) {
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
      } else if (field.type === 'record' && isNewClient(value)) {
        if (!allowsNew(line, cookies) || Object.keys(value).length !== 1 || Object.keys(value.new).some((k) => k !== 'name')) {
          fields.push({ name: field.name, message: 'Choose one from the list.' });
        } else if (typeof value.new.name !== 'string' || value.new.name.trim() === '') {
          fields.push({ name: field.name, message: `${field.label} is required.` });
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
    if (line.key === 'rfp_intake') rfpProblems(intake, fields, persona);
    if (line.key === 'cash_forecast') forecastProblems(intake, fields);
    return fields;
  }

  /** F-51, backend-stated samples (the page checks none of them): Months, As of and Audience, in the backend's words. */
  function forecastProblems(intake, fields) {
    const say = (name, message) => {
      const at = fields.findIndex((f) => f.name === name);
      if (at >= 0) fields.splice(at, 1);
      fields.push({ name, message });
    };
    if (!isBlank(intake.months) && (!Number.isInteger(intake.months) || intake.months < 1 || intake.months > 12)) say('months', 'Months must be between 1 and 12.');
    if (!isBlank(intake.as_of) && !(isDate(intake.as_of) && new Date(`${intake.as_of}T00:00:00Z`).toISOString().startsWith(intake.as_of))) say('as_of', 'As of must be a date.');
    if (!isBlank(intake.audience) && fields.some((f) => f.name === 'audience')) say('audience', 'Choose one of the listed audiences.');
  }

  /** F-49, backend-stated samples (G-23-2, G-23-3, readiness question 3): the deadline's rules, a "Received" in the
   *  future (against the mock's clock) and a reference already logged for the client. */
  function rfpProblems(intake, fields, persona) {
    const named = (name) => fields.some((f) => f.name === name);
    const stated = intake.deadline_status === 'stated';
    if (!isBlank(intake.deadline_at) && !stated && !named('deadline_at')) {
      fields.push({ name: 'deadline_at', message: 'A deadline can only be entered when it is stated.' });
    }
    if (stated && isBlank(intake.deadline_at) && !named('deadline_at')) {
      fields.push({ name: 'deadline_at', message: 'Enter the deadline the RFP states.' });
    }
    if (SHAPES.datetime(intake.received_at) && Date.parse(intake.received_at) > Date.parse(lines[persona].as_of) && !named('received_at')) {
      fields.push({ name: 'received_at', message: "Received can't be in the future." });
    }
    const client = isNewClient(intake.client) ? `new:${String(intake.client.new.name).trim().toLowerCase()}` : intake.client;
    if (typeof intake.rfp_reference === 'string' && refs.has(`${client}|${intake.rfp_reference.trim().toLowerCase()}`) && !named('rfp_reference')) {
      fields.push({ name: 'rfp_reference', message: 'This RFP is already logged for that client.' });
    }
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

  /** True when an upload belongs to start work: its kind is the evidence_kind of a line served to the persona, and
   *  its case is one that line starts on (the line's fixed case, or a project option served to the persona). */
  function ownsUpload(url, raw, persona) {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return false;
    }
    if (typeof body?.kind !== 'string' || !kindsFor(persona).includes(body.kind)) return false;
    const caseId = decodePart(url.pathname.split('/')[4] ?? '');
    return lines[persona].items.some(
      (l) => l.intake.some((f) => f.type === 'evidence' && f.evidence_kind === body.kind) && caseBase(l, persona, caseId) !== undefined,
    );
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

  /** Remembers a logged RFP: its duplicate key and the Unassigned row work-list.mjs adds. */
  function logRfp(intake, persona) {
    const chosen = isNewClient(intake.client) ? undefined : served(persona, { name: 'client' }).find((row) => row.value === intake.client);
    const client = chosen?.label ?? String(intake.client.new.name).trim();
    refs.add(`${isNewClient(intake.client) ? `new:${client.toLowerCase()}` : intake.client}|${intake.rfp_reference.trim().toLowerCase()}`);
    logged.set(WORK_IDS.rfp_intake, { work_id: WORK_IDS.rfp_intake, reference: intake.rfp_reference.trim(), client });
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

    const fields = intakeProblems(line, body.intake, persona, body.case_id, cookies);
    if (fields.length > 0) return [422, { code: 'invalid', message: INVALID, fields }];
    const held = line.key === 'cash_forecast' && cookies?.psl_mock_start_work === HOLD_COOKIE;
    const response = [201, held ? HELD_FORECAST : { work_id: WORK_IDS[line.key], state: START_STATES[line.key] ?? 'processing' }];
    started.set(body.idempotency_key, { body, response });
    if (line.key === 'rfp_intake') logRfp(body.intake, persona);
    if (uncertainOnce(persona, cookies, 'start_uncertain')) return [500, LOST];
    return response;
  }

  /** The client an RFP start names, as its label (a new client by its name); undefined for another line. */
  const clientLabel = (intake, persona) =>
    isNewClient(intake?.client) ? String(intake.client.new.name).trim() : served(persona, { name: 'client' }).find((row) => row.value === intake?.client)?.label;

  return {
    started,
    issued,
    ownsUpload,
    clientLabel,
    reset: () => {
      resetDemoProjects();
      started.clear();
      revisions.clear();
      issued.clear();
      used.clear();
      refs.clear();
      logged.clear();
    },
    handle(operationId, { url, raw, persona, cookies }) {
      if (operationId === 'E-LINES') return [200, servedLines(persona, cookies)];
      if (operationId === 'E-LINE-OPTIONS') return options(url, persona);
      if (operationId === 'E-EVIDENCE-UPLOAD') return upload(url, raw, persona, cookies);
      return start(raw, persona, cookies);
    },
  };
}
