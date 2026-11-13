// Local contract mock for /api/v1. Routes come from the reviewed openapi.json; M-1
// operations answer with sample fixtures, everything else answers 501. Local use only.
//
// Persona: cookie psl_mock_persona (finance_lead | pm | none; default finance_lead).
// Scenario: cookie psl_mock_scenario or header X-Mock-Scenario (401 | 403 | 404 | 409 | 422),
// applied only when the operation declares that status.
import { readFileSync } from 'node:fs';
import http from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const OPENAPI_PATH = join(here, '..', '..', 'architecture', 'packages', 'v2-reviewed', 'openapi.json');

export const M1_OPERATIONS = ['E-ME', 'E-WORK-LIST', 'E-WORK-ITEM', 'E-WORK-HISTORY', 'E-TASK-CLAIM', 'E-TASK-DECIDE'];
export const PERSONAS = ['finance_lead', 'pm', 'none'];
export const DEFAULT_PERSONA = 'finance_lead';
const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete']);

export const SCENARIO_BODIES = {
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'We could not find that record.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' },
  422: { code: 'invalid', message: 'Check the highlighted fields and try again.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };
const NO_ROUTE = { code: 'not_found', message: 'We could not find that record.' };

function readFixture(name) {
  return JSON.parse(readFileSync(join(here, 'fixtures', `${name}.json`), 'utf8'));
}

export function loadRoutes(openapi) {
  const routes = [];
  for (const [template, ops] of Object.entries(openapi.paths)) {
    const pattern = new RegExp(
      '^' + template.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{[^}]+\}/g, '[^/]+') + '$',
    );
    for (const [method, op] of Object.entries(ops)) {
      if (!op || typeof op !== 'object' || !op.operationId) continue;
      routes.push({ method, template, pattern, operationId: op.operationId, statuses: Object.keys(op.responses) });
    }
  }
  return routes;
}

function parseCookies(header = '') {
  const cookies = {};
  for (const part of header.split(';')) {
    const eq = part.indexOf('=');
    if (eq > 0) cookies[part.slice(0, eq).trim()] = decodeCookie(part.slice(eq + 1).trim());
  }
  return cookies;
}

// A malformed value such as `%` keeps its raw text instead of crashing the mock.
function decodeCookie(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function send(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(text);
}

export function createMockServer(openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'))) {
  const routes = loadRoutes(openapi);
  const me = Object.fromEntries(PERSONAS.map((p) => [p, readFixture(`me.${p}`)]));
  const fixtures = Object.fromEntries(M1_OPERATIONS.filter((id) => id !== 'E-ME').map((id) => [id, readFixture(id)]));

  return http.createServer((req, res) => {
    // Drain any request body; the mock answers from fixtures only.
    req.resume();
    req.on('end', () => {
      const url = new URL(req.url ?? '/', 'http://mock.local');
      const method = (req.method ?? 'GET').toLowerCase();
      const route = routes.find((r) => r.method === method && r.pattern.test(url.pathname));
      if (!route) return send(res, 404, NO_ROUTE);
      if (!M1_OPERATIONS.includes(route.operationId)) return send(res, 501, NOT_MOCKED);

      const cookies = parseCookies(req.headers.cookie);
      const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
      const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
      if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) {
        return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
      }
      if (WRITE_METHODS.has(method) && req.headers['x-csrftoken'] !== me[persona].csrf_token) {
        return send(res, 403, CSRF_FAILED);
      }
      if (route.operationId === 'E-ME') return send(res, 200, me[persona]);
      return send(res, 200, fixtures[route.operationId]);
    });
  });
}

export function startMockServer({ port = Number(process.env.MOCK_PORT ?? 4010) } = {}) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('The mock API refuses to start with NODE_ENV=production.');
  }
  const server = createMockServer();
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const server = await startMockServer();
    const { port } = server.address();
    console.log(`Mock API (sample data) on http://127.0.0.1:${port}/api/v1`);
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
