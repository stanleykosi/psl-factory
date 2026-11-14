// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { STATE_TAGS } from '@/features/work-item/labels';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';

vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

type Line = { line: string; state: keyof typeof STATE_TAGS; work_id: string };
type Journey = { case_id: string; title: string; lines: Line[]; next: string };
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fromMock = (url: URL, persona = 'finance_lead') => projects({ operationId: 'E-PROJECT', url, persona }) as { status: number; body: Journey };
const mockResponse = (url: URL, persona = 'finance_lead') => {
  const r = fromMock(url, persona);
  return json(r.status, r.body);
};
const p0101 = () => fromMock(new URL('http://x/api/v1/projects/P-0101')).body;

let persona = 'finance_lead';
let destinations: string[] | undefined;
let respond: (url: URL) => Response | Promise<Response>;
let calls: URL[];

beforeEach(() => {
  persona = 'finance_lead';
  destinations = undefined;
  calls = [];
  respond = (url) => mockResponse(url, persona);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, { ...me(persona), ...(destinations ? { destinations } : {}) });
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

const page = (caseId: string) => (
  <AppShell>
    <ProjectJourneyPage caseId={caseId} />
  </AppShell>
);

async function open(caseId = 'P-0101') {
  const result = render(page(caseId));
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByRole('status')).toBeNull());
  return result;
}

const lineItems = () => [...document.querySelectorAll('ol.projects__lines > li')] as HTMLElement[];

describe('journey reads E-PROJECT and keeps order (JR-08)', () => {
  it('P-0101: breadcrumb, title, Journey tab, What is next and one li per line in response order', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe('/api/v1/projects/P-0101');
    const body = p0101();
    const crumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe(`Projects / ${body.title}`);
    expect(within(crumb).getByRole('link', { name: 'Projects' }).getAttribute('href')).toBe('/projects');
    expect(crumb.querySelector('[aria-current="page"]')!.textContent).toBe(body.title);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    const tabs = within(screen.getByRole('navigation', { name: 'Project' })).getAllByRole('link');
    expect(tabs.map((t) => [t.textContent, t.getAttribute('href'), t.getAttribute('aria-current')])).toEqual([['Journey', '/projects/P-0101', 'page']]);
    const next = document.querySelector('.psl-callout')!;
    expect(next.textContent).toBe(`What is next${body.next}`);
    expect(screen.getByRole('heading', { level: 2, name: 'The whole journey' })).toBeTruthy();
    expect(lineItems()).toHaveLength(body.lines.length);
    expect(lineItems().map((li) => within(li).getAllByRole('link').map((a) => a.getAttribute('href')))).toEqual(
      body.lines.map((l) => [`/work/${l.work_id}`]),
    );
    expect(lineItems().map((li) => li.querySelector('.projects__linename')!.textContent)).toEqual(body.lines.map((l) => l.line));
  });

  it('server order is kept exactly, including repeated lines', async () => {
    const lines: Line[] = [
      { line: 'Zulu line', state: 'verified', work_id: 'W-9' },
      { line: 'Alpha line', state: 'waiting', work_id: 'W-1' },
      { line: 'Zulu line', state: 'ready', work_id: 'W-5' },
    ];
    respond = () => json(200, { case_id: 'P-7', title: 'Seven', lines, next: 'Nothing yet.' });
    await open('P-7');
    expect(lineItems().map((li) => li.querySelector('a')!.getAttribute('href'))).toEqual(['/work/W-9', '/work/W-1', '/work/W-5']);
  });

  it('shows no PM, route, facts, per-line references, tab counts, station bars or agent summary', async () => {
    await open();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(document.querySelector('.psl-facts, .psl-track, .psl-mini, .psl-badge')).toBeNull();
    const main = document.querySelector('main')!.textContent!;
    for (const absent of ['PM ', 'Route', 'pieces of work', 'Station', 'RFP-', 'Ask me', 'Milestones', 'Documents', 'Money', 'Registers', 'Actions', 'undefined']) {
      expect(main).not.toContain(absent);
    }
  });
});

describe('state tags come from the enum', () => {
  const states = Object.keys(STATE_TAGS) as Line['state'][];
  it.each(states)('%s renders its CMP-05 words and tone', async (state) => {
    respond = () => json(200, { case_id: 'P-1', title: 'One', lines: [{ line: 'A line', state, work_id: 'W-1' }], next: 'Next.' });
    await open('P-1');
    const tag = lineItems()[0].querySelector('.psl-tag')!;
    expect(tag.textContent).toBe(STATE_TAGS[state].text);
    expect(tag.className).toContain(`psl-tag--${STATE_TAGS[state].tone}`);
  });

  it('owner_needed and followup_needed read as on the board', () => {
    expect(STATE_TAGS.owner_needed).toEqual({ text: 'Owner needed', tone: 'person' });
    expect(STATE_TAGS.followup_needed.text).toBe('Stopped: invoice follow-up needed');
  });
});

describe('empty, no access and not open', () => {
  it('P-0105: title, tab bar and What is next stay; No work on this project yet. replaces the list', async () => {
    await open('P-0105');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Sabi Market · web store');
    expect(screen.getByRole('navigation', { name: 'Project' })).toBeTruthy();
    expect(document.querySelector('.psl-callout')!.textContent).toContain('What is next');
    expect(document.querySelector('ol')).toBeNull();
    expect(document.querySelector('.psl-empty')!.textContent).toBe('No work on this project yet.');
  });

  it.each([404, 403])('%s shows the no-access state and nothing from the response or the request', async (status) => {
    respond = () => json(status, { code: 'lagoon_secret_code', message: 'Lagoon Health secret' });
    await open('P-0101');
    const section = screen.getByRole('heading', { level: 1, name: 'You can’t open this project' }).closest('section')!;
    expect(section.textContent).toContain('NO ACCESS');
    expect(section.textContent).toContain('It belongs to work you don’t have access to. Nothing about it is shown here, not even its name.');
    expect(within(section).getByRole('link', { name: 'Back to projects' }).getAttribute('href')).toBe('/projects');
    const text = document.body.textContent!;
    for (const leaked of ['P-0101', 'Lagoon Health', 'lagoon_secret_code']) expect(text).not.toContain(leaked);
    expect(screen.queryByRole('navigation', { name: 'Project' })).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).toBeNull();
  });

  it('P-0102 as pm (the mock 404) shows no access without the title', async () => {
    persona = 'pm';
    await open('P-0102');
    expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Harbour Bank');
  });

  it('without the projects destination: not open, and no E-PROJECT request', async () => {
    destinations = ['my_work'];
    render(page('P-0101'));
    await until(() => expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });

  it('persona none: the frame shows no sections, and no E-PROJECT request', async () => {
    persona = 'none';
    render(page('P-0101'));
    await until(() => expect(screen.getByText('No sections are open to your role yet.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });
});

describe('signed out, failures and stale responses', () => {
  it('401 shows the signed-out callout with next=/projects/P-0101', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101');
  });

  it.each([
    ['500', () => json(500, { code: 'server_down', message: 'x' }), 'server_down'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
    ['malformed 200 (the E-ME body)', () => json(200, me('finance_lead')), 'unexpected_response'],
  ])('%s shows the journey error card; Try again re-reads and recovers', async (_, failure, code) => {
    respond = failure as () => Response;
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toContain('We couldn’t load this project. Your work is safe; nothing was changed.');
    expect(card.textContent).toContain(`Reference ${code} for support.`);
    respond = (url) => mockResponse(url);
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await until(() => expect(lineItems()).toHaveLength(p0101().lines.length));
    expect(calls).toHaveLength(2);
  });

  it('loading shows status; a late response for the previous case_id is ignored', async () => {
    const pending: Record<string, () => void> = {};
    respond = (url) => new Promise<Response>((resolve) => (pending[url.pathname.split('/')[4]] = () => resolve(mockResponse(url))));
    const view = render(page('P-0101'));
    await until(() => expect(pending['P-0101']).toBeTruthy());
    expect(screen.getByRole('status')).toBeTruthy();
    view.rerender(page('P-0104'));
    await until(() => expect(pending['P-0104']).toBeTruthy());
    await act(async () => pending['P-0104']());
    await until(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Delta Foods · ordering app'));
    await act(async () => pending['P-0101']());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Delta Foods · ordering app');
  });

  it('renders no SAMPLE DATA tag of its own, even with the switch on', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open();
    expect(document.querySelector('main .psl-sample')).toBeNull();
  });
});
