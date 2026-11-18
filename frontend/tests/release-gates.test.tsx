// @vitest-environment jsdom
// F-32 SCR-44: the release work item drawn by the line workspace frame (contract mock only). Three states from data,
// decision controls only from the task's `you_can_act`, no write from the work page, verified only from the returned status.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { workspaceLinks } from '@/features/workspace/proposals';
import { AppShell } from '@/shell/AppShell';

import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2501',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (id: string): WorkItem => read(`work/${id}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let persona = 'pm';
const requests = () => fetchStub.mock.calls.map(([request]) => `${request.method} ${new URL(request.url).pathname}`);

beforeEach(() => {
  persona = 'pm';
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', withoutBellFeed(fetchStub));
});
afterEach(() => vi.unstubAllGlobals());

async function open(body: WorkItem, status = 200) {
  fetchStub.mockImplementation(async (request) => {
    if (new URL(request.url).pathname === '/api/v1/me') return json(200, read(`me.${persona}.json`));
    return status === 200 ? json(200, body) : json(status, { code: 'x', message: 'We could not find that record.' });
  });
  const view = render(
    <AppShell>
      <WorkItemView id={body.id} tab="overview" />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
  if (status === 200) await screen.findByRole('heading', { level: 1, name: body.title });
  return view;
}

const decisionControls = () => ['Approve for release', 'Return with a note'].map((name) => screen.getByText(name, { selector: 'a, button' }));

describe('three states from data', () => {
  it('W-2501 waiting: status, four gates, Tola checks, the task statement, Ask Tola, and no decision control', async () => {
    await open(item('W-2501'));
    expect(screen.getByText('Release · waiting on PMO Lead').className).toContain('psl-tag--person');
    const gates = screen.getByRole('region', { name: 'Release gates · build 1.0.0' });
    expect(within(gates).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      expect.stringContaining('PMO Lead assigned · Kemi Adebayo'),
      expect.stringContaining('Client UAT response recorded'),
      expect.stringContaining('Planning decision Waiting for PMO Lead'),
      expect.stringContaining('Release readiness'),
    ]);
    expect(screen.getByRole('region', { name: 'Checked release progress' }).textContent).toContain('As of 23 Mar 10:12 WAT');
    expect(screen.getByText('Only a PMO Lead can decide.')).toBeTruthy();
    expect(screen.queryByText('Approve for release')).toBeNull();
    expect(screen.queryByText('Open the decision')).toBeNull();
    expect(screen.getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(screen.queryByText('Open go-live')).toBeNull();
  });

  it('W-2502 decision: facts, Tola checks, Approve and Return as links to the decision page, and no Open go-live', async () => {
    await open(item('W-2502'));
    expect(screen.getByText('Your decision', { selector: '.psl-tag' })).toBeTruthy();
    const facts = screen.getByRole('region', { name: 'What you’re deciding' });
    expect(facts.textContent).toContain('4 of 4 stages built');
    expect(facts.textContent).toContain('1 medium · 0 high');
    for (const control of decisionControls()) {
      expect(control.tagName).toBe('A');
      expect(control.getAttribute('href')).toBe('/work/W-2502/decide?task=T-2502');
    }
    expect(screen.queryByText('Open go-live')).toBeNull();
  });

  it('W-2503 ready: the green banner, the readiness note, Next and Open go-live linking to W-2510', async () => {
    await open(item('W-2503'));
    expect(screen.getByText('Release ready', { selector: '.psl-tag' }).className).toContain('psl-tag--done');
    const banner = screen.getByText(/Release ready and verified on 25 Mar/);
    expect(banner.closest('.psl-callout')!.className).toContain('success');
    expect(screen.getByRole('region', { name: 'Readiness note · by Tola' }).textContent).toContain('Rollback plan');
    expect(screen.getByRole('heading', { name: 'Next' }).parentElement!.textContent).toContain('Tola drafts the go-live document for the client.');
    expect(screen.getByRole('link', { name: 'Open go-live' }).getAttribute('href')).toBe('/work/W-2510');
  });
});

describe('decision controls only from you_can_act', () => {
  for (const [id, sentence] of [
    ['W-2504', 'This decision needs a PMO Lead.'],
    ['W-2505', 'You prepared Release gates · build 1.0.0, so someone else must review it.'],
    ['W-2506', 'This decision isn’t open to you here.'],
  ] as const) {
    it(`${id}: both controls are unavailable, with no href, described by the reason`, async () => {
      await open(item(id));
      for (const control of decisionControls()) {
        expect(control.getAttribute('aria-disabled')).toBe('true');
        expect(control.getAttribute('href')).toBeNull();
        const reason = control.getAttribute('aria-describedby')!.split(' ').map((i) => document.getElementById(i)!.textContent);
        expect(reason.join(' ')).toContain(sentence);
      }
      expect(document.querySelector('a[href*="/decide"]')).toBeNull();
    });
  }

  it('the persona does not change the controls for the same fixture, and the page reads no /me for authority beyond the frame', async () => {
    const seen: string[][] = [];
    for (const who of ['pm', 'finance_lead', 'ceo']) {
      persona = who;
      const view = await open(item('W-2502'));
      seen.push(decisionControls().map((c) => `${c.tagName} ${c.getAttribute('href')}`));
      view.unmount();
    }
    expect(seen[1]).toEqual(seen[0]);
    expect(seen[2]).toEqual(seen[0]);
    const grep = (file: string) => readFileSync(join(__dirname, '..', file), 'utf8');
    for (const file of ['src/features/workspace/Steps.tsx', 'src/features/workspace/Workspace.tsx', 'src/features/projects/DeliveryTab.tsx']) expect(grep(file)).not.toMatch(/useMe\(/);
  });

  it('pressing either link on W-2502 sends no claim, decision or step request from the work page', async () => {
    await open(item('W-2502'));
    for (const control of decisionControls()) fireEvent.click(control);
    expect(requests().filter((r) => r.startsWith('POST'))).toEqual([]);
    expect(requests().some((r) => /claim|decision|steps/.test(r))).toBe(false);
  });
});

describe('verified only from the backend', () => {
  it('W-2508, whose agent step "Mark release ready" is done, shows no banner, no Release ready and no Open go-live', async () => {
    await open(item('W-2508'));
    expect(screen.queryByText(/Release ready/)).toBeNull();
    expect(document.querySelector('.ws-note')).toBeNull();
    expect(document.querySelector('.psl-callout--success')).toBeNull();
    expect(screen.queryByText('Open go-live')).toBeNull();
    expect(screen.getByText('Preparing', { selector: '.psl-tag' })).toBeTruthy();
  });

  it('the same banner text with tone person draws the warning banner, not the green one', async () => {
    const body = item('W-2503');
    body.workspace!.status = { label: 'Release ready', tone: 'person' };
    await open(body);
    const callout = screen.getByText(/Release ready and verified on 25 Mar/).closest('.psl-callout')!;
    expect(callout.className).toContain('warning');
    expect(callout.className).not.toContain('success');
  });
});

describe('unknown, not zero', () => {
  it('W-2507: Open issues reads Unknown, the unknown check reads Unknown, and Tola has no time line', async () => {
    await open(item('W-2507'));
    const facts = screen.getByRole('region', { name: 'What you’re deciding' });
    expect(within(facts).getByText('Open issues').nextElementSibling!.textContent).toBe('Unknown');
    const checks = screen.getByRole('region', { name: 'Checked release progress' });
    expect(checks.textContent).toContain('Unknown');
    expect(checks.querySelector('time')).toBeNull();
    expect(document.querySelector('main')!.textContent).not.toMatch(/undefined|NaN/);
  });
});

describe('links only from data', () => {
  const link = (target: object) => ({ workspace: { links: [{ key: 'k', label: 'Open go-live', target }] } }) as unknown as { workspace: NonNullable<WorkItem['workspace']> };
  const links = (target: object) => workspaceLinks(link(target).workspace);
  it('a work link needs a valid work id; any other kind or id draws nothing', () => {
    expect(links({ kind: 'work', work_id: 'W-2510' })).toEqual([{ key: 'k', label: 'Open go-live', kind: 'work', href: '/work/W-2510' }]);
    for (const target of [{ kind: 'work', work_id: '../x' }, { kind: 'work', work_id: '' }, { kind: 'work' }, { kind: 'work', work_id: 'W-1/../x' }, { kind: 'mystery', work_id: 'W-2510' }]) {
      expect(links(target)).toEqual([]);
    }
  });
});

describe('access', () => {
  for (const status of [403, 404]) {
    it(`${status} looks the same and shows no title, project or reference`, async () => {
      await open(item('W-2502'), status);
      expect(document.body.textContent).not.toMatch(/Lagoon|REL-0091|Approve for release|Kemi/);
    });
  }
  it('401 shows the signed-out state with next set to the work page', async () => {
    await open(item('W-2502'), 401);
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toContain('next=');
  });
});
