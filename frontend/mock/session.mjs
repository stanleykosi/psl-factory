// Live-contract reads the frame makes beside GET /me (contracts/psl-factory.openapi.json): GET /api/v1/session and
// GET /api/v1/role-dashboard. Not in v7, so they are answered here, per persona. Scenario 401 signs the session out.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

export const SESSION_PATH = '/api/v1/session';
export const ROLE_DASHBOARD_PATH = '/api/v1/role-dashboard';

export function sessionRoute({ scenario, me }) {
  if (String(scenario) === '401') return [200, { csrf_token: 'mock-csrf-signed-out', signed_in: false, next_url: '/' }];
  return [200, { csrf_token: me.csrf_token, signed_in: true, next_url: '/' }];
}

const dashboardOf = (persona) => JSON.parse(readFileSync(join(here, 'fixtures', `role-dashboard.${persona}.json`), 'utf8'));

export function roleDashboardRoute({ persona }) {
  return [200, dashboardOf(persona)];
}

/** The persona's role words as the bar shows them (its first position); persona none has none, and mock records call it "Staff". */
export function roleWords(persona) {
  return dashboardOf(persona).positions[0]?.name ?? 'Staff';
}
