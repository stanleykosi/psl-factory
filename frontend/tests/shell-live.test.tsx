// @vitest-environment jsdom
// F-57: the frame on the live GET /me, GET /session and GET /role-dashboard.
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/api/errors';
import { AppShell } from '@/shell/AppShell';
import { hasDestination } from '@/shell/destinations';
import { DestinationPage } from '@/shell/DestinationPage';
import { MyWorkPage } from '@/features/my-work/MyWorkPage';
import { ProjectsPage } from '@/features/projects/ProjectsPage';
import { AssistantFrame } from '@/features/assistant/AssistantFrame';
import { SetupGate } from '@/features/setup/SetupFrame';

import { bellFeed, isBellFeed } from './bell-feed';
import { destinationList } from './destinations';

const nav = vi.hoisted(() => ({ pathname: '/my-work' }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const SIX = ['my_work', 'projects', 'overview', 'setup', 'clients', 'assistant'];
const me = (patch: Record<string, unknown> = {}) => ({
  name: 'Kemi Adebayo',
  work_desk_url: '/retired/',
  destinations: destinationList(SIX),
  startable_lines: ['pmo-weekly-report/v1'],
  csrf_token: 't',
  assistant_agents: ['tola' as const],
  ...patch,
});
const position = (name: string) => ({ role: 'pmo-lead', mode: 'lead', name, area: name, focus: 'x', workspace: `${name} workspace`, team: null, invite_url: null, manage_url: null });
const dashboard = (positions: unknown[]) => ({ positions, actions: [], decisions: [], team_decisions: [], limited: false, workspace_decisions: [], approval_desks: [], has_teams: false, page: 1, has_next: false, as_of: '2026-11-23T09:00:00Z' });
const SESSION = { csrf_token: 'session-token', signed_in: false, next_url: '/' };

type Handler = () => Response | Promise<Response>;
let routes: Record<string, Handler>;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const calls = (path: string) => fetchStub.mock.calls.filter(([request]) => new URL(request.url).pathname === path);

beforeEach(() => {
  routes = { '/api/v1/me': () => json(200, me()), '/api/v1/role-dashboard': () => json(200, dashboard([])), '/api/v1/session': () => json(200, SESSION) };
  fetchStub = vi.fn(async (request: Request) => {
    if (isBellFeed(request)) return bellFeed();
    const handler = routes[new URL(request.url).pathname];
    return handler ? handler() : json(404, { code: 'not_found', message: 'No.' });
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const topNav = () => document.querySelector('nav.psl-nav') as HTMLElement;
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const roleSpan = () => topNav().querySelector('.shell-who-role');
const whoText = () => topNav().querySelector('.psl-nav__who')!.textContent;

function renderShell(pathname = '/my-work', page = <p>page body</p>) {
  nav.pathname = pathname;
  return render(<AppShell>{page}</AppShell>);
}
const ready = () => screen.findByText('page body');

describe('the frame on live /me', () => {
  it('draws five links in order, no Clients link, Projects current on /clients, Start work, and never /retired/', async () => {
    renderShell('/clients');
    await ready();
    const links = within(topNav()).getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual(['My work', 'Projects', 'Overview', 'Assistant', 'Setup']);
    expect(within(topNav()).getByRole('link', { name: 'Projects' }).getAttribute('aria-current')).toBe('page');
    expect(within(topNav()).getByRole('button', { name: 'Start work' })).toBeTruthy();
    for (const el of document.querySelectorAll('[href], [src]')) expect(`${el.getAttribute('href')}${el.getAttribute('src')}`).not.toContain('/retired/');
    expect(document.body.textContent).not.toContain('/retired/');
  });

  it('never uses work_desk_url or django_url as a link, even when they hold real-looking paths', async () => {
    routes['/api/v1/me'] = () => json(200, me({ work_desk_url: '/desk/', destinations: SIX.map((key) => ({ key, title: key, django_url: `/workspace/${key}/` })) }));
    renderShell();
    await ready();
    for (const el of document.querySelectorAll('[href], [src]')) expect(`${el.getAttribute('href')}${el.getAttribute('src')}`).not.toMatch(/\/desk\/|\/workspace\//);
  });

  it('Start work shows only when startable_lines is not empty', async () => {
    routes['/api/v1/me'] = () => json(200, me({ startable_lines: [] }));
    renderShell();
    await ready();
    expect(screen.queryByRole('button', { name: 'Start work' })).toBeNull();
  });

  it('hasDestination looks keys up, including clients', () => {
    const m = me({ destinations: destinationList(['my_work', 'clients']) });
    expect([hasDestination(m, 'my_work'), hasDestination(m, 'clients'), hasDestination(m, 'setup')]).toEqual([true, true, false]);
  });
});

describe('every frame page asks hasDestination', () => {
  const pages: [string, string, () => React.ReactElement][] = [
    ['my_work', '/my-work', () => <MyWorkPage />],
    ['projects', '/projects', () => <ProjectsPage />],
    ['assistant', '/assistant', () => <AssistantFrame><p>x</p></AssistantFrame>],
    ['setup', '/setup', () => <SetupGate><p>x</p></SetupGate>],
    ['overview', '/overview', () => <DestinationPage destination="overview" />],
  ];
  it.each(pages)('/me without %s shows NotOpenState on %s', async (key, path, page) => {
    routes['/api/v1/me'] = () => json(200, me({ destinations: destinationList(['my_work', 'projects', 'overview', 'setup', 'assistant'].filter((k) => k !== key).concat(key === 'my_work' ? ['clients'] : [])) }));
    renderShell(path, page());
    expect(await screen.findByText('This section isn’t open to your role.')).toBeTruthy();
    // The assistant frame already starts its own list read before it gates (unchanged by F-57); the other pages make none.
    const own = fetchStub.mock.calls.map(([r]) => new URL(r.url).pathname).filter((p) => !['/api/v1/me', '/api/v1/role-dashboard', '/api/v1/session', '/api/v1/notifications'].includes(p));
    expect(own).toEqual(key === 'assistant' ? ['/api/v1/assistant/conversations'] : []);
  });
});

describe('role words from role-dashboard', () => {
  it('unique names in first-seen order show in the top bar and the phone menu', async () => {
    routes['/api/v1/role-dashboard'] = () => json(200, dashboard([position('PMO Lead'), position('PMO Lead'), position('Finance Lead')]));
    renderShell();
    await ready();
    await waitFor(() => expect(roleSpan()).not.toBeNull());
    expect(roleSpan()!.textContent).toBe(' · PMO Lead, Finance Lead');
    expect(whoText()).toBe('Kemi Adebayo · PMO Lead, Finance Lead');
    fireEvent.click(within(phoneBar()).getByRole('button', { name: 'Menu' }));
    expect(document.querySelector('#phone-menu small')!.textContent).toBe('PMO Lead, Finance Lead');
  });

  it.each([
    ['500', () => json(500, { code: 'x', message: 'y' })],
    ['401', () => json(401, { code: 'unauthenticated', message: 'Sign in to continue.' })],
    ['a network failure', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['no positions', () => json(200, dashboard([]))],
    ['blank names', () => json(200, dashboard([position(' '), position('')]))],
  ] as [string, Handler][])('%s gives the name alone, with no separator and no error', async (_, handler) => {
    routes['/api/v1/role-dashboard'] = handler;
    renderShell();
    await ready();
    await waitFor(() => expect(calls('/api/v1/role-dashboard')).toHaveLength(1));
    await act(async () => undefined);
    expect(whoText()).toBe('Kemi Adebayo');
    expect(roleSpan()).toBeNull();
    fireEvent.click(within(phoneBar()).getByRole('button', { name: 'Menu' }));
    expect(document.querySelector('#phone-menu small')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(document.body.textContent).not.toMatch(/ · /);
  });

  it('the frame renders while role-dashboard is still pending, and the words arrive after', async () => {
    let release!: (r: Response) => void;
    routes['/api/v1/role-dashboard'] = () => new Promise<Response>((resolve) => (release = resolve));
    renderShell();
    await ready();
    expect(whoText()).toBe('Kemi Adebayo');
    await act(async () => release(json(200, dashboard([position('PMO Lead')]))));
    await waitFor(() => expect(whoText()).toBe('Kemi Adebayo · PMO Lead'));
  });

  it('reads role-dashboard once per page load', async () => {
    renderShell();
    await ready();
    await act(async () => undefined);
    expect(calls('/api/v1/role-dashboard')).toHaveLength(1);
    expect(calls('/api/v1/me')).toHaveLength(1);
  });
});

describe('signed out', () => {
  beforeEach(() => {
    routes['/api/v1/me'] = () => json(401, { code: 'unauthenticated', message: 'Sign in to continue.' });
  });

  it('shows the callout and the later-release line, with no anchor in main and nothing for /accounts/', async () => {
    renderShell();
    expect(await screen.findByText('You’re signed out.')).toBeTruthy();
    expect(screen.getByText(/Sign-in opens in a later release\. Ask your administrator if you need access now\./)).toBeTruthy();
    const main = screen.getByRole('main');
    expect(main.querySelectorAll('a')).toHaveLength(0);
    expect(document.body.innerHTML).not.toContain('/accounts/');
    expect(within(topNav()).queryAllByRole('link')).toEqual([]);
    expect(screen.queryByRole('button', { name: 'Menu' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Start work' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Alerts' })).toBeNull();
  });

  it('reads /session once and stores its token for the next write', async () => {
    renderShell();
    await screen.findByText('You’re signed out.');
    expect(calls('/api/v1/session')).toHaveLength(1);
    expect(calls('/api/v1/me')).toHaveLength(1);
    const { liveApi, call } = await import('@/api/client');
    routes['/api/v1/me/alert-preferences'] = () => json(200, {});
    await call(liveApi.POST('/api/v1/me/alert-preferences', { params: { header: { 'X-CSRFToken': '' } }, body: { revision: 1, email_requested: true, whatsapp_requested: false } }));
    expect(calls('/api/v1/me/alert-preferences')[0][0].headers.get('X-CSRFToken')).toBe('session-token');
  });

  it('a session that appeared meanwhile reads /me once more and the frame renders', async () => {
    let signedIn = false;
    routes['/api/v1/me'] = () => (signedIn ? json(200, me()) : json(401, { code: 'unauthenticated', message: 'Sign in to continue.' }));
    routes['/api/v1/session'] = () => {
      signedIn = true;
      return json(200, { ...SESSION, signed_in: true });
    };
    renderShell();
    await ready();
    expect(calls('/api/v1/me')).toHaveLength(2);
    expect(calls('/api/v1/session')).toHaveLength(1);
    expect(within(topNav()).getAllByRole('link')).toHaveLength(5);
  });

  it('a failing /session read is ignored', async () => {
    routes['/api/v1/session'] = () => json(500, { code: 'x', message: 'y' });
    renderShell();
    expect(await screen.findByText('You’re signed out.')).toBeTruthy();
  });
});

describe('errors and csrf on /me', () => {
  it.each([
    ['429', () => json(429, { code: 'rate_limited', message: 'Slow down.' }), 'rate_limited'],
    ['503 read_limited', () => json(503, { code: 'read_limited', message: 'Too heavy.' }), 'read_limited'],
    ['400', () => json(400, { code: 'bad_request', message: 'No.' }), 'bad_request'],
    ['500', () => json(500, { code: 'server_error', message: 'No.' }), 'server_error'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
  ] as [string, Handler, string][])('%s shows the error card with its reference, and Try again reloads /me', async (_, handler, code) => {
    routes['/api/v1/me'] = handler;
    renderShell();
    const card = await screen.findByRole('alert');
    expect(card.textContent).toContain(`Reference ${code} for support.`);
    routes['/api/v1/me'] = () => json(200, me());
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await ready();
    expect(calls('/api/v1/me')).toHaveLength(2);
    expect(calls('/api/v1/session')).toHaveLength(0);
  });

  it('403 forbidden shows the forbidden state', async () => {
    routes['/api/v1/me'] = () => json(403, { code: 'forbidden', message: 'Your role does not allow this.' });
    renderShell();
    expect(await screen.findByText('Your account can’t use PSL Factory.')).toBeTruthy();
    expect(calls('/api/v1/session')).toHaveLength(0);
  });

  it('403 csrf_failed on /me refreshes the session once and reads /me once more', async () => {
    let first = true;
    routes['/api/v1/me'] = () => {
      if (!first) return json(200, me());
      first = false;
      return json(403, { code: 'csrf_failed', message: 'x' });
    };
    renderShell();
    await ready();
    expect(calls('/api/v1/session')).toHaveLength(1);
    expect(calls('/api/v1/me')).toHaveLength(2);
  });

  it('403 csrf_failed twice ends on the error card, with no third read', async () => {
    routes['/api/v1/me'] = () => json(403, { code: 'csrf_failed', message: 'x' });
    renderShell();
    const card = await screen.findByRole('alert');
    expect(card.textContent).toContain('Reference csrf_failed for support.');
    expect(calls('/api/v1/me')).toHaveLength(2);
  });

  it('an ApiError is what call() throws for the csrf kind', async () => {
    const { call, liveApi } = await import('@/api/client');
    routes['/api/v1/me'] = () => json(403, { code: 'csrf_failed', message: 'x' });
    const error = await call(liveApi.GET('/api/v1/me')).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
  });
});
