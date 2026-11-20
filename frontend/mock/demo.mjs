// Live demo mode of the mock (D-155). Local use only: the design engineer clicks through every flow and sees loading
// times, agent work and results.
//
// Switches: env MOCK_DEMO=1 (the dev script sets it) turns the demo on; cookie psl_mock_demo (on | off) overrides it per
// browser. With the demo off nothing is slowed and no line or assistant run happens. Speed: cookie psl_mock_speed
// (fast | normal | slow), default normal when the demo is on and fast when it is off, so tests and e2e wait for nothing.
// Delay: a read waits about 0.3-1.2 s, a write or upload about 0.8-2 s (a little random), times 1 (normal) or 2.5 (slow).
export const SPEEDS = { fast: 0, normal: 1, slow: 2.5 };
export const DEMO_COOKIE = 'psl_mock_demo';
export const SPEED_COOKIE = 'psl_mock_speed';

const READ_MS = [300, 1200];
const WRITE_MS = [800, 2000];

/** True when the demo is on for this request. */
export function demoOn(cookies, env = process.env) {
  if (cookies[DEMO_COOKIE] === 'on') return true;
  if (cookies[DEMO_COOKIE] === 'off') return false;
  return env.MOCK_DEMO === '1';
}

/** fast | normal | slow for this request. */
export function speedOf(cookies, env = process.env) {
  if (Object.hasOwn(SPEEDS, cookies[SPEED_COOKIE])) return cookies[SPEED_COOKIE];
  return demoOn(cookies, env) ? 'normal' : 'fast';
}

/** How long this request waits before it answers, in milliseconds. */
export function delayMs(method, cookies, { env = process.env, random = Math.random } = {}) {
  const [low, high] = method === 'get' ? READ_MS : WRITE_MS;
  return Math.round((low + random() * (high - low)) * SPEEDS[speedOf(cookies, env)]);
}

/** Holds back the answer: the request is handled now, so state changes in order; only the reply is late. */
export function delayReply(res, ms) {
  if (ms <= 0) return;
  const end = res.end.bind(res);
  res.end = (...args) => {
    setTimeout(() => end(...args), ms);
    return res;
  };
}
