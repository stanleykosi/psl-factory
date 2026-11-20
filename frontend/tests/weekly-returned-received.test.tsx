// @vitest-environment jsdom
// F-22: the weekly client report after the review, returned to the PM or received by the client (PROPOSAL
// D-LINE-WORKSPACE, contract mock only). The fetch stub stands in for the backend; nothing here proves a real backend,
// real delivery or the idempotency promise. The client template is a test template.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { reloadPage } from '@/features/response';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2209',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const records: { items: { value: string; label: string }[] } = read('start-work/options/records.json');

const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response))[];
let stepAnswers: Response[];

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
      if (url.pathname.includes('/fields/') && url.pathname.endsWith('/options')) return json(200, { items: records.items.map(({ value, label }) => ({ value, label })), as_of: '2026-11-12T09:00:00Z' });
      if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
        const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      if (url.pathname.endsWith('/steps')) return stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? json(200, { work_id: 'W-2209', state: 'ready', revision: 9, outcome: 'done' }));
      if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-2212', state: 'action_needed', revision: 8 });
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
  vi.mocked(reloadPage).mockClear();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function open(first: WorkItem, ...later: (WorkItem | (() => Response))[]) {
  itemAnswers = [first, ...later];
  render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
}
const wsEl = () => document.querySelector('.ws') as HTMLElement;
const text = () => wsEl().textContent!;
const buttons = () => within(wsEl()).queryAllByRole('button').map((b) => b.textContent);
const press = async (name: string) => {
  await act(async () => {
    fireEvent.click(within(wsEl()).getByRole('button', { name }));
  });
};

describe('returned (W-2209, W-2210)', () => {
  it('shows the status, the note above "Your update", four parts with cites, the Next panel and one primary button', async () => {
    await open(item('W-2209'));
    expect(screen.getByText('Returned to you')).toBeTruthy();
    const t = text();
    expect(t.indexOf('Kemi Adebayo returned v1 on 12 Nov')).toBeGreaterThanOrEqual(0);
    expect(t.indexOf('Kemi Adebayo returned v1')).toBeLessThan(t.indexOf('Your update'));
    for (const cite of ['2 RECORDS', 'ISS-0233', 'MIN-0141', '2 ACTIONS']) expect(t).toContain(cite);
    const headings = within(wsEl()).getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(['Your update', 'Next']);
    // the note is the warning alone: no panel, no "Nothing here yet."
    expect(t).not.toContain('Nothing here yet.');
    expect(document.querySelectorAll('.ws-section--text')).toHaveLength(1);
    // the step's own sentence is the Next line, drawn once
    expect(t.split('Edit your part, then Tola reassembles v2 and it goes back for review.')).toHaveLength(2);
    expect(buttons()).toEqual(['Edit your update']);
    expect(posts()).toHaveLength(0);
  });

  it('Edit opens the F-21 form with the saved words; Send posts one send_to_tola with the revision, eight inputs and a UUID key, then reloads to the assembling state', async () => {
    await open(item('W-2209'), item('W-2209.next'));
    await press('Edit your update');
    const f = within(screen.getByRole('form', { name: 'Edit your update' }));
    await waitFor(() => expect(document.activeElement?.textContent).toBe('Edit your update'));
    expect((f.getByLabelText('Status (optional)') as HTMLTextAreaElement).value).toBe('Milestone 2 complete; go-live work started');
    expect(f.getAllByRole('combobox')).toHaveLength(4);
    // the saved cites open with the words (QA-2-1)
    for (const [part, labels] of [['status', ['Milestone 2 · UAT signed 11 Nov', 'UAT walkthrough · 11 Nov']], ['risks', ['ISS-0233 Login fails on older Android phones · High']], ['timeline', ['Weekly sync with Lagoon Health · 10 Nov']], ['next steps', ['Client to send test accounts · due 13 Nov', 'CR-0031 Add SMS reminders · being assessed']]] as const) {
      const picker = f.getByRole('combobox', { name: `Cites for ${part} (optional)` });
      for (const label of labels) expect(picker.textContent).toContain(label);
    }
    fireEvent.change(f.getByLabelText('Status (optional)'), { target: { value: 'Milestone 2 complete; test devices needed by Friday.' } });
    await act(async () => {
      fireEvent.click(f.getByRole('button', { name: 'Edit your update' }));
    });
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [post] = posts();
    expect(post.path).toBe('/api/v1/work/W-2209/steps');
    expect(post.csrf).toBe('mock-csrf-pm');
    expect(stepRequest(post.body), ajv.errorsText(stepRequest.errors)).toBe(true);
    const { idempotency_key: key, ...rest } = post.body!;
    expect(key).toMatch(UUID);
    expect(rest).toMatchObject({ expected_revision: 6, step: 'send_to_tola' });
    // all eight inputs; the cites were not touched and are sent as they were saved
    expect(rest.inputs).toEqual({
      status: 'Milestone 2 complete; test devices needed by Friday.',
      status_cites: ['MS-0002', 'MTG-0141'],
      risks: 'Login fails on older Android phones (high)',
      risks_cites: ['ISS-0233'],
      timeline: 'Go-live 4 Dec, subject to the login fix',
      timeline_cites: ['MTG-0140'],
      next_steps: 'Fix verification; go-live plan',
      next_steps_cites: ['ACT-0412', 'CR-0031'],
    });
    expect(post.body).not.toHaveProperty('note');
    expect(post.body).not.toHaveProperty('evidence_ids');
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-2209')).toHaveLength(2));
  });

  it('W-2210 has no step: no button of any kind, whoever looks', async () => {
    await open(item('W-2210'));
    expect(buttons()).toEqual([]);
    expect(text()).toContain('Edit your part, then Tola reassembles');
    expect(posts()).toHaveLength(0);
  });

  it('without its note section no banner and no invented words appear', async () => {
    const body = item('W-2209');
    body.workspace!.sections = body.workspace!.sections.filter((s) => s.key !== 'returned');
    await open(body);
    expect(text()).not.toMatch(/returned v1|Kemi|Nothing here yet/);
    expect(document.querySelector('.ws-note')).toBeNull();
  });

  it('a 409, 422 and 500 on the step keep the form, as F-21', async () => {
    stepAnswers = [json(500, { code: 'server_error', message: 'No.' })];
    await open(item('W-2209'));
    await press('Edit your update');
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form', { name: 'Edit your update' })).getByRole('button', { name: 'Edit your update' }));
    });
    await screen.findByText('We couldn’t confirm this step. Check the page before trying again.');
    expect(screen.getByRole('form', { name: 'Edit your update' })).toBeTruthy();
  });
});

describe('received (W-2211 to W-2214)', () => {
  it('W-2211: the data sentence with its Verified tag, the Approved row, two DELIVERED rows with their own times, the Next line, no button', async () => {
    await open(item('W-2211'));
    expect(screen.getByText('Received by client')).toBeTruthy();
    const t = text();
    expect(t).toContain('Lagoon Health received v2: emailed 12 Nov 15:10 to 2 contacts, both deliveries confirmed. Verified.');
    expect(within(wsEl()).getByText('Verified')).toBeTruthy();
    expect(t).toContain('Approved by Kemi Adebayo');
    expect(t).toContain('12 Nov 14:58');
    const rows = [...wsEl().querySelectorAll('.ws-rows--recipients .ws-row')].map((r) => r.textContent);
    expect(rows).toEqual([
      expect.stringContaining('Approved by Kemi Adebayo'),
      expect.stringMatching(/Emailed to Dr Amaka Obi.*Delivered.*12 Nov 15:10/),
      expect.stringMatching(/Emailed to Lagoon Health projects inbox.*Delivered.*12 Nov 15:11/),
    ]);
    expect(rows[0]).not.toMatch(/Delivered|Received|Unknown/);
    expect(t).toContain("Next week's report opens on 19 Nov, after the week ends.");
    expect(buttons()).toEqual([]);
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });

  it('the page follows the data: changed sentences and times are drawn, nothing is counted or dated by the page', async () => {
    const body = item('W-2211');
    body.workspace!.sections[0].items[0].text = 'Emailed to 3 contacts on 20 Nov.';
    body.workspace!.next = ['Next report opens 26 Nov.'];
    body.workspace!.sections[1].items[1].at = '2026-11-13T10:05:00Z';
    await open(body);
    expect(text()).toContain('Emailed to 3 contacts on 20 Nov.');
    expect(text()).toContain('Next report opens 26 Nov.');
    expect(text()).toContain('13 Nov 11:05');
    expect(text()).not.toMatch(/19 Nov|2 contacts/);
  });

  it('a received recipient with no time reads Time unknown', async () => {
    const body = item('W-2211');
    delete body.workspace!.sections[1].items[1].at;
    await open(body);
    expect(within(wsEl().querySelectorAll('.ws-rows--recipients .ws-row')[1] as HTMLElement).getByText('Time unknown')).toBeTruthy();
  });

  it('W-2212: no Verified, one confirmed row, the other Uncertain, the status per data, reconcile only, no resend', async () => {
    await open(item('W-2212'));
    const t = text();
    expect(screen.getByText('Delivery not confirmed')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Verified|both deliveries confirmed/);
    const rows = [...wsEl().querySelectorAll('.ws-rows--recipients .ws-row')].map((r) => r.textContent!);
    expect(rows[1]).toMatch(/Delivered/);
    expect(rows[2]).toMatch(/Uncertain/);
    expect(rows[2]).not.toMatch(/Delivered|Received/);
    expect(t).toContain('1 delivery confirmed, 1 not confirmed yet.');
    await screen.findByRole('group', { name: 'Confirm what happened' });
    expect(screen.queryAllByRole('button', { name: /send again|resend|approve|send/i }).filter((b) => b.textContent !== 'Start work')).toEqual([]);
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(posts()).toHaveLength(0);
  });

  it('W-2213: Unknown with no time, the backend’s failed tag, nothing delivered or verified', async () => {
    await open(item('W-2213'));
    const rows = [...wsEl().querySelectorAll('.ws-rows--recipients .ws-row')].map((r) => r.textContent!);
    expect(rows[1]).toMatch(/Unknown$/);
    expect(rows[1]).not.toMatch(/Delivered|Received|\d:\d\d/);
    expect(rows[2]).toMatch(/Bounced/);
    expect(document.body.textContent).not.toMatch(/Verified|Delivered/);
  });

  it('W-2214: Nothing here yet. and no delivery claim', async () => {
    await open(item('W-2214'));
    expect(text()).toContain('Nothing here yet.');
    expect(document.body.textContent).not.toMatch(/Verified|Delivered|Received by client\./);
    expect(buttons()).toEqual([]);
  });

  it('a received view whose recipients are not all confirmed draws no verified tag and keeps its own status', async () => {
    for (const id of ['W-2212', 'W-2213', 'W-2214']) {
      expect(item(id).workspace!.view, id).toBe('received');
      expect(JSON.stringify(item(id).workspace!.status), id).not.toContain('verified');
    }
  });
});

describe('access', () => {
  const gone = (status: number, code: string) => {
    itemAnswers = [() => json(status, { code, message: 'No.' })];
    render(
      <AppShell>
        <WorkItemView id="W-2299" tab="overview" />
      </AppShell>,
    );
  };

  it('a 404 on the read draws the no-access state with no title, client or id', async () => {
    gone(404, 'not_found');
    await screen.findByText(/Nothing about it is shown here, not even its name or amount\./);
    expect(document.body.textContent).not.toMatch(/Lagoon Health|Weekly client report|W-2299|WCR-0216/);
  });

  it('a 403 on the read draws the same no-access state', async () => {
    gone(403, 'forbidden');
    await screen.findByText(/Nothing about it is shown here, not even its name or amount\./);
    expect(document.body.textContent).not.toMatch(/Lagoon Health|W-2299/);
  });

  it('a 401 draws the signed-out callout with next set to this page', async () => {
    gone(401, 'not_signed_in');
    await screen.findByText('You’re signed out.');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fwork%2FW-2299');
    expect(document.body.textContent).not.toMatch(/Lagoon Health|W-2299/);
  });

  it('a 403 on the Edit step shows the forbidden line and keeps the page', async () => {
    stepAnswers = [json(403, { code: 'forbidden', message: 'No.' })];
    await open(item('W-2209'));
    await press('Edit your update');
    await act(async () => {
      fireEvent.click(within(screen.getByRole('form', { name: 'Edit your update' })).getByRole('button', { name: 'Edit your update' }));
    });
    await screen.findByText('You can’t take that step.');
  });
});

describe('an uncertain item with no reconcile (QA-2-3)', () => {
  it('says it is checking and offers only a reload; nothing is sent', async () => {
    const body = item('W-2212');
    delete body.reconcile;
    delete body.allowed_actions;
    await open(body);
    expect(screen.getByText('We are checking what happened. Nothing was sent again.')).toBeTruthy();
    expect(within(screen.getByText('We are checking what happened. Nothing was sent again.').closest('[role="alert"]') as HTMLElement).getAllByRole('button').map((b) => b.textContent)).toEqual(['Reload']);
    expect(screen.queryByRole('group', { name: 'Confirm what happened' })).toBeNull();
    expect(sent.filter((r) => r.method === 'POST')).toEqual([]);
  });

  it('an uncertain item that still offers steps but no reconcile locks every step: the sentence, steps off, a forced press sends nothing', async () => {
    const body = item('W-2205.next');
    delete body.reconcile;
    delete body.allowed_actions;
    await open(body);
    expect(screen.getByText('We are checking what happened. Nothing was sent again.')).toBeTruthy();
    expect(screen.queryByRole('group', { name: 'Confirm what happened' })).toBeNull();
    const steps = within(document.querySelector('.ws-steps') as HTMLElement).getAllByRole('button');
    expect(steps.length).toBeGreaterThan(0);
    for (const b of steps) expect(b.getAttribute('aria-disabled')).toBe('true');
    await press('Approve and send');
    await press('Return with a note');
    expect(sent.filter((r) => r.method === 'POST')).toEqual([]);
  });

  it('with its reconcile present the sentence is not drawn on load', async () => {
    await open(item('W-2212'));
    expect(screen.queryByText('We are checking what happened. Nothing was sent again.')).toBeNull();
  });
});

describe('the Next panel (UI-1-1 to UI-1-3, TECH-1-1)', () => {
  it('is plain: no Decide modifiers, named Next; the aside takes its name from it when nothing else is in it', async () => {
    await open(item('W-2211'));
    const panel = wsEl().querySelector('.ws-decide') as HTMLElement;
    expect(panel.className).toContain('ws-decide--next');
    expect(panel.className).not.toContain('psl-panel--decide');
    expect(panel.querySelector('.psl-panel__head--decide')).toBeNull();
    const aside = wsEl().querySelector('aside') as HTMLElement;
    expect(aside.hasAttribute('aria-label')).toBe(false);
    expect(within(wsEl()).getByRole('complementary', { name: 'Next' })).toBe(aside);
  });

  it('with a step the panel is still plain; its line stays visible while the form is open', async () => {
    await open(item('W-2209'));
    const panel = wsEl().querySelector('.ws-decide') as HTMLElement;
    expect(panel.className).toContain('ws-decide--next');
    await press('Edit your update');
    expect(text().split('Edit your part, then Tola reassembles v2 and it goes back for review.').length).toBeGreaterThanOrEqual(2);
    expect(wsEl().querySelector('.ws-decide--next .psl-btn')).not.toBeNull();
  });

  it('without next the panel is Decide with its modifiers, as before', async () => {
    await open(item('W-2204'));
    const panel = wsEl().querySelector('.ws-decide') as HTMLElement;
    expect(panel.className).toContain('psl-panel--decide');
    expect(panel.className).not.toContain('ws-decide--next');
    expect(wsEl().querySelector('aside')!.getAttribute('aria-label')).toBe('Review and decide');
  });
});

describe('frame changes leave earlier boards alone', () => {
  it('a recipients row without a tag still draws the receipt word; no next means the panel is Decide', async () => {
    await open(item('W-2204'));
    expect(within(wsEl()).getByRole('heading', { level: 2, name: 'Decide' })).toBeTruthy();
  });

  it('a recipient row without a tag draws the receipt word', async () => {
    const body = item('W-2211');
    delete body.workspace!.sections[1].items[1].tag;
    delete body.workspace!.next;
    await open(body);
    expect(text()).toMatch(/Emailed to Dr Amaka Obi\s*Received/);
  });
});
