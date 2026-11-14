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

type Line = { line: string; state: keyof typeof STATE_TAGS; work_id: string; title?: string; reference?: string; detail?: string };
type Journey = { case_id: string; title: string; lines: Line[]; next: string; agent_summary?: { agent: string; text: string } };
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

const page = (caseId: string, tab?: 'milestones' | 'money') => (
  <AppShell>
    <ProjectJourneyPage caseId={caseId} tab={tab} />
  </AppShell>
);

async function open(caseId = 'P-0101', tab?: 'milestones' | 'money') {
  const result = render(page(caseId, tab));
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByRole('status')).toBeNull());
  return result;
}

const lineItems = () => [...document.querySelectorAll('ol.projects__lines > li')] as HTMLElement[];
const projectTabs = () => within(screen.getByRole('tablist', { name: 'Project' })).getAllByRole('tab');
const facts = () => [...document.querySelectorAll('.psl-fact')].map((f) => [f.querySelector('b')!.textContent, f.querySelector('strong')!.textContent, f.className]);

describe('journey reads E-PROJECT and keeps order (JR-08), drawn as SCR-07', () => {
  it('P-0101: breadcrumb, title, six tabs with counts, PM and route line, facts, lines in order, what is next and Tola', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe('/api/v1/projects/P-0101');
    const body = p0101();
    const crumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(crumb.textContent).toBe('Projects / Lagoon Health');
    expect(within(crumb).getByRole('link', { name: 'Projects' }).getAttribute('href')).toBe('/projects');
    expect(crumb.querySelector('[aria-current="page"]')!.textContent).toBe('Lagoon Health');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(projectTabs().map((t) => [t.textContent, t.getAttribute('href'), t.getAttribute('aria-selected')])).toEqual([
      ['Journey', '/projects/P-0101', 'true'],
      ['Milestones4', '/projects/P-0101/milestones', 'false'],
      ['Documents6', '/projects/P-0101/documents', 'false'],
      ['Money', '/projects/P-0101/money', 'false'],
      ['Registers6', '/projects/P-0101/registers', 'false'],
      ['Actions9', '/projects/P-0101/actions', 'false'],
    ]);
    expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(projectTabs()[0].id);
    expect(document.querySelector('.projects__route')!.textContent).toBe('PM Tunde Bello · Route A from RFP-0031 · 8 pieces of work across 6 lines');
    expect(document.querySelector('.projects__phoneline')!.textContent).toBe('8 pieces of work · 2 waiting on people · 1 stopped');
    expect(screen.getByRole('region', { name: 'Facts earned' })).toBeTruthy();
    expect(facts()).toEqual([
      ['CONTRACT STAGES', '4', 'psl-fact'],
      ['INVOICES VERIFIED', '1', 'psl-fact psl-fact--earned'],
      ['WAITING ON PEOPLE', '2', 'psl-fact psl-fact--current'],
      ['STOPPED', '1', 'psl-fact psl-fact--current'],
      ['NEXT MILESTONE', 'UAT sign-off', 'psl-fact'],
      ['PAID', 'Finance tracks', 'psl-fact'],
    ]);
    expect(screen.getByRole('heading', { level: 2, name: 'The whole journey, oldest first' })).toBeTruthy();
    expect(lineItems()).toHaveLength(8);
    expect(lineItems().map((li) => within(li).getAllByRole('link').map((a) => a.getAttribute('href')))).toEqual(
      body.lines.map((l) => [`/work/${l.work_id}`]),
    );
    expect(lineItems().map((li) => li.querySelector('.projects__linename')!.textContent)).toEqual(body.lines.map((l) => l.title));
    expect(lineItems()[6].textContent).toBe('Invoice · Milestone 2 INV-0412Station 4 of 7 · Finance reviewWaiting');
    expect(lineItems().map((li) => li.querySelector('.projects__dot')!.className.split('--')[1])).toEqual([
      'done',
      'done',
      'done',
      'done',
      'done',
      'waiting',
      'waiting',
      'person',
    ]);
    expect(document.querySelector('.projects__next')!.textContent).toBe(`What is next ${body.next}`);
    const tola = screen.getByRole('complementary', { name: "Tola's summary" });
    expect(tola.textContent).toContain('Tola · PMO agent');
    const paragraphs = body.agent_summary!.text.split('\n\n');
    expect(paragraphs).toHaveLength(2);
    expect([...tola.querySelectorAll('.projects__agentbody p')].slice(0, 2).map((p) => p.textContent)).toEqual(paragraphs);
    expect(within(tola).getByRole('link', { name: 'Ask me about this project' }).getAttribute('href')).toBe('/assistant');
  });

  it('server order is kept exactly; repeated line names carry their reference or state in the link name (UX-1-1)', async () => {
    const lines: Line[] = [
      { line: 'Zulu line', state: 'verified', work_id: 'W-9' },
      { line: 'Alpha line', state: 'waiting', work_id: 'W-1' },
      { line: 'Zulu line', state: 'ready', work_id: 'W-5', reference: 'INV-5' },
    ];
    respond = () => json(200, { case_id: 'P-7', title: 'Seven', lines, next: 'Nothing yet.' });
    await open('P-7');
    expect(lineItems().map((li) => li.querySelector('a')!.getAttribute('href'))).toEqual(['/work/W-9', '/work/W-1', '/work/W-5']);
    expect(lineItems().map((li) => li.querySelector('a')!.textContent)).toEqual(['Zulu line, Verified', 'Alpha line', 'Zulu line, INV-5']);
  });

  it('a body without the PROPOSAL fields still draws every board element, with unknowns as Not known', async () => {
    respond = () =>
      json(200, { case_id: 'P-7', title: 'Kora Logistics · fleet tracker', lines: [{ line: 'RFP response', state: 'verified', work_id: 'W-9' }], next: 'Next.' });
    await open('P-7');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('Projects / Kora Logistics');
    expect(projectTabs().map((t) => t.textContent)).toEqual(['Journey', 'Milestones', 'Documents', 'Money', 'Registers', 'Actions']);
    expect(document.querySelector('.projects__route')!.textContent).toBe('1 piece of work across 1 line');
    expect(document.querySelector('.projects__phoneline')!.textContent).toBe('1 piece of work');
    expect(facts().map(([, value, cls]) => [value, cls])).toEqual(Array(6).fill(['Not known', 'psl-fact psl-fact--unknown']));
    expect(lineItems()[0].querySelector('.projects__linename')!.textContent).toBe('RFP response');
    expect(screen.getByRole('complementary').textContent).toContain('Tola has not summarised this project yet.');
    expect(document.querySelector('main')!.textContent).not.toContain('undefined');
  });

  it('PROPOSAL fields in another shape degrade to Not known instead of throwing; a line station stands in for detail (TECH-2-1)', async () => {
    respond = () =>
      json(200, {
        case_id: 'P-7',
        title: 'Kora Logistics · fleet tracker',
        lines: [
          { line: 'Prepare an invoice', state: 'waiting', work_id: 'W-9', title: { text: 'x' }, reference: 7, station: { index: 4, count: 7, name: 'Finance review' } },
        ],
        next: 'Next.',
        pm: 'Tunde Bello',
        route: { name: 'Route A' },
        facts: { contract_stages: 4 },
        agent_summary: { agent: 'Tola', paragraphs: ['Old shape.'] },
        tab_counts: { milestones: '4', documents: 2 },
      });
    await open('P-7');
    expect(document.querySelector('.projects__route')!.textContent).toBe('1 piece of work across 1 line');
    expect(facts().map(([, value]) => value)).toEqual(Array(6).fill('Not known'));
    expect(lineItems()[0].textContent).toBe('Prepare an invoiceStation 4 of 7 · Finance reviewWaiting');
    expect(projectTabs().map((t) => t.textContent)).toEqual(['Journey', 'Milestones', 'Documents2', 'Money', 'Registers', 'Actions']);
    expect(screen.getByRole('complementary').textContent).toContain('Tola has not summarised this project yet.');
    expect(document.querySelector('main')!.textContent).not.toMatch(/undefined|object Object/);
  });

  it('v7 PROPOSAL shapes: PM object, work and line counts, money and unknown facts, a Chidi summary', async () => {
    respond = () =>
      json(200, {
        case_id: 'P-8',
        title: 'Kora Logistics · fleet tracker',
        lines: [],
        next: 'Next.',
        pm: { name: 'Kunle Ade', is_you: false },
        work_count: 12,
        line_count: 5,
        facts: [
          { label: 'Paid', money: { amount: '4250000.00', currency: 'NGN', unknown: false } },
          { label: 'Invoiced', money: { currency: 'NGN', unknown: true } },
          { label: 'Stopped', value: '0' },
          { label: '' },
        ],
        agent_summary: { agent: 'chidi', text: 'One paragraph.' },
      });
    await open('P-8');
    expect(document.querySelector('.projects__route')!.textContent).toBe('PM Kunle Ade · 12 pieces of work across 5 lines');
    expect(document.querySelector('.projects__phoneline')!.textContent).toBe('12 pieces of work · 0 stopped');
    expect(facts()).toEqual([
      ['Paid', '₦4,250,000.00', 'psl-fact'],
      ['Invoiced', 'Not known', 'psl-fact psl-fact--unknown'],
      ['Stopped', '0', 'psl-fact'],
    ]);
    const chidi = screen.getByRole('complementary', { name: "Chidi's summary" });
    expect(chidi.textContent).toContain('Chidi · Finance agent');
    expect(chidi.textContent).toContain('One paragraph.');
  });

  it('arrow keys move focus along the project tabs; the other tabs open a coming-next panel', async () => {
    await open();
    projectTabs()[0].focus();
    fireEvent.keyDown(projectTabs()[0], { key: 'ArrowRight' });
    expect(document.activeElement).toBe(projectTabs()[1]);
    fireEvent.keyDown(projectTabs()[1], { key: 'End' });
    expect(document.activeElement).toBe(projectTabs()[5]);
    fireEvent.keyDown(projectTabs()[5], { key: 'ArrowRight' });
    expect(document.activeElement).toBe(projectTabs()[0]);
  });
});

describe('tabs other than Journey (contents come with FE-M3-PROJECT-TABS)', () => {
  it.each([
    ['milestones', 'Milestones come next', 1],
    ['money', 'Money comes next', 3],
  ] as const)('%s: same header, the tab selected and a coming-next panel instead of the journey', async (tab, heading, index) => {
    await open('P-0101', tab);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(projectTabs()[index].getAttribute('aria-selected')).toBe('true');
    expect(projectTabs()[index].tabIndex).toBe(0);
    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('aria-labelledby')).toBe(projectTabs()[index].id);
    expect(within(panel).getByRole('heading', { level: 2, name: heading })).toBeTruthy();
    expect(within(panel).getByRole('link', { name: 'Open the journey' }).getAttribute('href')).toBe('/projects/P-0101');
    expect(lineItems()).toHaveLength(0);
    expect(calls).toHaveLength(1);
  });

  it('401 on a tab signs in back to that tab', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open('P-0101', 'milestones');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101%2Fmilestones');
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
    expect(screen.getByRole('tablist', { name: 'Project' })).toBeTruthy();
    expect(document.querySelector('.projects__next')!.textContent).toContain('What is next');
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
    expect(screen.queryByRole('tablist', { name: 'Project' })).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).toBeNull();
  });

  it('P-0104 as pm (the mock 404) shows no access without the title', async () => {
    persona = 'pm';
    await open('P-0104');
    expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this project' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Delta Foods');
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
