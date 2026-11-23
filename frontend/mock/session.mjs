// Live-contract reads the frame makes beside GET /me (contracts/psl-factory.openapi.json): GET /api/v1/session and
// GET /api/v1/role-dashboard. Not in v7, so they are answered here, per persona. Scenario 401 signs the session out.
// F-58: POST /api/v1/session (sign in), POST /api/v1/session/logout and GET /api/v1/me/onboarding, in the live shapes.
// The session state lives in the cookie psl_mock_session ("in" by default, "out" after a logout); while it is "out"
// every authenticated read answers 401. Tokens: signed out "mock-csrf-signed-out" (scenario 401), after a logout
// "mock-csrf-signed-out-2", signed in the persona's own; a write with any other token gets 403 csrf_failed.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

export const SESSION_PATH = '/api/v1/session';
export const ROLE_DASHBOARD_PATH = '/api/v1/role-dashboard';

export const LOGOUT_PATH = '/api/v1/session/logout';
export const ONBOARDING_PATH = '/api/v1/me/onboarding';
export const SESSION_COOKIE = 'psl_mock_session';

/** A sample sign-in the mock accepts. A sample only, never real credentials. */
const SAMPLE_USERNAME = 'sample.user';
const SAMPLE_PASSWORD = 'sample-password';

const SIGNED_OUT_TOKEN = 'mock-csrf-signed-out';
const LOGGED_OUT_TOKEN = 'mock-csrf-signed-out-2';
const NOT_SIGNED_IN = { code: 'not_signed_in', message: 'Sign in to continue.' };
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
// Scenario cookies a sign-in or sign-out answers with (the others do not apply to a write that has no record).
const SCENARIO_ERRORS = {
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'Not available right now.' },
};

/** True while the person is signed out: after a logout (cookie) or under scenario 401. */
export const signedOut = ({ cookies, scenario }) => cookies[SESSION_COOKIE] === 'out' || String(scenario) === '401';

/** The token a write must carry now, as GET /session last gave it. */
function currentToken({ cookies, scenario, me }) {
  if (cookies[SESSION_COOKIE] === 'out') return LOGGED_OUT_TOKEN;
  return String(scenario) === '401' ? SIGNED_OUT_TOKEN : me.csrf_token;
}

export function sessionRoute({ cookies, scenario, me }) {
  const token = currentToken({ cookies, scenario, me });
  return [200, { csrf_token: token, signed_in: !signedOut({ cookies, scenario }), next_url: '/' }];
}

const setCookie = (value) => ({ 'Set-Cookie': `${SESSION_COOKIE}=${value}; Path=/; SameSite=Lax` });

/** Reply to a write: [status, body, extra headers]. Scenario errors first, then the token check, as the live API does. */
function guarded({ cookies, scenario, me, token }, run) {
  if (SCENARIO_ERRORS[scenario]) return [Number(scenario), SCENARIO_ERRORS[scenario]];
  if (token !== currentToken({ cookies, scenario, me })) return [403, CSRF_FAILED];
  return run();
}

const invalidInput = (fields) => [422, { code: 'invalid_input', message: 'Check the details and try again.', fields: fields.map((name) => ({ name, message: 'Check this field.' })) }];

/** POST /api/v1/session: the sample pair signs in; any other pair is one 422 sign_in_failed with no field. */
export function signInRoute({ raw, ...ctx }) {
  return guarded(ctx, () => {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return invalidInput(['body']);
    }
    const text = (value) => typeof value === 'string' && value !== '';
    const bad = [];
    if (typeof body !== 'object' || body === null || Array.isArray(body)) return invalidInput(['body']);
    for (const key of Object.keys(body)) if (!['username', 'password', 'remember', 'next_url'].includes(key)) bad.push(key);
    if (!text(body.username)) bad.push('username');
    if (!text(body.password)) bad.push('password');
    if (body.remember !== undefined && typeof body.remember !== 'boolean') bad.push('remember');
    if (body.next_url !== undefined && !text(body.next_url)) bad.push('next_url');
    if (bad.length > 0) return invalidInput(bad);
    if (body.username !== SAMPLE_USERNAME || body.password !== SAMPLE_PASSWORD) return [422, { code: 'sign_in_failed', message: 'Check the sign-in details.' }];
    const next = typeof body.next_url === 'string' && body.next_url.startsWith('/') && !body.next_url.startsWith('//') ? body.next_url : '/';
    return [200, { csrf_token: ctx.me.csrf_token, signed_in: true, next_url: next }, setCookie('in')];
  });
}

/** POST /api/v1/session/logout: the session ends and the token rotates. */
export function logoutRoute({ raw, ...ctx }) {
  return guarded(ctx, () => {
    let body;
    try {
      body = JSON.parse(raw || '{}');
    } catch {
      return invalidInput(['body']);
    }
    if (typeof body !== 'object' || body === null || Array.isArray(body) || Object.keys(body).length > 0) return invalidInput(['body']);
    return [200, { csrf_token: LOGGED_OUT_TOKEN, signed_in: false, next_url: '/accounts/login/' }, setCookie('out')];
  });
}

/** GET /api/v1/me/onboarding: persona none has no team and no work. */
export function onboardingRoute({ persona }) {
  if (persona === 'none') return [200, { admitted: false, can_create_workspace: false, next_url: '/getting-started/' }];
  return [200, { admitted: true, can_create_workspace: false, next_url: '/' }];
}

export const SIGNED_OUT_REPLY = [401, NOT_SIGNED_IN];

const dashboardOf = (persona) => JSON.parse(readFileSync(join(here, 'fixtures', `role-dashboard.${persona}.json`), 'utf8'));

export function roleDashboardRoute({ persona }) {
  return [200, dashboardOf(persona)];
}

/** The persona's role words as the bar shows them (its first position); persona none has none, and mock records call it "Staff". */
export function roleWords(persona) {
  return dashboardOf(persona).positions[0]?.name ?? 'Staff';
}
