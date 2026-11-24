// F-60: POST /api/v1/accounts/invitations/preview and /accept in the live shapes. Neither needs a signed-in person; both need
// the current CSRF token. Tokens are 43-character fixtures (letter repeats), never real credentials.
//   'v' valid, one access group   'm' valid, two access groups   'e' expired   'u' used   'r' renewed between preview and accept
// A token that is accepted becomes used until the mock is reset.
const SHAPE = /^[A-Za-z0-9_-]{43}$/;
const UNAVAILABLE = { code: 'invitation_unavailable', message: 'This invitation is unavailable.' };
const SCENARIO_ERRORS = {
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'Not available right now.' },
};
const PERSON = { name: 'Sola Martins', email: 'sola.martins@psl.example', expires_at: '2026-11-26T14:00:00Z' };
const ONE = [{ name: 'Ojo Foods', access: 'PMO' }, { name: 'Kora Logistics', access: 'PMO' }];
const TWO = [{ name: 'Ojo Foods', access: 'PMO' }, { name: 'Kora Logistics', access: 'Finance Lead' }];

export const INVITATION_PATHS = ['/api/v1/accounts/invitations/preview', '/api/v1/accounts/invitations/accept'];

const used = new Set();
export const resetInvitations = () => used.clear();

const invalidInput = (names) => [422, { code: 'invalid_input', message: 'Check the details and try again.', fields: names.map((name) => ({ name, message: 'Check this field.' })) }];
const text = (value, max = 128) => typeof value === 'string' && value.length >= 1 && value.length <= max;

function previewOf(token) {
  if (used.has(token)) return null;
  if (token[0] === 'v' || token[0] === 'r') return { ...PERSON, workspaces: ONE };
  if (token[0] === 'm') return { ...PERSON, workspaces: TWO };
  return null;
}

/** Reply to a write: [status, body]. Scenario errors first, then the token check, then the body. */
export function invitationRoute({ path, raw, scenario, expectedToken, token }) {
  if (SCENARIO_ERRORS[scenario]) return [Number(scenario), SCENARIO_ERRORS[scenario]];
  if (token !== expectedToken) return [403, { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' }];
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalidInput(['body']);
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return invalidInput(['body']);
  const accept = path.endsWith('/accept');
  const allowed = accept ? ['token', 'password', 'confirm'] : ['token'];
  const bad = Object.keys(body).filter((key) => !allowed.includes(key));
  if (typeof body.token !== 'string' || !SHAPE.test(body.token)) bad.push('token');
  if (accept) {
    if (!text(body.password)) bad.push('password');
    if (!text(body.confirm)) bad.push('confirm');
  }
  if (bad.length > 0) return invalidInput(bad);
  const found = previewOf(body.token);
  if (!accept) return found ? [200, found] : [422, UNAVAILABLE];
  if (!found) return [422, UNAVAILABLE];
  if (body.password !== body.confirm) return [422, { code: 'invalid_input', message: 'The passwords differ.' }];
  if (body.password.length < 12) return [422, { code: 'action_unavailable', message: 'This password is too short. It must contain at least 12 characters.' }];
  if (body.password === 'password1234') return [422, { code: 'action_unavailable', message: 'This password is too common.' }];
  // The renewed link: the invitation was replaced after the preview, so this accept and every later preview fail.
  if (body.token[0] === 'r') {
    used.add(body.token);
    return [422, { code: 'action_unavailable', message: 'This invitation is unavailable.' }];
  }
  used.add(body.token);
  return [201, { complete: true, next_url: '/sign-in' }];
}
