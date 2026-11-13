// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Destination } from '@/api/types';
import { AppShell } from '@/shell/AppShell';
import { DestinationPage, UnknownPage } from '@/shell/DestinationPage';
import { HomeRedirect } from '@/shell/HomeRedirect';

const nav = vi.hoisted(() => ({ pathname: '/my-work', replace: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: nav.replace, push: vi.fn(), prefetch: vi.fn() }),
}));

const fixture = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;

beforeEach(() => {
  nav.replace.mockReset();
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

const routeOf: Record<string, Destination> = {
  '/my-work': 'my_work',
  '/projects': 'projects',
  '/overview': 'overview',
  '/assistant': 'assistant',
  '/setup': 'setup',
};

function renderAt(pathname: string) {
  nav.pathname = pathname;
  const page = pathname === '/' ? <HomeRedirect /> : <DestinationPage destination={routeOf[pathname]} />;
  return render(<AppShell>{page}</AppShell>);
}

const topNav = () => document.querySelector('nav.psl-nav') as HTMLElement;
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const menuButton = () => within(phoneBar()).getByRole('button', { name: 'Menu' });
/** The top bar's who-line: full text, the name part and the role part (visually hidden below 1080px). */
const who = () => {
  const el = topNav().querySelector('.psl-nav__who')!;
  return { text: el.textContent, name: el.querySelector('.shell-who-name')!.textContent, role: el.querySelector('.shell-who-role')!.textContent };
};

async function loaded() {
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
}

describe('navigation follows /me', () => {
  it('finance_lead sees all five destinations, the current one marked, and who is signed in', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    renderAt('/my-work');
    await loaded();
    const links = within(topNav()).getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual(['My work', 'Projects', 'Overview', 'Assistant', 'Setup']);
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/my-work', '/projects', '/overview', '/assistant', '/setup']);
    expect(links[0]).toHaveProperty('className', 'psl-navlink');
    expect(links[0].getAttribute('aria-current')).toBe('page');
    expect(links.slice(1).every((a) => !a.hasAttribute('aria-current'))).toBe(true);
    expect(within(topNav()).getByText('PSL FACTORY')).toBeTruthy();
    expect(who()).toEqual({ text: 'Ada Okafor · Finance Lead', name: 'Ada Okafor', role: ' · Finance Lead' });
    expect(screen.getByRole('heading', { level: 1, name: 'My work' })).toBeTruthy();
    expect(screen.getByText('This page is not built yet. It arrives in a later release.')).toBeTruthy();
    expect(fetchStub).toHaveBeenCalledTimes(1);
    expect(new URL(fetchStub.mock.calls[0][0].url).pathname).toBe('/api/v1/me');
  });

  it('pm sees only My work, Projects and Assistant; /overview is not open to them', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('pm')));
    renderAt('/overview');
    await loaded();
    expect(within(topNav()).getAllByRole('link').map((a) => a.textContent)).toEqual(['My work', 'Projects', 'Assistant']);
    expect(topNav().querySelector('[aria-current]')).toBeNull();
    expect(who()).toEqual({ text: 'Tunde Bello · PM', name: 'Tunde Bello', role: ' · PM' });
    const main = screen.getByRole('main');
    expect(within(main).getByText('This section isn’t open to your role.')).toBeTruthy();
    expect(within(main).getByRole('link').getAttribute('href')).toBe('/my-work');
    expect(within(main).queryByRole('heading', { level: 1 })).toBeNull();
    expect(within(main).queryByText(/not built yet/)).toBeNull();
  });

  it('persona none sees no sections and their name', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('none')));
    renderAt('/my-work');
    await loaded();
    expect(within(topNav()).queryAllByRole('link')).toEqual([]);
    expect(who()).toEqual({ text: 'Sample Person · Staff', name: 'Sample Person', role: ' · Staff' });
    expect(screen.getByText('No sections are open to your role yet.')).toBeTruthy();
    expect(screen.getByText('Ask a Lead or Admin to check your roles.')).toBeTruthy();
  });

  it('an unknown address shows a plain not-found message with a link to the first destination', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('pm')));
    nav.pathname = '/nonexistent';
    render(
      <AppShell>
        <UnknownPage />
      </AppShell>,
    );
    await loaded();
    const main = screen.getByRole('main');
    expect(within(main).getByRole('heading', { level: 3 }).textContent).toBe('This page doesn’t exist.');
    expect(within(main).getByRole('link', { name: 'Go to My work' }).getAttribute('href')).toBe('/my-work');
    expect(topNav().querySelector('[aria-current]')).toBeNull();
  });

  it('/ sends the person to their first destination', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('pm')));
    renderAt('/');
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/my-work'));
  });

  it('has no Start work, bell, account menu or sign-out', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    renderAt('/my-work');
    await loaded();
    fireEvent.click(menuButton());
    expect(document.body.textContent).not.toMatch(/Start|Sign out|Notifications/);
    expect(screen.queryAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent)).toEqual(['Menu']);
  });
});

describe('frame states', () => {
  it('loading shows a status message and no destinations or name', async () => {
    let resolve!: (r: Response) => void;
    fetchStub.mockReturnValue(new Promise((r) => (resolve = r)));
    renderAt('/my-work');
    expect(screen.getByRole('status').textContent).toBe('Loading…');
    expect(screen.queryAllByRole('link').map((a) => a.textContent)).toEqual(['Skip to main content']);
    expect(document.body.textContent).not.toContain('Ada Okafor');
    expect(screen.queryByRole('button', { name: 'Menu' })).toBeNull();
    expect(screen.getAllByText('SAMPLE DATA')).toHaveLength(2);
    await act(async () => resolve(json(200, fixture('finance_lead'))));
    await loaded();
  });

  it('401 shows signed out with a sign-in link back to this page', async () => {
    fetchStub.mockResolvedValue(json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }));
    renderAt('/my-work');
    await waitFor(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
    expect(within(topNav()).queryByText('My work')).toBeNull();
    expect(document.querySelector('.psl-callout--warning')).toBeTruthy();
  });

  it('403 shows the forbidden callout with the error message', async () => {
    fetchStub.mockResolvedValue(json(403, { code: 'forbidden', message: 'Your role does not allow this.' }));
    renderAt('/my-work');
    await waitFor(() => expect(screen.getByText('Your account can’t use PSL Factory.')).toBeTruthy());
    expect(screen.getByText(/Your role does not allow this\./)).toBeTruthy();
  });

  it.each([
    ['404', () => json(404, { code: 'not_found', message: 'We could not find that record.' }), 'not_found'],
    ['500', () => new Response('<html></html>', { status: 500 }), 'unexpected_response'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
  ] as const)('%s shows the error pattern and Try again reloads /me', async (_, respond, code) => {
    fetchStub.mockImplementationOnce(respond as () => Promise<Response>);
    renderAt('/my-work');
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    // STATES error card: eyebrow, message, reference line, then a full-size secondary Try again button.
    const card = screen.getByRole('alert');
    expect(card.className).toBe('shell-errorcard');
    expect([...card.children].map((el) => el.textContent)).toEqual([
      'ERROR · COULDN’T LOAD',
      'We couldn’t load your account. Your work is safe; nothing was changed.',
      `Reference ${code} for support.`,
      'Try again',
    ]);
    expect(card.children[0].className).toBe('shell-eyebrow');
    expect(card.children[2].className).toBe('shell-reference');
    expect(within(card).getByRole('button', { name: 'Try again' }).className).toBe('psl-btn psl-btn--secondary psl-btn--lg psl-btn--block');
    expect(document.querySelector('.psl-callout--problem')).toBeNull();
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(within(topNav()).getAllByRole('link')).toHaveLength(5));
    expect(fetchStub).toHaveBeenCalledTimes(2);
  });

  it.each(['loaded', '401', '404'])('SAMPLE DATA shows in both bars (%s)', async (kind) => {
    fetchStub.mockResolvedValue(
      kind === 'loaded' ? json(200, fixture('pm')) : json(Number(kind), { code: 'x', message: 'y' }),
    );
    renderAt('/my-work');
    await loaded();
    expect(topNav().querySelector('.psl-sample')?.textContent).toBe('SAMPLE DATA');
    expect(phoneBar().querySelector('.psl-sample')?.textContent).toBe('SAMPLE DATA');
  });
});

describe('phone bar menu', () => {
  it('opens as a disclosure, marks the current page, closes on Esc and returns focus', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    renderAt('/projects');
    await loaded();
    const button = menuButton();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(button.getAttribute('aria-controls')).toBe('phone-menu');
    expect(document.getElementById('phone-menu')).toBeNull();
    fireEvent.click(button);
    expect(button.getAttribute('aria-expanded')).toBe('true');
    const menu = document.getElementById('phone-menu')!;
    expect(menu.tagName).toBe('NAV');
    expect(menu.getAttribute('aria-label')).toBe('Main');
    expect(menu.className).toBe('psl-pop psl-menu');
    expect(menu.textContent).toContain('Ada Okafor');
    const links = within(menu).getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual(['My work', 'Projects', 'Overview', 'Assistant', 'Setup']);
    expect(links[1].getAttribute('aria-current')).toBe('page');
    links[2].focus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.getElementById('phone-menu')).toBeNull();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(button);
  });

  it('choosing a destination closes the menu', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    renderAt('/my-work');
    await loaded();
    fireEvent.click(menuButton());
    const projects = within(document.getElementById('phone-menu')!).getByRole('link', { name: 'Projects' });
    expect(projects.getAttribute('href')).toBe('/projects');
    fireEvent.click(projects);
    expect(document.getElementById('phone-menu')).toBeNull();
  });
});

describe('accessibility (axe-core in jsdom, colour contrast checked in the browser run)', () => {
  const options: axe.RunOptions = {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
    rules: { 'color-contrast': { enabled: false } },
  };

  it('TopNav and PhoneBar (menu open) have no violations', async () => {
    fetchStub.mockResolvedValue(json(200, fixture('finance_lead')));
    renderAt('/my-work');
    await loaded();
    fireEvent.click(menuButton());
    const results = await axe.run(document.body, options);
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
  });

  it('the signed-out frame has no violations', async () => {
    fetchStub.mockResolvedValue(json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }));
    renderAt('/my-work');
    await waitFor(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    const results = await axe.run(document.body, options);
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
