// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';
import { destinationList } from './destinations';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/00000000-0000-4000-8000-000000000101',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const LAGOON = '00000000-0000-4000-8000-000000000101';
type Item = { id: number; line: string; reference: string | null; state: string; started: string; updated: string; django_url: string; api_url: string };
type Journey = {
  case_id: string;
  title: string;
  items: Item[];
  page: number;
  next_page: number | null;
  tabs: { key: string; title: string }[];
  facts: { total: number; waiting: number; stopped: number; finance: { stages: number | null; delivered: number | null; next: string | null; limited: boolean } | null; engagement: { route: string; reference: string; manager: string | null } | null };
  assistant: { agent: string; scope: string; api_url: string }[];
};
const item = (id: number, over: Partial<Item> = {}): Item => ({ id, line: `Line ${id}`, reference: null, state: 'Waiting', started: '2026-11-12T09:00:00Z', updated: '2026-11-14T09:00:00Z', django_url: `/work/${id}/`, api_url: `/api/v1/work/${id}`, ...over });
const body = (over: Partial<Journey> = {}): Journey => ({
  case_id: LAGOON,
  title: 'Lagoon Health · patient app',
  items: [item(1)],
  page: 1,
  next_page: null,
  tabs: ['journey', 'milestones', 'documents', 'money', 'registers', 'actions'].map((key) => ({ key, title: key })),
  facts: { total: 1, waiting: 1, stopped: 0, finance: { stages: 4, delivered: 1, next: 'UAT sign-off', limited: false }, engagement: { route: 'Route A', reference: 'ENG-0101', manager: 'Tunde Bello' } },
  assistant: [{ agent: 'tola', scope: 'project', api_url: '/api/v1/assistant/conversations' }],
  ...over,
});
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fromMock = (url: URL, persona = 'finance_lead') => projects({ operationId: 'E-PROJECT', url, persona }) as { status: number; body: Journey };
const mockResponse = (url: URL, persona = 'finance_lead') => {
  const r = fromMock(url, persona);
  return json(r.status, r.body);
};
const HARMATTAN = '00000000-0000-4000-8000-000000000102';
const p0101 = () => fromMock(new URL(`http://x/api/v1/projects/${LAGOON}`)).body;

let persona = 'finance_lead';
let destinations: string[] | undefined;
let respond: (url: URL) => Response | Promise<Response>;
let calls: URL[];
const lastCall = () => calls[calls.length - 1];

beforeEach(() => {
  persona = 'finance_lead';
  destinations = undefined;
  calls = [];
  respond = (url) => mockResponse(url, persona);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, { ...me(persona), ...(destinations ? { destinations: destinationList(destinations) } : {}) });
      calls.push(url);
      return respond(url);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

const page = (caseId: string, tab?: 'milestones' | 'documents') => (
  <AppShell>
    <ProjectJourneyPage caseId={caseId} tab={tab} />
  </AppShell>
);

async function open(caseId = LAGOON, tab?: 'milestones' | 'documents') {
  const result = render(page(caseId, tab));
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  return result;
}

const lineItems = () => [...document.querySelectorAll('ol.projects__lines > li')] as HTMLElement[];
const projectTabs = () => within(screen.getByRole('tablist', { name: 'Project' })).getAllByRole('tab');
const facts = () => [...document.querySelectorAll('.psl-fact')].map((f) => [f.querySelector('b')!.textContent, f.querySelector('strong')!.textContent, f.className]);

const moreButton = () => screen.queryByRole('button', { name: 'Show more' });

describe('journey reads GET /projects/{case_id}, drawn as SCR-07', () => {
  it('P-0101: breadcrumb, title, six tabs without counts, PM and route line, four facts, the work rows in order, no what-is-next and no summary', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe(`/api/v1/projects/${LAGOON}`);
    expect(calls[0].search).toBe('');
    const live = p0101();
    const crumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe('Projects / Lagoon Health');
    expect(within(crumb).getByRole('link', { name: 'Projects' }).getAttribute('href')).toBe('/projects');
    expect(crumb.querySelector('[aria-current="page"]')!.textContent).toBe('Lagoon Health');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    const base = `/projects/${LAGOON}`;
    expect(projectTabs().map((t) => [t.textContent, t.getAttribute('href'), t.getAttribute('aria-selected')])).toEqual([
      ['Journey', base, 'true'],
      ['Milestones', `${base}/milestones`, 'false'],
      ['Documents', `${base}/documents`, 'false'],
      ['Money', `${base}/money`, 'false'],
      ['Registers', `${base}/registers`, 'false'],
      ['Actions', `${base}/actions`, 'false'],
    ]);
    expect(screen.getByRole('tabpanel', { name: 'Journey' })).toBeTruthy();
    expect(document.querySelector('.projects__route')!.textContent).toBe('PM Tunde Bello · Route A · 8 pieces of work');
    expect(document.querySelector('.projects__phoneline')!.textContent).toBe('8 pieces of work · 2 waiting on people · 1 stopped');
    expect(screen.getByRole('region', { name: 'Facts earned' })).toBeTruthy();
    expect(facts()).toEqual([
      ['CONTRACT STAGES', '4', 'psl-fact'],
      ['WAITING ON PEOPLE', '2', 'psl-fact psl-fact--current'],
      ['STOPPED', '1', 'psl-fact psl-fact--current'],
      ['NEXT MILESTONE', 'UAT sign-off', 'psl-fact'],
    ]);
    expect(screen.getByText('Figures may be partial.')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'The whole journey, oldest first' })).toBeTruthy();
    expect(lineItems()).toHaveLength(8);
    expect(lineItems().map((li) => within(li).getAllByRole('link').map((a) => a.getAttribute('href')))).toEqual(live.items.map((i) => [`/work/${i.id}`]));
    expect(lineItems().map((li) => li.querySelector('.projects__linename')!.firstChild!.textContent)).toEqual(live.items.map((i) => i.line));
    expect(lineItems()[6].textContent).toBe('Invoice · Milestone 2, INV-0412 INV-0412Started 16 Mar · Updated 19 Nov' + 'Waiting');
    expect(screen.getByText('8 of 8 shown')).toBeTruthy();
    expect(moreButton()).toBeNull();
    const text = document.querySelector('main')!.textContent!;
    for (const gone of ['What is next', 'Station', 'INVOICES VERIFIED', 'PAID', 'lines', 'summary', 'undefined']) expect(text).not.toContain(gone);
  });

  it('a work row: the line, the reference only when there is one, the dates, and one neutral tag with the state words as given', async () => {
    respond = () =>
      json(
        200,
        body({
          items: [
            item(12, { line: 'Prepare an invoice', reference: 'INV-0412', state: 'Waiting' }),
            item(13, { line: 'Plan a project', reference: null, state: 'Version 2', started: '2026-03-01T09:00:00Z', updated: '2026-10-30T09:00:00Z' }),
            item(14, { line: 'Check release', state: 'A word nobody planned for' }),
            item(15, { line: 'Blocked thing', state: 'Blocked' }),
          ],
        }),
      );
    await open();
    expect(lineItems().map((li) => li.querySelector('a')!.getAttribute('href'))).toEqual(['/work/12', '/work/13', '/work/14', '/work/15']);
    expect(lineItems()[0].querySelector('.projects__ref')!.textContent).toBe(' INV-0412');
    expect(lineItems()[1].querySelector('.projects__ref')).toBeNull();
    expect(lineItems()[1].querySelector('.projects__detail')!.textContent).toBe('Started 01 Mar · Updated 30 Oct');
    const tags = lineItems().map((li) => li.querySelector('.psl-tag')!);
    expect(tags.map((t) => t.textContent)).toEqual(['Waiting', 'Version 2', 'A word nobody planned for', 'Blocked']);
    for (const tag of tags) expect(tag.className).toContain('psl-tag--neutral');
    expect(lineItems().map((li) => li.querySelector('.projects__dot')!.className)).toEqual(Array(4).fill('projects__dot projects__dot--neutral'));
  });

  it('server order is kept exactly; repeated titles carry their reference or state in the link name (UX-1-1)', async () => {
    respond = () => json(200, body({ items: [item(9, { line: 'Zulu line', state: 'Verified' }), item(1, { line: 'Alpha line' }), item(5, { line: 'Zulu line', reference: 'INV-5' })] }));
    await open();
    expect(lineItems().map((li) => li.querySelector('a')!.getAttribute('href'))).toEqual(['/work/9', '/work/1', '/work/5']);
    expect(lineItems().map((li) => li.querySelector('a')!.textContent)).toEqual(['Zulu line, Verified', 'Alpha line', 'Zulu line, INV-5']);
  });

  it('finance null reads Not available in both finance cells, never 0, and no partial line; no engagement leaves PM and route out', async () => {
    respond = () => json(200, body({ title: 'Standalone fit-out', facts: { total: 0, waiting: 0, stopped: 0, finance: null, engagement: null }, items: [], assistant: [] }));
    await open();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('Projects');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Standalone fit-out');
    expect(document.querySelector('.projects__route')!.textContent).toBe('0 pieces of work');
    expect(facts()).toEqual([
      ['CONTRACT STAGES', 'Not available', 'psl-fact psl-fact--unknown'],
      ['WAITING ON PEOPLE', '0', 'psl-fact'],
      ['STOPPED', '0', 'psl-fact'],
      ['NEXT MILESTONE', 'Not available', 'psl-fact psl-fact--unknown'],
    ]);
    expect(screen.queryByText('Figures may be partial.')).toBeNull();
    expect(document.querySelector('.psl-empty')!.textContent).toBe('No work yetNo work on this project yet.');
    expect(document.querySelector('ol')).toBeNull();
    expect(moreButton()).toBeNull();
  });

  it('a null manager leaves the PM out of the route line; a null stage or next milestone reads Not available', async () => {
    respond = () => json(200, body({ facts: { total: 3, waiting: 0, stopped: 0, finance: { stages: null, delivered: null, next: null, limited: true }, engagement: { route: 'Route B', reference: 'ENG-1', manager: null } } }));
    await open();
    expect(document.querySelector('.projects__route')!.textContent).toBe('Route B · 3 pieces of work');
    expect(facts().map(([label, value]) => [label, value])).toEqual([
      ['CONTRACT STAGES', 'Not available'],
      ['WAITING ON PEOPLE', '0'],
      ['STOPPED', '0'],
      ['NEXT MILESTONE', 'Not available'],
    ]);
    expect(screen.getByText('Figures may be partial.')).toBeTruthy();
  });

  it('the client crumb is the part of the title before the first " · "; no separator, no client', async () => {
    respond = () => json(200, body({ title: 'Kora · fleet · tracker' }));
    const first = await open();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('Projects / Kora');
    first.unmount();
    respond = () => json(200, body({ title: 'Whole title only' }));
    await open();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('Projects');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Whole title only');
  });

  it('arrow keys move focus along the project tabs', async () => {
    await open();
    projectTabs()[0].focus();
    fireEvent.keyDown(projectTabs()[0], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(projectTabs()[1]));
    fireEvent.keyDown(projectTabs()[1], { key: 'End' });
    await waitFor(() => expect(document.activeElement).toBe(projectTabs()[5]));
    fireEvent.keyDown(projectTabs()[5], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(projectTabs()[0]));
  });
});

describe('the Assistant link', () => {
  it('shows "Ask me about this project" to /assistant when assistant[] is not empty and the person has the destination; it makes no request', async () => {
    await open();
    const panel = screen.getByRole('complementary', { name: 'Assistant' });
    expect(within(panel).getByRole('link', { name: 'Ask me about this project' }).getAttribute('href')).toBe('/assistant');
    expect(panel.textContent).toBe('Ask me about this project');
    expect(calls.map((c) => c.pathname)).toEqual([`/api/v1/projects/${LAGOON}`]);
  });

  it('is absent when assistant[] is empty, and when the person lacks the Assistant destination', async () => {
    respond = () => json(200, body({ assistant: [] }));
    const first = await open();
    expect(screen.queryByRole('complementary')).toBeNull();
    first.unmount();
    respond = (url) => mockResponse(url, persona);
    destinations = ['my_work', 'projects'];
    await open();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Ask me about this project' })).toBeNull();
  });
});

describe('Show more on the journey', () => {
  it('P-0102 has 24 pieces of work: 20 shown, "20 of 24 shown"; Show more reads ?page=2, appends, focuses the first new row', async () => {
    await open(HARMATTAN, undefined);
    expect(lineItems()).toHaveLength(20);
    expect(screen.getByText('20 of 24 shown')).toBeTruthy();
    fireEvent.click(moreButton()!);
    await until(() => expect(lineItems()).toHaveLength(24));
    expect(lastCall().search).toBe('?page=2');
    expect(screen.getByText('24 of 24 shown')).toBeTruthy();
    expect(moreButton()).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(lineItems()[20].querySelector('a')));
    expect(calls).toHaveLength(2);
  });

  it('a failed second read keeps the first rows and offers Retry, which reads page 2 again', async () => {
    await open(HARMATTAN);
    respond = () => json(503, { code: 'unavailable', message: 'Down.' });
    fireEvent.click(moreButton()!);
    await until(() => expect(screen.getByText(/We couldn’t load more/)).toBeTruthy());
    expect(lineItems()).toHaveLength(20);
    expect(screen.getByText('20 of 24 shown')).toBeTruthy();
    respond = (url) => mockResponse(url);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await until(() => expect(lineItems()).toHaveLength(24));
    expect(lastCall().search).toBe('?page=2');
  });

  it('a 401 on the second read shows the signed-out state', async () => {
    await open(HARMATTAN);
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    fireEvent.click(moreButton()!);
    await until(() => expect(screen.getByRole('link', { name: 'Sign in' })).toBeTruthy());
  });
});

describe('tabs from the live tabs[]', () => {
  it('shows only the keys live returned that are routed, in the returned order; no Delivery, Templates or counts', async () => {
    respond = () => json(200, body({ tabs: ['journey', 'templates', 'actions', 'delivery', 'month-end', 'milestones', 'hr'].map((key) => ({ key, title: key })) }));
    await open();
    expect(projectTabs().map((t) => t.textContent)).toEqual(['Journey', 'Actions', 'Milestones']);
  });

  it('a person whose tabs[] lacks money sees no Money tab', async () => {
    respond = () => json(200, body({ tabs: ['journey', 'milestones', 'documents', 'registers', 'actions'].map((key) => ({ key, title: key })) }));
    await open();
    expect(projectTabs().map((t) => t.textContent)).toEqual(['Journey', 'Milestones', 'Documents', 'Registers', 'Actions']);
  });
});

describe('empty, no access and not open', () => {
  it.each([404, 403])('%s shows the no-access state and nothing from the response or the request', async (status) => {
    respond = () => json(status, { code: 'lagoon_secret_code', message: 'Lagoon Health secret' });
    await open();
    const section = screen.getByRole('heading', { level: 1, name: 'You can’t open this project' }).closest('section')!;
    expect(section.textContent).toContain('NO ACCESS');
    expect(section.textContent).toContain('It belongs to work you don’t have access to. Nothing about it is shown here, not even its name.');
    expect(within(section).getByRole('link', { name: 'Back to projects' }).getAttribute('href')).toBe('/projects');
    const text = document.body.textContent!;
    for (const leaked of [LAGOON, 'Lagoon Health', 'lagoon_secret_code']) expect(text).not.toContain(leaked);
    expect(screen.queryByRole('tablist', { name: 'Project' })).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).toBeNull();
  });

  it.each(['P-0099', '00000000-0000-4000-8000-000000000099'])('the mock no-access id %s shows no access', async (id) => {
    await open(id);
    expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy();
  });

  it('P-0104 as pm (the mock 404), in either form, shows no access without the title', async () => {
    persona = 'pm';
    const first = await open('00000000-0000-4000-8000-000000000104');
    expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Delta Foods');
    first.unmount();
    await open('P-0104');
    expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy();
  });

  it('without the projects destination: not open, and no project request', async () => {
    destinations = ['my_work'];
    render(page(LAGOON));
    await until(() => expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });

  it('persona none: the frame shows no sections, and no project request', async () => {
    persona = 'none';
    render(page(LAGOON));
    await until(() => expect(screen.getByText('No sections are open to your role yet.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });
});

describe('signed out, failures and stale responses', () => {
  it('401 shows the signed-out callout with the project path as the return path', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe(`/sign-in?next=%2Fprojects%2F${LAGOON}`);
  });

  it('401 on a tab signs in back to that tab', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open(LAGOON, 'milestones');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe(`/sign-in?next=%2Fprojects%2F${LAGOON}%2Fmilestones`);
  });

  it.each([
    ['500', () => json(500, { code: 'server_down', message: 'x' }), 'server_down'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
    ['malformed 200 (the /me body)', () => json(200, me('finance_lead')), 'unexpected_response'],
    ['200 without a title', () => json(200, { ...body(), title: '' }), 'unexpected_response'],
    ['200 without items', () => json(200, { ...body(), items: undefined }), 'unexpected_response'],
  ])('%s shows the journey error card; Try again re-reads and recovers', async (_, failure, code) => {
    respond = failure as () => Response;
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toContain('We couldn’t load this project. Your work is safe; nothing was changed.');
    expect(card.textContent).toContain(`Reference ${code} for support.`);
    respond = (url) => mockResponse(url);
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await until(() => expect(lineItems()).toHaveLength(p0101().items.length));
    expect(calls).toHaveLength(2);
  });

  it('loading shows status; a late response for the previous case_id is ignored', async () => {
    const pending: Record<string, () => void> = {};
    respond = (url) => new Promise<Response>((resolve) => (pending[url.pathname.split('/')[4]] = () => resolve(mockResponse(url))));
    const view = render(page(LAGOON));
    await until(() => expect(pending[LAGOON]).toBeTruthy());
    expect(screen.getByText('Loading…')).toBeTruthy();
    view.rerender(page(HARMATTAN));
    await until(() => expect(pending[HARMATTAN]).toBeTruthy());
    await act(async () => pending[HARMATTAN]());
    await until(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Harmattan Bank · mobile onboarding'));
    await act(async () => pending[LAGOON]());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Harmattan Bank · mobile onboarding');
  });

  it('shows the one SAMPLE DATA tag from the project’s sample flag when the switch is on, and none when it is off', async () => {
    const first = await open();
    expect(document.querySelector('main .psl-sample')).toBeNull();
    first.unmount();
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open();
    expect(document.querySelectorAll('main .psl-sample')).toHaveLength(1);
  });
});
