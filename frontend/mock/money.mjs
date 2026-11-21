// F-26: E-PROJECT-TAB for the money tab and E-REPORT in the contract mock. A money body comes from
// fixtures/projects/money/<case_id>.json and a report from fixtures/reports/<report_id>.json. Visibility follows the
// persona's rows in fixtures/projects/list.json (else 404, as E-PROJECT; P-0099 is the no-access id). The scripted
// answers (money P-0107 403 and P-0108 404 in money/index.json; report R-0103 500 and R-0106 403 in reports/index.json)
// are test cases, not access rules. A case with no money fixture keeps the mock's 501. Sample data only.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { demoProject } from './demo-projects.mjs';
import { caseVisible } from './projects.mjs';
import { DEFAULT_PERSONA, PERSONAS, SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const moneyDir = join(here, 'fixtures', 'projects', 'money');
const reportDir = join(here, 'fixtures', 'reports');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const bodies = (dir, pattern) =>
  Object.fromEntries(
    readdirSync(dir)
      .filter((name) => pattern.test(name))
      .map((name) => [name.slice(0, -5), readJson(join(dir, name))]),
  );

const moneyBodies = bodies(moneyDir, /^P-\d+\.json$/);
const moneyIndex = readJson(join(moneyDir, 'index.json'));
const reportBodies = bodies(reportDir, /^R-\d+\.json$/);
const reportIndex = readJson(join(reportDir, 'index.json'));

const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };
const SERVER_ERROR = { code: 'server_error', message: 'Something went wrong on our side.' };

function decodeId(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The requests this module answers: E-REPORT, and E-PROJECT-TAB for the money tab only. */
export function isMoneyRequest(operationId, url) {
  return operationId === 'E-REPORT' || (operationId === 'E-PROJECT-TAB' && url.pathname.split('/')[5] === 'money');
}

function scripted(status) {
  return status === 500 ? [500, SERVER_ERROR] : [status, SCENARIO_BODIES[status]];
}

function moneyTab(url, persona) {
  const caseId = decodeId(url.pathname.split('/')[4] ?? '');
  if (!caseVisible(caseId, persona)) return [404, SCENARIO_BODIES[404]];
  if (moneyIndex[caseId]?.status) return scripted(moneyIndex[caseId].status);
  if (demoProject(caseId)) return [200, { items: [], as_of: new Date().toISOString(), money: [] }]; // D-164: no stages yet
  return Object.hasOwn(moneyBodies, caseId) ? [200, moneyBodies[caseId]] : [501, NOT_MOCKED];
}

function report(url, persona) {
  const reportId = decodeId(url.pathname.split('/')[4] ?? '');
  const entry = Object.hasOwn(reportIndex, reportId) ? reportIndex[reportId] : undefined;
  if (!entry || !caseVisible(entry.case_id, persona)) return [404, SCENARIO_BODIES[404]];
  if (entry.status) return scripted(entry.status);
  return Object.hasOwn(reportBodies, reportId) ? [200, reportBodies[reportId]] : [404, SCENARIO_BODIES[404]];
}

/** [status, body]. The scenario cookie or header wins when the operation declares that status, as elsewhere. */
export function moneyRoute({ route, url, req, cookies }) {
  const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
  const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
  if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) return [Number(scenario), SCENARIO_BODIES[scenario]];
  return route.operationId === 'E-REPORT' ? report(url, persona) : moneyTab(url, persona);
}
