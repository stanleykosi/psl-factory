// @vitest-environment jsdom
// D-170: a tab change keeps the page's frame (breadcrumb or eyebrow, title, tab bar) and only the tab's content shows a
// skeleton. Project, work item (Overview, History) and the RFP frame; Setup is in setup-rules.test.tsx. The fetch stub
// stands in for the backend; a failed or no-access read never shows the frame (INV-ACCESS).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectLayoutFrame, ProjectTabBody } from '@/features/projects/ProjectJourney';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemHistoryPane, WorkItemLayoutFrame, WorkItemOverviewPane } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';

const pathname = { value: '/projects/P-0101' };
vi.mock('next/navigation', () => ({
  usePathname: () => pathname.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const never = () => new Promise<Response>(() => {});

type Answer = (url: URL) => Response | Promise<Response>;
let calls: URL[];
let answer: Answer;
beforeEach(() => {
  calls = [];
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(
      vi.fn(async (request: Request) => {
        const url = new URL(request.url);
        if (url.pathname === '/api/v1/me') return json(200, read('me.finance_lead.json'));
        calls.push(url);
        return answer(url);
      }),
    ),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const h1 = () => screen.getByRole('heading', { level: 1 });

describe('project tabs share one frame and one read', () => {
  const project = () => json(200, projects({ operationId: 'E-PROJECT', url: new URL('http://x/api/v1/projects/P-0101'), persona: 'finance_lead' }).body);
  const tree = () => (
    <AppShell>
      <ProjectLayoutFrame caseId="P-0101">
        <ProjectTabBody />
      </ProjectLayoutFrame>
    </AppShell>
  );
  const reads = () => calls.filter((u) => u.pathname === '/api/v1/projects/P-0101');

  it('changing tab keeps the title and tab bar, reads the project once, and shows a skeleton only in the panel', async () => {
    pathname.value = '/projects/P-0101';
    answer = (url) => (url.pathname === '/api/v1/projects/P-0101' ? project() : never());
    const view = render(tree());
    await waitFor(() => expect(h1()).toBeTruthy());
    const title = h1();
    const tabs = screen.getByRole('tablist', { name: 'Project' });
    expect(within(tabs).getByRole('tab', { name: 'Journey' }).getAttribute('aria-selected')).toBe('true');

    pathname.value = '/projects/P-0101/milestones';
    view.rerender(tree());
    expect(h1()).toBe(title);
    expect(screen.getByRole('tablist', { name: 'Project' })).toBe(tabs);
    expect(within(tabs).getByRole('tab', { name: /^Milestones/ }).getAttribute('aria-selected')).toBe('true');
    const panel = screen.getByRole('tabpanel', { name: 'Milestones' });
    await waitFor(() => expect(within(panel).getByRole('status')).toBeTruthy());
    expect(reads()).toHaveLength(1);
  });

  it.each([
    ['no access', 403],
    ['not found', 404],
    ['a failed read', 500],
  ])('%s: no title, tabs or project name show', async (_name, status) => {
    pathname.value = '/projects/P-0101';
    answer = () => json(status, { code: status === 500 ? 'server_error' : 'forbidden', message: 'Lagoon Health secret' });
    render(tree());
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(screen.queryByRole('tablist', { name: 'Project' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Lagoon Health/);
  });
});

describe('work item tabs share one frame and one read', () => {
  const W = 'W-1004';
  const item = (): WorkItem => read(`work/${W}.json`);
  const tree = () => (
    <AppShell>
      <WorkItemLayoutFrame id={W}>{pathname.value.endsWith('/history') ? <WorkItemHistoryPane /> : <WorkItemOverviewPane />}</WorkItemLayoutFrame>
    </AppShell>
  );

  it('Overview to History keeps the header and tab bar, reads the item once, and only the history area loads', async () => {
    pathname.value = `/work/${W}`;
    answer = (url) => (url.pathname === `/api/v1/work/${W}` ? json(200, item()) : never());
    const view = render(tree());
    await waitFor(() => expect(h1()).toBeTruthy());
    const title = h1();
    const tabs = screen.getByRole('tablist', { name: 'Work item' });

    pathname.value = `/work/${W}/history`;
    view.rerender(tree());
    expect(h1()).toBe(title);
    expect(screen.getByRole('tablist', { name: 'Work item' })).toBe(tabs);
    expect(within(tabs).getByRole('tab', { name: /^History/ }).getAttribute('aria-selected')).toBe('true');
    await waitFor(() => expect(screen.getAllByRole('status').length).toBeGreaterThan(0));
    expect(calls.filter((u) => u.pathname === `/api/v1/work/${W}`)).toHaveLength(1);
  });

  it.each([403, 404, 500])('a %i read never shows the header or tabs', async (status) => {
    pathname.value = `/work/${W}`;
    answer = () => json(status, { code: status === 500 ? 'server_error' : 'forbidden', message: 'nope' });
    render(tree());
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(screen.queryByRole('tablist', { name: 'Work item' })).toBeNull();
    expect(document.body.textContent).not.toContain(item().title);
  });
});

describe('RFP frame while the next item of the same RFP loads', () => {
  const submission = (id: string): WorkItem => {
    const it = structuredClone(read('work/W-3501.json')) as WorkItem;
    it.id = id;
    it.rfp!.tabs = [
      { key: 'requirements', label: 'Requirements', work_id: 'W-3499' },
      { key: 'submission', label: 'Submission', work_id: 'W-3501' },
    ] as NonNullable<typeof it.rfp>['tabs'];
    return it;
  };
  const tree = (id: string) => (
    <AppShell>
      <WorkItemLayoutFrame id={id}>
        <WorkItemOverviewPane />
      </WorkItemLayoutFrame>
    </AppShell>
  );
  const rfpNav = () => screen.queryByRole('navigation', { name: 'RFP' });

  it('draws the remembered frame with a skeleton under it, then the fresh read; a failed read removes it', async () => {
    pathname.value = '/work/W-3501';
    let next: ((r: Response) => void) | undefined;
    answer = (url) => (url.pathname === '/api/v1/work/W-3501' ? json(200, submission('W-3501')) : new Promise<Response>((r) => (next = r)));
    const view = render(tree('W-3501'));
    await waitFor(() => expect(rfpNav()).toBeTruthy());

    view.rerender(tree('W-3499'));
    await waitFor(() => expect(next).toBeDefined());
    expect(rfpNav()).toBeTruthy();
    expect(screen.getByRole('status')).toBeTruthy();
    next!(json(404, { code: 'not_found', message: 'gone' }));
    await waitFor(() => expect(rfpNav()).toBeNull());
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this work item');
  });

  it('the fresh read replaces the remembered frame', async () => {
    pathname.value = '/work/W-3501';
    let next: ((r: Response) => void) | undefined;
    answer = (url) => (url.pathname === '/api/v1/work/W-3501' ? json(200, submission('W-3501')) : new Promise<Response>((r) => (next = r)));
    const view = render(tree('W-3501'));
    await waitFor(() => expect(rfpNav()).toBeTruthy());
    view.rerender(tree('W-3499'));
    await waitFor(() => expect(next).toBeDefined());
    next!(json(200, submission('W-3499')));
    await waitFor(() => expect(document.querySelector('.shell-loading')).toBeNull());
    expect(rfpNav()).toBeTruthy();
  });

  it('an item the remembered RFP does not list never gets its frame', async () => {
    pathname.value = '/work/W-3501';
    answer = (url) => (url.pathname === '/api/v1/work/W-3501' ? json(200, submission('W-3501')) : never());
    const view = render(tree('W-3501'));
    await waitFor(() => expect(rfpNav()).toBeTruthy());
    view.rerender(tree('W-9999'));
    await waitFor(() => expect(rfpNav()).toBeNull());
    expect(screen.getByRole('status')).toBeTruthy();
  });
});
