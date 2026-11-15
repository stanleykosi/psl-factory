// Document templates mock (E-TEMPLATES, E-TEMPLATE-VERSION) for F-20. Sample data only: every template is a test
// template, and the mock never returns test_template false (no fixture value is presented as PSL's own).
// Built on D-TEMPLATES-VIEW r1, which is still a proposal; the cursor query is a proposal too.
//
// Scenario: cookie psl_mock_templates = desktop (default) | mobile | readonly | empty | forbidden | many.
// Save: cookie psl_mock_templates_save = stale (another person uploads first, then 409) | invalid (422 naming filename, note).
// pm and none get 403 on both calls. can_upload comes from the data, never from the persona.
// An upload is kept as an in-memory override per persona:scenario:template; resetTemplates() clears it.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const STALE = { code: 'stale_revision', message: 'This template changed. Reload to see the newer version.' };
const DENIED = new Set(['pm', 'none']);
const SCENARIOS = ['desktop', 'mobile', 'readonly', 'empty', 'forbidden', 'many'];
const PAGE_SIZE = 50;
const NOTE_LIMIT = 2000;

const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', path), 'utf8'));
const DATA = Object.fromEntries(['desktop', 'mobile', 'readonly', 'empty', 'many'].map((name) => [name, read(`templates/${name}.json`)]));
const personName = (persona) => read(`me.${persona}.json`).name;

// persona:scenario:template_id -> the fields an upload changed
const overrides = new Map();

export function resetTemplates() {
  overrides.clear();
}

// MOCK_TEMPLATES_SCENARIO sets the default for a whole mock run: the design-fidelity tool scopes its cookies to the
// page's folder (/setup/templates/), so they never reach /api/v1.
const DEFAULT_SCENARIO = SCENARIOS.includes(process.env.MOCK_TEMPLATES_SCENARIO) ? process.env.MOCK_TEMPLATES_SCENARIO : 'desktop';
const scenarioOf = (cookies) => (SCENARIOS.includes(cookies.psl_mock_templates) ? cookies.psl_mock_templates : DEFAULT_SCENARIO);
const dataOf = (scenario) => DATA[scenario === 'forbidden' ? 'desktop' : scenario];

function currentRows(persona, scenario) {
  return dataOf(scenario).items.map((row) => {
    const override = row.template_id ? overrides.get(`${persona}:${scenario}:${row.template_id}`) : undefined;
    return override ? { ...row, ...override } : row;
  });
}

export function templatesList({ url, persona, cookies }) {
  const scenario = scenarioOf(cookies);
  if (DENIED.has(persona) || scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  const rows = currentRows(persona, scenario);
  const match = /^o:(\d+)$/.exec(url.searchParams.get('cursor') ?? '');
  const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
  const body = { items: rows.slice(offset, offset + PAGE_SIZE), as_of: dataOf(scenario).as_of };
  if (offset + PAGE_SIZE < rows.length) body.next_cursor = `o:${offset + PAGE_SIZE}`;
  return { status: 200, body };
}

const invalid = (fields) => ({
  status: 422,
  body: {
    code: 'invalid',
    message: `Check these fields: ${fields.map((f) => f.name).join(', ')}.`,
    fields,
  },
});

const isBase64 = (text) => text.length > 0 && text.length % 4 === 0 && /^[A-Za-z0-9+/]+={0,2}$/.test(text);

function bodyProblems(body) {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return [{ name: 'body', message: 'Send a JSON object.' }];
  const problems = [];
  if (!Number.isInteger(body.expected_revision) || body.expected_revision < 1) problems.push({ name: 'expected_revision', message: 'Send the revision you read.' });
  if (typeof body.filename !== 'string' || body.filename.trim() === '') problems.push({ name: 'filename', message: 'Choose a file.' });
  if (typeof body.content_base64 !== 'string' || !isBase64(body.content_base64)) problems.push({ name: 'content_base64', message: 'The file is empty or could not be read.' });
  if (body.note !== undefined && (typeof body.note !== 'string' || Array.from(body.note).length > NOTE_LIMIT)) {
    problems.push({ name: 'note', message: `The note can be up to ${NOTE_LIMIT} characters.` });
  }
  for (const key of Object.keys(body)) {
    if (!['expected_revision', 'filename', 'content_base64', 'note'].includes(key)) problems.push({ name: key, message: 'Not part of an upload.' });
  }
  return problems;
}

export function templateVersion({ url, raw, persona, cookies }) {
  const scenario = scenarioOf(cookies);
  if (DENIED.has(persona) || scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  const id = decodeURIComponent(url.pathname.split('/')[5] ?? '');
  const rows = currentRows(persona, scenario);
  const row = rows.find((r) => r.template_id === id);
  if (!row) return { status: 404, body: NOT_FOUND };
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid([{ name: 'body', message: 'Send a JSON object.' }]);
  }
  const problems = bodyProblems(body);
  if (problems.length > 0) return invalid(problems);
  const key = `${persona}:${scenario}:${id}`;
  if (cookies.psl_mock_templates_save === 'invalid') {
    return invalid([
      { name: 'filename', message: 'That file type isn’t accepted.' },
      { name: 'note', message: 'The note can’t be saved.' },
    ]);
  }
  if (cookies.psl_mock_templates_save === 'stale') {
    store(key, row, persona);
    return { status: 409, body: STALE };
  }
  if (body.expected_revision !== row.revision) return { status: 409, body: STALE };
  if (row.can_upload !== true) return { status: 403, body: FORBIDDEN };
  const next = store(key, row, persona);
  return { status: 200, body: { template_id: id, version: next.version, test_template: true, revision: next.revision } };
}

function store(key, row, persona) {
  const next = {
    version: String(Number(row.version) + 1),
    versions: (row.versions ?? 0) + 1,
    revision: row.revision + 1,
    updated_at: new Date().toISOString(),
    updated_by: personName(persona),
  };
  overrides.set(key, next);
  return next;
}
