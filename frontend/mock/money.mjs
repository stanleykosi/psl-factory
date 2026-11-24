// F-71: the live money tab (GET /projects/{case_id}/money, with ?figure=<key>) and the one-completion read
// (GET /projects/{case_id}/milestones/{milestone_id}) in the contract mock. A money body comes from
// fixtures/projects/money/<P-nnnn>.json (cookie psl_mock_milestones=changed: <P-nnnn>.changed.json, a change on one stage);
// a completion's proof from fixtures/projects/milestones.json and the milestones fixture it belongs to. Visibility follows
// the persona's rows in fixtures/projects/list.json (else 404, as GET /projects/{case_id}; P-0099 is the no-access id).
// The scripted answers (money P-0107 403 and P-0108 404 in money/index.json) are test cases, not access rules. A case with
// no money fixture keeps the mock's 501. Sample data only.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { demoProject } from './demo-projects.mjs';
import { caseVisible, idOf, uuidOf } from './projects.mjs';
import { DEFAULT_PERSONA, PERSONAS, SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const moneyDir = join(here, 'fixtures', 'projects', 'money');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const moneyBodies = Object.fromEntries(
  readdirSync(moneyDir)
    .filter((name) => /^P-\d+(\.changed)?\.json$/.test(name))
    .map((name) => [name.slice(0, -5), readJson(join(moneyDir, name))]),
);
const moneyIndex = readJson(join(moneyDir, 'index.json'));
const proofs = readJson(join(here, 'fixtures', 'projects', 'milestones.json'));
const milestoneFiles = Object.fromEntries(
  readdirSync(join(here, 'fixtures', 'projects', 'tabs'))
    .filter((name) => /^P-\d+\.milestones\.json$/.test(name))
    .map((name) => [name.slice(0, 6), readJson(join(here, 'fixtures', 'projects', 'tabs', name))]),
);

const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };
const SERVER_ERROR = { code: 'server_error', message: 'Something went wrong on our side.' };

function decodeId(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const parts = (url) => url.pathname.split('/');

/** The requests this module answers: the money tab of E-PROJECT-TAB, and one recorded completion. */
export function isMoneyRequest(operationId, url) {
  return operationId === 'E-PROJECT-TAB' && parts(url)[5] === 'money';
}

/** GET /api/v1/projects/{case_id}/milestones/{milestone_id}; the generic project-tab route does not reach it. */
export const isMilestoneRequest = (url) => /^\/api\/v1\/projects\/[^/]+\/milestones\/[^/]+$/.test(url.pathname);

function scripted(status) {
  return status === 500 ? [500, SERVER_ERROR] : [status, SCENARIO_BODIES[status]];
}

function moneyTab(url, persona, cookies) {
  const caseId = idOf(decodeId(parts(url)[4] ?? ''));
  if (!caseVisible(caseId, persona)) return [404, SCENARIO_BODIES[404]];
  if (moneyIndex[caseId]?.status) return scripted(moneyIndex[caseId].status);
  let body;
  if (demoProject(caseId)) body = { items: [], limited: false, as_of: new Date().toISOString(), finance_url: `/projects/${uuidOf(caseId)}/finance/` }; // D-164: no stages yet
  else body = moneyBodies[cookies.psl_mock_milestones === 'changed' && Object.hasOwn(moneyBodies, `${caseId}.changed`) ? `${caseId}.changed` : caseId];
  if (!body) return [501, NOT_MOCKED];
  if (!url.searchParams.has('figure')) return [200, body];
  const item = body.items.find((i) => i.key === url.searchParams.get('figure'));
  return item ? [200, { ...body, items: [item] }] : [404, SCENARIO_BODIES[404]];
}

function completion(url, persona) {
  const [, , , , rawId = '', , rawMilestone = ''] = parts(url);
  const caseId = idOf(decodeId(rawId));
  if (!caseVisible(caseId, persona)) return [404, SCENARIO_BODIES[404]];
  const found = milestoneFiles[caseId]?.sections[0].items.find((i) => String(i.record_id) === decodeId(rawMilestone));
  const proof = found && Object.hasOwn(proofs, found.record_id) ? proofs[found.record_id] : undefined;
  if (!found || !proof) return [404, SCENARIO_BODIES[404]];
  return [200, { id: found.record_id, name: found.title, completed_at: found.at, ...proof }];
}

/** [status, body]. The scenario cookie or header wins when the operation declares that status, as elsewhere. */
export function moneyRoute({ route, url, req, cookies }) {
  const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
  const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
  if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) return [Number(scenario), SCENARIO_BODIES[scenario]];
  return isMilestoneRequest(url) ? completion(url, persona) : moneyTab(url, persona, cookies);
}
