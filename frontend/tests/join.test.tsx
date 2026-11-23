// @vitest-environment jsdom
// F-60: account set-up from an invitation, against a fetch stub in the live shapes. Tokens are letter repeats, never real.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { JoinView } from '@/features/join/JoinView';
import { NewPasswordFields } from '@/features/sign-in/NewPasswordFields';
import { AppShell } from '@/shell/AppShell';

const nav = vi.hoisted(() => ({ pathname: '/staff/join/', replace: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: nav.replace, push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const TOKEN = 'v'.repeat(43);
const PERSON = { name: 'Sola Martins', email: 'sola.martins@psl.example', expires_at: '2026-11-26T14:00:00Z' };
const ONE = [{ name: 'Ojo Foods', access: 'PMO' }, { name: 'Kora Logistics', access: 'PMO' }];
const UNAVAILABLE = { code: 'invitation_unavailable', message: 'This invitation is unavailable.' };
const GOOD = 'a-long-enough-password';
const session = (token = 'tok-1', signedIn = false) => json(200, { csrf_token: token, signed_in: signedIn, next_url: '/' });

type Handler = (request: Request) => Response | Promise<Response>;
let routes: Record<string, Handler>;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let storageSpy: ReturnType<typeof vi.spyOn>[];
const PREVIEW = 'POST /api/v1/accounts/invitations/preview';
const ACCEPT = 'POST /api/v1/accounts/invitations/accept';
const calls = (key: string) => fetchStub.mock.calls.map(([r]) => r).filter((r) => `${r.method} ${new URL(r.url).pathname}` === key);
const bodyOf = async (request: Request) => JSON.parse(await request.clone().text()) as Record<string, unknown>;

function open(hash: string | null = TOKEN) {
  window.history.replaceState(null, '', `/staff/join/${hash === null ? '' : `#${hash}`}`);
  return render(
    <AppShell>
      <JoinView />
    </AppShell>,
  );
}
const welcome = () => document.querySelector('.join-welcome')!.textContent;
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const formReady = () => screen.findByRole('button', { name: 'Finish setup' });
async function fill(password = GOOD, confirm = password) {
  await formReady();
  fireEvent.change(field('New password'), { target: { value: password } });
  fireEvent.change(field('Confirm new password'), { target: { value: confirm } });
}
const press = () => fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));

beforeEach(() => {
  nav.pathname = '/staff/join/';
  nav.replace.mockReset();
  setCsrfToken(null);
  routes = {
    'GET /api/v1/session': () => session(),
    [PREVIEW]: () => json(200, { ...PERSON, workspaces: ONE }),
    [ACCEPT]: () => json(201, { complete: true, next_url: '/sign-in' }),
    'GET /api/v1/me/onboarding': () => json(200, { admitted: true, can_create_workspace: false, next_url: '/' }),
    'POST /api/v1/session/logout': () => json(200, { csrf_token: 'out-2', signed_in: false, next_url: '/accounts/login/' }),
  };
  fetchStub = vi.fn(async (request: Request) => {
    const handler = routes[`${request.method} ${new URL(request.url).pathname}`];
    return handler ? handler(request) : json(404, { code: 'not_found', message: 'No.' });
  });
  vi.stubGlobal('fetch', fetchStub);
  storageSpy = [vi.spyOn(Storage.prototype, 'setItem')];
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('page and token', () => {
  it('makes only the session read and the preview: no /me, no bars', async () => {
    open();
    await formReady();
    expect(fetchStub.mock.calls.map(([r]) => `${r.method} ${new URL(r.url).pathname}`)).toEqual(['GET /api/v1/session', PREVIEW]);
    expect(document.querySelector('nav.psl-nav')).toBeNull();
    expect(document.querySelector('header.psl-phonebar')).toBeNull();
    expect(screen.queryByRole('link', { name: 'My work' })).toBeNull();
  });

  it('clears the fragment, and the token is in no URL, storage or console output; it is sent only in the two bodies', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) => vi.spyOn(console, m));
    const replace = vi.spyOn(window.history, 'replaceState');
    open();
    await fill();
    expect(window.location.hash).toBe('');
    expect(window.location.pathname + window.location.search).toBe('/staff/join/');
    expect(replace).toHaveBeenCalledWith(null, '', '/staff/join/');
    press();
    await screen.findByRole('heading', { name: 'Your account is ready.' });
    for (const request of fetchStub.mock.calls.map(([r]) => r)) expect(request.url).not.toContain(TOKEN);
    expect((await bodyOf(calls(PREVIEW)[0])).token).toBe(TOKEN);
    expect((await bodyOf(calls(ACCEPT)[0])).token).toBe(TOKEN);
    expect(storageSpy[0]).not.toHaveBeenCalled();
    expect(JSON.stringify({ ...window.localStorage })).not.toContain(TOKEN);
    expect(JSON.stringify({ ...window.sessionStorage })).not.toContain(TOKEN);
    expect(document.cookie).not.toContain(TOKEN);
    expect(JSON.stringify(spies.map((s) => s.mock.calls))).not.toContain(TOKEN);
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it.each([
    ['no fragment', null],
    ['an empty fragment', ''],
    ['a short value', 'v'.repeat(42)],
    ['a long value', 'v'.repeat(44)],
    ['other characters', `${'v'.repeat(42)}+`],
    ['a space', `${'v'.repeat(42)} `],
    ['a query-like value', `token=${'v'.repeat(37)}`],
  ])('%s shows the unavailable state and sends no request', async (_name, hash) => {
    open(hash);
    expect(await screen.findByText('This invitation can’t be used')).toBeTruthy();
    expect(fetchStub).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('New password')).toBeNull();
  });

  it('the page route sets no-referrer through its metadata', async () => {
    const source = readFileSync(join(__dirname, '../src/app/staff/join/page.tsx'), 'utf8');
    expect(source).toContain("referrer: 'no-referrer'");
    expect(source).toContain("title: 'Set up your account'");
  });
});

describe('the set-up form', () => {
  it('shows the welcome line, the dated validity line, a read-only email and the hint under New password', async () => {
    open();
    await formReady();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Set up your account');
    expect(welcome()).toBe('Welcome, Sola Martins. You’ve been given PMO for Ojo Foods and Kora Logistics.');
    expect(screen.getByText('This invitation works until 26 Nov 2026, 15:00.')).toBeTruthy();
    const email = field('Work email');
    expect(email.readOnly).toBe(true);
    expect(email.disabled).toBe(false);
    expect(email.value).toBe(PERSON.email);
    expect(email.autocomplete).toBe('username');
    expect(field('New password').type).toBe('password');
    expect(field('New password').autocomplete).toBe('new-password');
    expect(field('Confirm new password').autocomplete).toBe('new-password');
    expect(field('New password').maxLength).toBe(128);
    const hint = screen.getByText('At least 12 characters');
    expect(field('New password').getAttribute('aria-describedby')).toBe(hint.id);
    expect(document.body.textContent).not.toMatch(/72 hours|WhatsApp|code to check/);
    expect(document.querySelector('form')!.getAttribute('method')).toBe('post');
    expect(screen.getByText('Wrong roles? Ask the person who invited you; you can’t change your own roles.')).toBeTruthy();
  });

  it('two access groups read as two sentences', async () => {
    routes[PREVIEW] = () => json(200, { ...PERSON, workspaces: [{ name: 'Ojo Foods', access: 'PMO' }, { name: 'Kora Logistics', access: 'Finance Lead' }] });
    open();
    await formReady();
    expect(welcome()).toBe('Welcome, Sola Martins. You’ve been given PMO for Ojo Foods. You’ve also been given Finance Lead for Kora Logistics.');
  });

  it('three workspaces of one access read "A, B and C"', async () => {
    routes[PREVIEW] = () => json(200, { ...PERSON, workspaces: ['A', 'B', 'C'].map((name) => ({ name, access: 'PMO' })) });
    open();
    await formReady();
    expect(welcome()).toBe('Welcome, Sola Martins. You’ve been given PMO for A, B and C.');
  });

  it('shows name, access and workspace values as text, never as markup', async () => {
    routes[PREVIEW] = () => json(200, { ...PERSON, name: '<b>x</b>', workspaces: [{ name: '<i>w</i>', access: '<u>a</u>' }] });
    open();
    await formReady();
    expect(welcome()).toBe('Welcome, <b>x</b>. You’ve been given <u>a</u> for <i>w</i>.');
    expect(document.querySelector('main b, main i, main u')).toBeNull();
  });

  it('expired and used invitations show the identical text and link, without saying which', async () => {
    routes[PREVIEW] = () => json(422, UNAVAILABLE);
    const first = open();
    await screen.findByText('This invitation can’t be used');
    const snapshot = document.querySelector('main')!.innerHTML.replace(/id="[^"]*"/g, '');
    first.unmount();
    routes[PREVIEW] = () => json(422, { ...UNAVAILABLE, message: 'something else' });
    open('u'.repeat(43));
    await screen.findByText('This invitation can’t be used');
    expect(document.querySelector('main')!.innerHTML.replace(/id="[^"]*"/g, '')).toBe(snapshot);
    expect(screen.getByText('It may have expired or already been used. Ask the person who invited you to send a new one.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Already set up? Sign in' }).getAttribute('href')).toBe('/sign-in');
    expect(document.body.textContent).not.toContain(PERSON.name);
    expect(document.body.textContent).not.toContain(PERSON.email);
    expect(screen.queryByLabelText('New password')).toBeNull();
  });

  it.each([
    ['429', () => json(429, { code: 'rate_limited', message: 'x' })],
    ['503', () => json(503, { code: 'unavailable', message: 'x' })],
    ['500', () => json(500, { code: 'server_error', message: 'x' })],
    ['network', () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('a %s on the preview shows "We couldn’t open your invitation" and Try again recovers with the token held', async (_name, fail) => {
    let broken = true;
    routes[PREVIEW] = () => (broken ? fail() : json(200, { ...PERSON, workspaces: ONE }));
    open();
    expect(await screen.findByText('We couldn’t open your invitation. Nothing was changed.')).toBeTruthy();
    expect(screen.queryByLabelText('New password')).toBeNull();
    broken = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await formReady();
    expect(await Promise.all(calls(PREVIEW).map(async (r) => (await bodyOf(r)).token))).toEqual([TOKEN, TOKEN]);
  });

  it('a failed session read is the same state', async () => {
    routes['GET /api/v1/session'] = () => json(503, { code: 'unavailable', message: 'x' });
    open();
    expect(await screen.findByText('We couldn’t open your invitation. Nothing was changed.')).toBeTruthy();
    expect(calls(PREVIEW)).toHaveLength(0);
  });
});

describe('submitting', () => {
  it('empty, empty again and mismatch show their messages, focus the right field and send nothing', async () => {
    open();
    await formReady();
    press();
    expect(await screen.findByText('Enter a new password.')).toBeTruthy();
    expect(document.activeElement).toBe(field('New password'));
    fireEvent.change(field('New password'), { target: { value: 'abc' } });
    press();
    expect(await screen.findByText('Enter the new password again.')).toBeTruthy();
    expect(document.activeElement).toBe(field('Confirm new password'));
    fireEvent.change(field('Confirm new password'), { target: { value: 'abd' } });
    press();
    expect(await screen.findByText('The two passwords don’t match.')).toBeTruthy();
    expect(document.activeElement).toBe(field('Confirm new password'));
    expect(calls(ACCEPT)).toHaveLength(0);
  });

  it('sends exactly token, password and confirm with the token from the last session read; a short password is the server’s to refuse', async () => {
    routes['GET /api/v1/session'] = () => session('tok-xyz');
    open();
    await fill('short', 'short');
    press();
    await screen.findByRole('heading', { name: 'Your account is ready.' });
    const [request] = calls(ACCEPT);
    expect(await bodyOf(request)).toEqual({ token: TOKEN, password: 'short', confirm: 'short' });
    expect(request.headers.get('X-CSRFToken')).toBe('tok-xyz');
  });

  it('422 invalid_input with fields shows each message under its field and clears both', async () => {
    routes[ACCEPT] = () => json(422, { code: 'invalid_input', message: 'x', fields: [{ name: 'password', message: 'Server says P.' }, { name: 'confirm', message: 'Server says C.' }] });
    open();
    await fill();
    press();
    expect(await screen.findByText('Server says P.')).toBeTruthy();
    expect(screen.getByText('Server says C.')).toBeTruthy();
    expect(field('New password').value).toBe('');
    expect(field('Confirm new password').value).toBe('');
    expect(field('Work email').value).toBe(PERSON.email);
  });

  it('a field the page does not know goes into the callout', async () => {
    routes[ACCEPT] = () => json(422, { code: 'invalid_input', message: 'x', fields: [{ name: 'token', message: 'Odd token.' }] });
    open();
    await fill();
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('Odd token.');
  });

  it('422 invalid_input without fields shows the server message in the callout', async () => {
    routes[ACCEPT] = () => json(422, { code: 'invalid_input', message: 'The passwords differ.' });
    open();
    await fill();
    press();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('The passwords differ.');
    await waitFor(() => expect(document.activeElement).toBe(alert));
  });

  it('422 action_unavailable shows the server text, rechecks the preview, and the form stays when the invitation is still valid', async () => {
    routes[ACCEPT] = () => json(422, { code: 'action_unavailable', message: 'This password is too short. It must contain at least 12 characters.' });
    open();
    await fill('short', 'short');
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('This password is too short. It must contain at least 12 characters.');
    await waitFor(() => expect(calls(PREVIEW)).toHaveLength(2));
    expect(await bodyOf(calls(PREVIEW)[1])).toEqual({ token: TOKEN });
    expect(screen.getByRole('button', { name: 'Finish setup' })).toBeTruthy();
    expect(field('New password').value).toBe('');
  });

  it('the renewed fixture lands in the unavailable state after the recheck', async () => {
    let renewed = false;
    routes[PREVIEW] = () => (renewed ? json(422, UNAVAILABLE) : json(200, { ...PERSON, workspaces: ONE }));
    routes[ACCEPT] = () => {
      renewed = true;
      return json(422, { code: 'action_unavailable', message: 'This invitation is unavailable.' });
    };
    open();
    await fill();
    press();
    expect(await screen.findByText('This invitation can’t be used')).toBeTruthy();
    expect(screen.queryByLabelText('New password')).toBeNull();
  });

  it('an accept that answers invitation_unavailable goes straight to the unavailable state', async () => {
    routes[ACCEPT] = () => json(422, UNAVAILABLE);
    open();
    await fill();
    press();
    expect(await screen.findByText('This invitation can’t be used')).toBeTruthy();
    expect(calls(PREVIEW)).toHaveLength(1);
  });

  it('a csrf_failed is retried once with the same body and a fresh token, then the ready state shows', async () => {
    let n = 0;
    routes['GET /api/v1/session'] = () => session(`tok-${++n}`);
    let accepts = 0;
    routes[ACCEPT] = () => (++accepts === 1 ? json(403, { code: 'csrf_failed', message: 'x' }) : json(201, { complete: true, next_url: '/sign-in' }));
    open();
    await fill();
    press();
    await screen.findByRole('heading', { name: 'Your account is ready.' });
    const sent = calls(ACCEPT);
    expect(sent).toHaveLength(2);
    expect(await bodyOf(sent[0])).toEqual(await bodyOf(sent[1]));
    expect(sent[0].headers.get('X-CSRFToken')).not.toBe(sent[1].headers.get('X-CSRFToken'));
  });

  it('two csrf_failed in a row show "Press Finish setup again" and keep the form', async () => {
    routes[ACCEPT] = () => json(403, { code: 'csrf_failed', message: 'x' });
    open();
    await fill();
    press();
    expect(await screen.findByText('Your session was refreshed. Press Finish setup again. Nothing was changed.')).toBeTruthy();
    expect(calls(ACCEPT)).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Finish setup' })).toBeTruthy();
  });

  it.each([
    ['429', () => json(429, { code: 'rate_limited', message: 'x' }), 'Too many tries. Try again later.', false],
    ['500', () => json(500, { code: 'server_error', message: 'x' }), 'Set-up isn’t working right now. Try again in a moment. Nothing was changed.', true],
    ['503', () => json(503, { code: 'unavailable', message: 'x' }), 'Set-up isn’t working right now. Try again in a moment. Nothing was changed.', true],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'We could not reach PSL Factory. Check your connection and try again.', true],
  ])('%s shows the fixed wording, clears both fields and keeps the email', async (_name, fail, text, signInLine) => {
    routes[ACCEPT] = fail;
    open();
    await fill();
    press();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(text);
    expect(alert.textContent?.includes('try signing in; your account may already be set up.')).toBe(signInLine);
    expect(field('New password').value).toBe('');
    expect(field('Confirm new password').value).toBe('');
    expect(field('Work email').value).toBe(PERSON.email);
    expect(calls(ACCEPT)).toHaveLength(1);
  });

  it('ignores a second press while busy', async () => {
    let release!: (r: Response) => void;
    routes[ACCEPT] = () => new Promise<Response>((resolve) => (release = resolve));
    open();
    await fill();
    press();
    await waitFor(() => expect(release).toBeTypeOf('function'));
    fireEvent.submit(document.querySelector('form')!);
    expect(calls(ACCEPT)).toHaveLength(1);
    release(json(201, { complete: true, next_url: '/sign-in' }));
    await screen.findByRole('heading', { name: 'Your account is ready.' });
  });
});

describe('after set-up', () => {
  it('shows a plain heading (focused), the email line and a Sign in link to exactly /sign-in; no callout, no further /me read', async () => {
    open();
    await fill();
    press();
    const heading = await screen.findByRole('heading', { name: 'Your account is ready.' });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(screen.getByText('Sign in with sola.martins@psl.example.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in');
    expect(document.querySelector('.psl-callout')).toBeNull();
    expect(calls('GET /api/v1/me/onboarding')).toHaveLength(0);
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it('the Sign in link follows a safe next_url and ignores a foreign one', async () => {
    routes[ACCEPT] = () => json(201, { complete: true, next_url: '/sign-in?next=%2Fsettings%2Falerts' });
    open();
    await fill();
    press();
    await screen.findByRole('heading', { name: 'Your account is ready.' });
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fsettings%2Falerts');
  });

  it('a signed-in session after accept runs the onboarding path: admitted goes to the safe next_url', async () => {
    routes['GET /api/v1/session'] = (() => {
      let n = 0;
      return () => session('t', ++n > 1);
    })();
    routes[ACCEPT] = () => json(201, { complete: true, next_url: '/settings/alerts' });
    open();
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/settings/alerts'));
  });

  it.each(['https://evil.example', '/accounts/login/', '//evil.example'])('a signed-in session never follows next_url %s', async (nextUrl) => {
    routes['GET /api/v1/session'] = (() => {
      let n = 0;
      return () => session('t', ++n > 1);
    })();
    routes[ACCEPT] = () => json(201, { complete: true, next_url: nextUrl });
    open();
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/'));
  });

  it('a signed-in session with no work open shows the not-admitted notice with a working Sign out', async () => {
    routes['GET /api/v1/session'] = (() => {
      let n = 0;
      return () => session('t', ++n > 1);
    })();
    routes['GET /api/v1/me/onboarding'] = () => json(200, { admitted: false, can_create_workspace: false, next_url: '/getting-started/' });
    open();
    await fill();
    press();
    expect(await screen.findByText('You’re signed in, but no work is open to you yet. Ask your administrator.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/sign-in'));
    expect(calls('POST /api/v1/session/logout')).toHaveLength(1);
  });
});

describe('the shared password fields', () => {
  it('render no hint when none is passed, and the hint once when one is', () => {
    const props = { password: '', confirm: '', onPassword: () => undefined, onConfirm: () => undefined };
    const { unmount } = render(<NewPasswordFields {...props} />);
    expect(document.querySelector('.psl-hint')).toBeNull();
    expect(field('New password').getAttribute('aria-describedby')).toBeNull();
    unmount();
    render(<NewPasswordFields {...props} hint="At least 12 characters" />);
    expect(screen.getAllByText('At least 12 characters')).toHaveLength(1);
  });
});

describe('the code', () => {
  it('has no password-length check, no duration, no WhatsApp and no review_alerts in the join feature', () => {
    const dir = join(__dirname, '../src/features/join');
    const sources = ['JoinView.tsx', 'signInTarget.ts', 'welcome.ts'].map((f) => readFileSync(join(dir, f), 'utf8')).join('\n');
    expect(sources).not.toMatch(/72 hours|WhatsApp|review_alerts|password\.length|confirm\.length/);
    expect(readFileSync(join(__dirname, '../src/features/sign-in/NewPasswordFields.tsx'), 'utf8')).not.toMatch(/\.length/);
  });

  it('the page is not proxied to Django', () => {
    expect(readFileSync(join(__dirname, '../next.config.ts'), 'utf8')).not.toContain('staff/join');
  });
});
