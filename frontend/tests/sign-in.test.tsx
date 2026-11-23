// @vitest-environment jsdom
// F-58: the sign-in page, the account menu's sign-out and the public branch of the shell.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { call, liveApi, setCsrfToken } from '@/api/client';
import { SignInView } from '@/features/sign-in/SignInView';
import { AppShell } from '@/shell/AppShell';

import { bellFeed, isBellFeed } from './bell-feed';

const nav = vi.hoisted(() => ({ pathname: '/sign-in', replace: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: nav.replace, push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const FAILED = { code: 'sign_in_failed', message: 'Check the sign-in details.' };
const csrf = { code: 'csrf_failed', message: 'SERVER TEXT about the token' };
const signedOut = (token = 'out-1') => json(200, { csrf_token: token, signed_in: false, next_url: '/accounts/login/' });
const me = { ...JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8')), csrf_token: 't' };
const dashboard = { positions: [{ name: 'PMO Lead' }], actions: [], decisions: [], team_decisions: [], limited: false, workspace_decisions: [], approval_desks: [], has_teams: false, page: 1, has_next: false, as_of: '2026-11-23T09:00:00Z' };

type Handler = (request: Request) => Response | Promise<Response>;
let routes: Record<string, Handler>;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const calls = (method: string, path: string) => fetchStub.mock.calls.map(([r]) => r).filter((r) => r.method === method && new URL(r.url).pathname === path);
const posts = () => calls('POST', '/api/v1/session');
const bodyOf = async (request: Request) => JSON.parse(await request.clone().text()) as Record<string, unknown>;

beforeEach(() => {
  nav.pathname = '/sign-in';
  nav.replace.mockReset();
  window.history.replaceState(null, '', '/sign-in');
  setCsrfToken(null);
  routes = {
    'GET /api/v1/session': () => signedOut(),
    'POST /api/v1/session': () => json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/' }),
    'GET /api/v1/me/onboarding': () => json(200, { admitted: true, can_create_workspace: false, next_url: '/' }),
    'POST /api/v1/session/logout': () => json(200, { csrf_token: 'out-2', signed_in: false, next_url: '/accounts/login/' }),
    'GET /api/v1/me': () => json(200, me),
    'GET /api/v1/role-dashboard': () => json(200, dashboard),
  };
  fetchStub = vi.fn(async (request: Request) => {
    if (isBellFeed(request)) return bellFeed();
    const handler = routes[`${request.method} ${new URL(request.url).pathname}`];
    return handler ? handler(request) : json(404, { code: 'not_found', message: 'No.' });
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const form = async () => screen.findByRole('button', { name: 'Sign in' });
const userField = () => screen.getByLabelText('Work email or sign-in name') as HTMLInputElement;
const passField = () => screen.getByLabelText('Password') as HTMLInputElement;
async function fill(user = 'sample.user', password = 'sample-password') {
  await form();
  fireEvent.change(userField(), { target: { value: user } });
  fireEvent.change(passField(), { target: { value: password } });
}
const press = () => fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

describe('the public branch of the shell', () => {
  it('/sign-in makes only the session read: no /me, no role words, no bars, no alert feed', async () => {
    render(
      <AppShell>
        <SignInView />
      </AppShell>,
    );
    await form();
    expect(fetchStub.mock.calls.map(([r]) => `${r.method} ${new URL(r.url).pathname}`)).toEqual(['GET /api/v1/session']);
    expect(document.querySelector('nav.psl-nav')).toBeNull();
    expect(document.querySelector('header.psl-phonebar')).toBeNull();
    expect(screen.queryByRole('link', { name: 'My work' })).toBeNull();
    expect(screen.queryByText('Skip to main content')).toBeNull();
  });

  it('a trailing slash is still the public path', async () => {
    nav.pathname = '/sign-in/';
    render(<AppShell><p>public body</p></AppShell>);
    expect(screen.getByText('public body')).toBeTruthy();
    expect(fetchStub).not.toHaveBeenCalled();
  });
});

describe('the default state', () => {
  it('has the board fields, a post form, no number of tries and no record name', async () => {
    render(<SignInView />);
    await form();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Sign in');
    expect(screen.getByText('Work you can see moving, from first draft to verified.')).toBeTruthy();
    expect(userField().type).toBe('text');
    expect(userField().autocomplete).toBe('username');
    expect(userField().getAttribute('autocapitalize')).toBe('none');
    expect(userField().getAttribute('spellcheck')).toBe('false');
    expect(passField().type).toBe('password');
    expect(passField().autocomplete).toBe('current-password');
    expect((screen.getByLabelText('Keep me signed in') as HTMLInputElement).checked).toBe(false);
    expect(document.querySelector('form')!.getAttribute('method')).toBe('post');
    expect(document.body.textContent).not.toMatch(/INV-0412|tries left|minutes|Only PMO/);
    expect(screen.getByText(/Forgot your password\? Reset opens in a later release\. Ask your administrator for help\./)).toBeTruthy();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.queryByText(/invitation/i)).toBeNull();
  });

  it('shows "Preparing sign-in…" and no form while the session read is pending', async () => {
    let release!: (r: Response) => void;
    routes['GET /api/v1/session'] = () => new Promise<Response>((resolve) => (release = resolve));
    render(<SignInView />);
    expect(screen.getByRole('status').textContent).toBe('Preparing sign-in…');
    expect(screen.queryByLabelText('Password')).toBeNull();
    await waitFor(() => expect(release).toBeTypeOf('function'));
    await act(async () => release(signedOut()));
    await form();
  });

  it('a failed session read shows "We couldn’t get sign-in ready" with no form, and Try again recovers', async () => {
    let fail = true;
    routes['GET /api/v1/session'] = () => (fail ? json(503, { code: 'unavailable', message: 'x' }) : signedOut());
    render(<SignInView />);
    expect(await screen.findByText('We couldn’t get sign-in ready. Nothing was changed.')).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await form();
    expect(screen.queryByText(/get sign-in ready/)).toBeNull();
  });

  it('a network failure on the session read is the same state', async () => {
    routes['GET /api/v1/session'] = () => Promise.reject(new TypeError('Failed to fetch'));
    render(<SignInView />);
    expect(await screen.findByText('We couldn’t get sign-in ready. Nothing was changed.')).toBeTruthy();
  });
});

describe('submitting', () => {
  it('an empty field makes no request and says which, with focus on the first', async () => {
    render(<SignInView />);
    await form();
    press();
    expect(screen.getByText('Enter your work email.')).toBeTruthy();
    expect(screen.getByText('Enter your password.')).toBeTruthy();
    expect(document.activeElement).toBe(userField());
    expect(posts()).toHaveLength(0);
    fireEvent.change(userField(), { target: { value: '   ' } });
    fireEvent.change(passField(), { target: { value: 'x' } });
    press();
    expect(screen.getByText('Enter your work email.')).toBeTruthy();
    expect(screen.queryByText('Enter your password.')).toBeNull();
    fireEvent.change(userField(), { target: { value: 'a' } });
    fireEvent.change(passField(), { target: { value: '' } });
    press();
    expect(document.activeElement).toBe(passField());
    expect(posts()).toHaveLength(0);
  });

  it.each([false, true])('sends {username (trimmed), password, remember: %s} with the token of the last session read', async (remember) => {
    render(<SignInView />);
    await fill('  sample.user ', ' sample-password ');
    if (remember) fireEvent.click(screen.getByLabelText('Keep me signed in'));
    press();
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(await bodyOf(posts()[0])).toEqual({ username: 'sample.user', password: ' sample-password ', remember });
    expect(posts()[0].headers.get('X-CSRFToken')).toBe('out-1');
  });

  it('a good sign-in stores the new token, then goes to / (the frame sends the person on)', async () => {
    render(<SignInView />);
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/'));
    expect(calls('GET', '/api/v1/me/onboarding')).toHaveLength(1);
    // The next write carries the token the sign-in returned.
    routes['POST /api/v1/me/alert-preferences'] = () => json(200, {});
    await call(liveApi.POST('/api/v1/me/alert-preferences', { params: { header: { 'X-CSRFToken': '' } }, body: { revision: 1, email_requested: true, whatsapp_requested: false } }));
    expect(calls('POST', '/api/v1/me/alert-preferences')[0].headers.get('X-CSRFToken')).toBe('in-1');
    expect(window.location.search).toBe('');
  });

  it('the password is not left in the field, the URL or the address bar after a good sign-in', async () => {
    render(<SignInView />);
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(passField().value).toBe('');
    expect(window.location.href).not.toContain('sample-password');
  });

  it('the button is busy and ignores a second press while the request runs', async () => {
    let release!: (r: Response) => void;
    routes['POST /api/v1/session'] = () => new Promise<Response>((resolve) => (release = resolve));
    render(<SignInView />);
    await fill();
    press();
    const busy = await screen.findByRole('button', { name: 'Signing in…' });
    fireEvent.click(busy);
    fireEvent.submit(document.querySelector('form')!);
    expect(posts()).toHaveLength(1);
    await act(async () => release(json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/' })));
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
  });
});

describe('errors', () => {
  const NUMBERS = /\d|minute|second|hour|tries left/;
  it.each([
    ['422 sign_in_failed', () => json(422, FAILED), 'That email and password don’t match.'],
    ['422 invalid_input with fields', () => json(422, { code: 'invalid_input', message: 'SERVER TEXT', fields: [{ name: 'username', message: 'SERVER FIELD' }] }), 'We couldn’t read those details. Check them and try again.'],
    ['403 csrf_failed', () => json(403, csrf), 'Your session was refreshed. Press Sign in again. Nothing was changed.'],
    ['429', () => json(429, { code: 'rate_limited', message: 'Try again in 15 minutes. SERVER TEXT' }), 'Too many sign-in tries. Try again later.'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'We could not reach PSL Factory. Check your connection and try again.'],
    ['500', () => json(500, { code: 'server_error', message: 'SERVER TEXT' }), 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.'],
    ['503', () => json(503, { code: 'unavailable', message: 'SERVER TEXT' }), 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.'],
    ['an unreadable 502', () => new Response('<html>', { status: 502 }), 'Sign-in isn’t working right now. Try again in a moment. Nothing was changed.'],
  ] as [string, Handler, string][])('%s shows its fixed wording, clears the password, keeps the name and focuses the callout', async (_, handler, wording) => {
    routes['POST /api/v1/session'] = handler;
    render(<SignInView />);
    await fill('someone@psl.example');
    press();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(wording);
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(passField().value).toBe('');
    expect(userField().value).toBe('someone@psl.example');
    expect(userField().getAttribute('aria-invalid')).toBeNull();
    expect(passField().getAttribute('aria-invalid')).toBeNull();
    expect(alert.textContent).not.toMatch(NUMBERS);
    expect(document.body.textContent).not.toContain('SERVER');
    expect(nav.replace).not.toHaveBeenCalled();
    // The button is back for another try.
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeTruthy();
  });

  it('a second wrong try shows the callout again with focus on it', async () => {
    routes['POST /api/v1/session'] = () => json(422, FAILED);
    render(<SignInView />);
    await fill();
    press();
    const first = await screen.findByRole('alert');
    fireEvent.change(passField(), { target: { value: 'again' } });
    (document.activeElement as HTMLElement).blur();
    press();
    await waitFor(() => expect(screen.getByRole('alert')).not.toBe(first));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('alert')));
  });

  it('a wrong password and an unknown name give the same page text', async () => {
    routes['POST /api/v1/session'] = () => json(422, FAILED);
    render(<SignInView />);
    await fill('known.user', 'wrong');
    press();
    const a = (await screen.findByRole('alert')).textContent;
    fireEvent.change(userField(), { target: { value: 'nobody.at.all' } });
    fireEvent.change(passField(), { target: { value: 'wrong' } });
    press();
    await waitFor(() => expect(posts()).toHaveLength(2));
    await act(async () => undefined);
    expect(screen.getByRole('alert').textContent).toBe(a);
  });

  it('after a csrf_failed the token is re-read and the second press carries it and succeeds', async () => {
    let session = 0;
    routes['GET /api/v1/session'] = () => signedOut(['stale', 'fresh'][session++] ?? 'fresh');
    routes['POST /api/v1/session'] = (request) => (request.headers.get('X-CSRFToken') === 'fresh' ? json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/my-work' }) : json(403, csrf));
    render(<SignInView />);
    await fill();
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('Press Sign in again');
    expect(calls('GET', '/api/v1/session')).toHaveLength(2);
    fireEvent.change(passField(), { target: { value: 'sample-password' } });
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/my-work'));
    expect(posts().map((r) => r.headers.get('X-CSRFToken'))).toEqual(['stale', 'fresh']);
  });
});

describe('where the person goes', () => {
  it('?next=/my-work is sent as next_url and followed when the server returns it', async () => {
    window.history.replaceState(null, '', '/sign-in?next=%2Fmy-work');
    routes['POST /api/v1/session'] = async (request) => json(200, { csrf_token: 'in-1', signed_in: true, next_url: ((await bodyOf(request)).next_url as string) ?? '/' });
    render(<SignInView />);
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/my-work'));
    expect((await bodyOf(posts()[0])).next_url).toBe('/my-work');
  });

  it.each(['https%3A%2F%2Fevil.example', '%2F%2Fevil.example', '%2F%5Cevil.example', 'javascript%3Aalert(1)', '%2Fapi%2Fv1%2Fme', '%2Faccounts%2Flogin%2F', '%2Fsign-in'])(
    '?next=%s is not sent and the person ends at /',
    async (next) => {
      window.history.replaceState(null, '', `/sign-in?next=${next}`);
      render(<SignInView />);
      await fill();
      press();
      await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/'));
      expect(await bodyOf(posts()[0])).not.toHaveProperty('next_url');
    },
  );

  it.each(['/accounts/login/', '/api/v1/me', '//evil.example', 'https://evil.example/x', '/getting-started/', '/sign-in'])('a server next_url of %s is not followed: the page goes to /', async (back) => {
    routes['POST /api/v1/session'] = () => json(200, { csrf_token: 'in-1', signed_in: true, next_url: back });
    render(<SignInView />);
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/'));
    expect(nav.replace).toHaveBeenCalledTimes(1);
  });

  it('not admitted: stays on the page with the plain notice and Sign out, and never follows next_url', async () => {
    routes['POST /api/v1/session'] = () => json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/getting-started/' });
    routes['GET /api/v1/me/onboarding'] = () => json(200, { admitted: false, can_create_workspace: false, next_url: '/getting-started/' });
    render(<SignInView />);
    await fill();
    press();
    expect(await screen.findByText('You’re signed in, but no work is open to you yet. Ask your administrator.')).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(nav.replace).not.toHaveBeenCalled();
    expect(document.body.innerHTML).not.toContain('getting-started');
    expect(screen.queryByText(/workspace/i)).toBeNull();
    // Sign out is the same call; the page then starts over.
    routes['GET /api/v1/session'] = () => signedOut('out-2');
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await form();
    expect(calls('POST', '/api/v1/session/logout')[0].headers.get('X-CSRFToken')).toBe('in-1');
    expect(nav.replace).toHaveBeenCalledWith('/sign-in');
  });

  it('a failed onboarding read falls back to going on', async () => {
    routes['GET /api/v1/me/onboarding'] = () => json(500, { code: 'x', message: 'y' });
    render(<SignInView />);
    await fill();
    press();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/'));
  });

  it('a signed-in visit shows no form and goes on with next from the query', async () => {
    window.history.replaceState(null, '', '/sign-in?next=%2Fprojects');
    routes['GET /api/v1/session'] = () => json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/' });
    render(<SignInView />);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/projects'));
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(posts()).toHaveLength(0);
  });

  it('a signed-in visit by someone who is not admitted shows the notice', async () => {
    routes['GET /api/v1/session'] = () => json(200, { csrf_token: 'in-1', signed_in: true, next_url: '/getting-started/' });
    routes['GET /api/v1/me/onboarding'] = () => json(200, { admitted: false, can_create_workspace: false, next_url: '/getting-started/' });
    render(<SignInView />);
    expect(await screen.findByText('You’re signed in, but no work is open to you yet. Ask your administrator.')).toBeTruthy();
    expect(nav.replace).not.toHaveBeenCalled();
  });
});

describe('forgot your password', () => {
  it('is plain text: no recovery request and no link', async () => {
    render(<SignInView />);
    await form();
    expect(screen.queryByRole('link', { name: /forgot/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /forgot/i })).toBeNull();
    expect(fetchStub.mock.calls.some(([r]) => new URL(r.url).pathname.includes('/accounts/recovery'))).toBe(false);
  });
});

describe('signing out from the frame', () => {
  const frame = async (width = 'desktop') => {
    nav.pathname = '/my-work';
    render(
      <AppShell>
        <p>page body</p>
      </AppShell>,
    );
    await screen.findByText('page body');
    return width;
  };
  const topNav = () => document.querySelector('nav.psl-nav') as HTMLElement;

  it('the name is an account menu button with the name, the role words and one item, Sign out', async () => {
    await frame();
    await waitFor(() => expect(topNav().textContent).toContain('PMO Lead'));
    const button = within(topNav()).getByRole('button', { name: 'Account menu: Ada Okafor · PMO Lead' });
    expect(button.getAttribute('aria-haspopup')).toBe('menu');
    fireEvent.click(button);
    const menu = screen.getByRole('menu', { name: 'Account' });
    expect(within(menu).getAllByRole('menuitem').map((i) => i.textContent)).toEqual(['Sign outSigns you out on this device']);
    expect(menu.closest('.cmp-pop')!.textContent).toContain('Ada Okafor');
    expect(menu.closest('.cmp-pop')!.textContent).toContain('PMO Lead');
  });

  it('Esc closes the menu and returns focus to the name', async () => {
    await frame();
    const button = within(topNav()).getByRole('button', { name: /Account menu/ });
    fireEvent.click(button);
    fireEvent.keyDown(screen.getByRole('menuitem'), { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it('Sign out posts {} with the token, keeps the new one and goes to /sign-in with no next', async () => {
    await frame();
    fireEvent.click(within(topNav()).getByRole('button', { name: /Account menu/ }));
    fireEvent.click(screen.getByRole('menuitem'));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/sign-in'));
    const request = calls('POST', '/api/v1/session/logout')[0];
    expect(await bodyOf(request)).toEqual({});
    expect(request.headers.get('X-CSRFToken')).toBe('t');
  });

  it('on a phone the menu has Sign out after the destinations, below a separator', async () => {
    await frame();
    fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
    const menu = document.querySelector('#phone-menu')!;
    const last = [...menu.children].at(-1)!;
    expect(last.textContent).toBe('Sign out');
    expect(menu.children[menu.children.length - 2].className).toBe('psl-sep');
    fireEvent.click(last);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/sign-in'));
  });

  it.each([
    ['500', () => json(500, { code: 'x', message: 'y' }), 'We couldn’t sign you out. Try again.'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'We couldn’t sign you out. Try again.'],
    ['403 csrf_failed', () => json(403, csrf), 'Your session was refreshed. Press Sign out again. Nothing was changed.'],
  ] as [string, Handler, string][])('%s keeps the person here with a toast and the menu still works', async (_, handler, wording) => {
    routes['GET /api/v1/session'] = () => signedOut('fresh');
    await frame();
    routes['POST /api/v1/session/logout'] = handler;
    const button = within(topNav()).getByRole('button', { name: /Account menu/ });
    fireEvent.click(button);
    fireEvent.click(screen.getByRole('menuitem'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe(wording));
    expect(nav.replace).not.toHaveBeenCalled();
    expect(calls('POST', '/api/v1/session/logout')).toHaveLength(1);
    fireEvent.click(button);
    expect(screen.getByRole('menuitem')).toBeTruthy();
  });

  it('after a csrf_failed the token was re-read, so the second press carries it and signs out', async () => {
    routes['GET /api/v1/session'] = () => signedOut('fresh');
    routes['POST /api/v1/session/logout'] = (request) => (request.headers.get('X-CSRFToken') === 'fresh' ? json(200, { csrf_token: 'out-2', signed_in: false, next_url: '/accounts/login/' }) : json(403, csrf));
    await frame();
    const button = within(topNav()).getByRole('button', { name: /Account menu/ });
    fireEvent.click(button);
    fireEvent.click(screen.getByRole('menuitem'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Press Sign out again'));
    fireEvent.click(button);
    fireEvent.click(screen.getByRole('menuitem'));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/sign-in'));
  });
});
