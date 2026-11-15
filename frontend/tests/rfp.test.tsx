// @vitest-environment jsdom
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/api/types';
import type { ResponseWorkItem } from '@/features/response';
import { ResponseView } from '@/features/response/ResponseView';
import { OutcomeView } from '@/features/rfp/OutcomeView';
import { WorkItemOverview } from '@/features/work-item/WorkItemOverview';
import { AppShell } from '@/shell/AppShell';
import { bellFeed, isBellFeed } from './bell-feed';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-2103/outcome',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
/** W-21xx items and their sidecars from fixtures/response/work, else the E-RESPONSE sidecars from fixtures/response. */
const item = (name: string): ResponseWorkItem =>
  existsSync(join(fixtures, `response/work/${name}.json`)) ? read(`response/work/${name}.json`) : read(`response/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };
const INVALID = { code: 'invalid', message: 'Check these fields: learned_at.' };

type Call = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { item: Answer; upload: Answer; claim: Answer; respond: Answer; outcome: Answer; followup: Answer };

const posts = (suffix: string) => calls.filter((c) => c.method === 'POST' && c.path.endsWith(suffix));
const writes = () => calls.filter((c) => c.method === 'POST' && !c.path.endsWith('/evidence'));
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.startsWith('/api/v1/work/')).length;

beforeEach(() => {
  calls = [];
  answers = {
    item: (_, c) => json(200, item(c.path.split('/')[4])),
    upload: (n, c) => json(200, { evidence_id: `EV-${c.path.split('/')[4]}-${n + 1}`, sha256: 'a'.repeat(64), case_revision: (c.body!.case_revision as number) + 1 }),
    claim: (_, c) => json(200, { task_id: c.path.split('/')[4], revision: (c.body!.expected_revision as number) + 1, claimed_by: 'Tunde Bello' }),
    respond: (_, c) => json(200, { task_id: c.path.split('/')[4], work_state: 'waiting' }),
    outcome: (_, c) => json(200, { work_id: c.path.split('/')[4], result: c.body!.result, state: 'waiting', revision: 6 }),
    followup: (_, c) => json(200, { work_id: c.path.split('/')[4], status: 'sent', revision: 8 }),
  };
  const n = { item: 0, upload: 0, claim: 0, respond: 0, outcome: 0, followup: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      const url = new URL(request.url);
      const body = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, body: body ? JSON.parse(body) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read('me.pm.json'));
      if (url.pathname.endsWith('/evidence')) return answers.upload(n.upload++, c);
      if (url.pathname.endsWith('/claim')) return answers.claim(n.claim++, c);
      if (url.pathname.endsWith('/response')) return answers.respond(n.respond++, c);
      if (url.pathname.endsWith('/rfp-outcome/followup')) return answers.followup(n.followup++, c);
      if (url.pathname.endsWith('/rfp-outcome')) return answers.outcome(n.outcome++, c);
      return answers.item(n.item++, c);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}
async function settle() {
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
async function openTeam(id = 'W-2101', task = 'T-2101') {
  render(
    <AppShell>
      <ResponseView id={id} taskId={task} />
    </AppShell>,
  );
  await settle();
}
async function openOutcome(id = 'W-2103') {
  render(
    <AppShell>
      <OutcomeView id={id} />
    </AppShell>,
  );
  await settle();
}

const text = () => document.body.textContent ?? '';
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const fileInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
const file = (name = 'proof.pdf', size = 64 * 1024) => new File([new Uint8Array(size).fill(37)], name, { type: 'application/pdf' });
async function addFile(f = file()) {
  const before = posts('/evidence').length;
  fireEvent.change(fileInput(), { target: { files: [f] } });
  await waitFor(() => expect(posts('/evidence')).toHaveLength(before + 1));
  await waitFor(() => expect(screen.queryByText(/Uploading…/)).toBeNull());
}
const choose = (name: string) => fireEvent.click(screen.getByRole('radio', { name }));
const type = (label: string | RegExp, value: string): void => {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
};

describe('RFP frame (from rfp only)', () => {
  it('W-2101 draws reference, title, status, PM and the five tabs with only the returned counts', async () => {
    await openTeam();
    expect(document.querySelector('.rfp-eyebrow')!.textContent).toBe('Pre-sale / RFP · TL-RFP-2026-014');
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Tamarind Loans · loan origination RFP']);
    expect(screen.getByRole('heading', { level: 1 }).className).toContain('shell-title');
    expect(text()).toContain('DEADLINE 28 NOV · 16 DAYS');
    expect(text()).toContain('PM Tunde Bello');
    const nav = screen.getByRole('navigation', { name: 'RFP' });
    expect(nav.querySelector('[role="tablist"]')).toBeNull();
    expect([...nav.children].map((t) => t.textContent)).toEqual(['Requirements64', 'Team input2/4', 'Pricing', 'Submission', 'Outcome']);
    expect([...nav.querySelectorAll('.psl-badge')].map((b) => b.textContent)).toEqual(['64', '2/4']);
    for (const name of ['Requirements', 'Pricing', 'Submission', 'Outcome']) {
      const tab = within(nav).getByText(name);
      expect(tab.closest('a, button')).toBeNull();
      expect(tab.closest('.psl-tab')!.hasAttribute('tabindex')).toBe(false);
    }
    expect(within(nav).getByText('Team input').closest('[aria-current="page"]')).toBeTruthy();
    expect(within(nav).queryAllByRole('link')).toHaveLength(0);
  });

  it('W-2103 links Team input to the item and marks Outcome current; the outcome tab is a link only with rfp_outcome', async () => {
    await openOutcome();
    const nav = screen.getByRole('navigation', { name: 'RFP' });
    expect(within(nav).getByRole('link', { name: /Team input/ }).getAttribute('href')).toBe('/work/W-2103');
    expect(within(nav).getByText('Outcome').closest('[aria-current="page"]')).toBeTruthy();
    expect(within(nav).getAllByRole('link')).toHaveLength(1);
    cleanup();
    const other = item('W-2103');
    other.rfp!.tabs = other.rfp!.tabs!.map((t) => ({ ...t, current: t.key === 'team_input' }));
    answers.item = () => json(200, other);
    await openOutcome();
    expect(within(screen.getByRole('navigation', { name: 'RFP' })).getByRole('link', { name: 'Outcome' }).getAttribute('href')).toBe('/work/W-2103/outcome');
    cleanup();
    const without = item('W-2109');
    without.rfp!.tabs = without.rfp!.tabs!.map((t) => ({ ...t, current: t.key === 'team_input' }));
    answers.item = () => json(200, without);
    await openOutcome('W-2109');
    expect(within(screen.getByRole('navigation', { name: 'RFP' })).queryByRole('link', { name: 'Outcome' })).toBeNull();
  });

  it('W-2110 (only reference and status) shows those and nothing else; the h1 is the page title', async () => {
    await openOutcome('W-2110');
    expect(document.querySelector('.rfp-eyebrow')!.textContent).toBe('Pre-sale / RFP · TL-RFP-2026-019');
    expect(text()).toContain('SUBMITTED 30 NOV');
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
    expect(text()).not.toContain('PM ');
    expect(document.querySelectorAll('.psl-badge')).toHaveLength(0);
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Record the outcome']);
    expect(text()).not.toContain('decided about our response');
  });

  it('tones the status tag by kind only', async () => {
    const kinds = { deadline: 'psl-tag--waiting', pending: 'psl-tag--waiting', submitted: 'psl-tag--neutral', won: 'psl-tag--done', lost: 'psl-tag--person', unknown: 'psl-tag--neutral' } as const;
    for (const [kind, tone] of Object.entries(kinds)) {
      const body = item('W-2103');
      body.rfp!.status = { kind: kind as keyof typeof kinds, label: `STATUS ${kind}`, days_left: 1 };
      answers.item = () => json(200, body);
      await openOutcome();
      expect(screen.getByText(`STATUS ${kind}`).className).toContain(tone);
      cleanup();
    }
  });

  it('at 390 draws no frame: "← RFP" in the bar with the OUTCOME note and the page title as h1', async () => {
    phone();
    await openOutcome();
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
    expect(text()).not.toContain('TL-RFP-2026-014');
    const back = screen.getByRole('link', { name: 'Back to RFP' });
    expect(back.getAttribute('href')).toBe('/work/W-2103');
    expect(back.closest('.psl-phonebar')!.textContent).toContain('OUTCOME');
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Record the outcome']);
    expect(screen.getByRole('main').querySelector('a[href="/work/W-2103"]')).toBeNull();
  });
});

describe('team input (FE-M2B-RFP)', () => {
  it('shows only the returned teams with given markers, the blocking sentence and the estimate for a team that needs one', async () => {
    await openTeam();
    const group = screen.getByRole('radiogroup', { name: 'Team' });
    const teams = within(group).getAllByRole('radio');
    expect(teams.map((r) => r.textContent)).toEqual(['Engineering', 'QA', 'Security', 'Product']);
    expect(teams.map((r) => r.getAttribute('aria-label'))).toEqual(['Engineering, given', 'QA, given', 'Security, missing', 'Product, missing']);
    expect(teams.some((r) => r.getAttribute('aria-checked') === 'true')).toBe(false);
    expect(text()).toContain("Security and Product haven't given input yet. Review can't start until they do.");
    expect(screen.getByRole('heading', { level: 2, name: 'Record team input' })).toBeTruthy();
    expect(screen.queryByLabelText('Estimate (person-days)')).toBeNull();
    choose('Security, missing');
    expect(screen.getByLabelText('Estimate (person-days)')).toBeTruthy();
    expect(text()).toContain('Needed for the costing sheet. Shown for Engineering and Security.');
    choose('QA, given');
    expect(screen.queryByLabelText('Estimate (person-days)')).toBeNull();
    expect(screen.queryByLabelText('Who gave it')).toBeNull();
    expect(button('Record input').disabled).toBe(true);
    expect(screen.getByRole('complementary', { name: 'About team input' }).textContent).toContain("don't log in");
  });

  it('a team the API does not return is never shown; several responders get a select', async () => {
    const body = item('W-2101');
    const response = body.tasks[0].response!;
    response.teams = response.teams!.filter((t) => t.key !== 'product');
    response.responders = [...response.responders, { id: 'P-OB', name: 'Ola Bakare', role: 'QA lead' }];
    answers.item = () => json(200, body);
    await openTeam();
    expect(screen.queryByRole('radio', { name: /^Product/ })).toBeNull();
    const who = screen.getByLabelText('Who gave it') as HTMLSelectElement;
    expect([...who.options].map((o) => o.text)).toEqual(['Choose…', 'Security lead · Kemi Adeyemi, PSL', 'QA lead · Ola Bakare']);
  });

  it('Record input stays off until every entry is there: a neutral hint, then the alert', async () => {
    await openTeam();
    expect(screen.getByText('Add the team, what they gave and when it was received to record this.').className).toContain('resp-alert--hint');
    choose('Security, missing');
    expect(screen.getByRole('alert').textContent).toBe('Add the estimate, what they gave and when it was received to record this.');
    type('Estimate (person-days)', '18');
    type('What they gave', 'Security estimate and data-protection notes');
    type('Received', '2026-11-12T15:10');
    expect(screen.getByRole('alert').textContent).toBe('Add the proof and confirm it’s genuine to record this.');
    await addFile(file('security-estimate-tamarind.xlsx'));
    expect(button('Record input').disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: 'I confirm this input came from the team named above.' }));
    expect(button('Record input').disabled).toBe(false);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  async function fillSecurity() {
    await openTeam();
    choose('Security, missing');
    type('Estimate (person-days)', '18');
    type('What they gave', '  Security estimate and data-protection notes ');
    type('Received', '2026-11-12T15:10');
    await addFile(file('security-estimate-tamarind.xlsx'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'I confirm this input came from the team named above.' }));
  }

  it('claims once with the task revision, then sends the team, the estimate as a number and what they gave', async () => {
    await fillSecurity();
    fireEvent.click(button('Record input'));
    await screen.findByText('Response recorded.');
    expect(posts('/claim')).toEqual([{ method: 'POST', path: '/api/v1/tasks/T-2101/claim', csrf: 'mock-csrf-pm', body: { expected_revision: 4 } }]);
    expect(posts('/response')).toEqual([
      {
        method: 'POST',
        path: '/api/v1/tasks/T-2101/response',
        csrf: 'mock-csrf-pm',
        body: {
          expected_revision: 5,
          who: 'P-KA',
          action: 'estimate',
          responded_at: '2026-11-12T15:10:00+01:00',
          evidence_id: 'EV-C-2101-1',
          attested: true,
          case_revision: 4,
          team: 'security',
          estimate_person_days: 18,
          what: 'Security estimate and data-protection notes',
        },
      },
    ]);
    expect(calls.findIndex((c) => c.path.endsWith('/claim'))).toBeLessThan(calls.findIndex((c) => c.path.endsWith('/response')));
  });

  it('a team without an estimate sends action input and no estimate, even after one was typed for another team', async () => {
    await openTeam();
    choose('Security, missing');
    type('Estimate (person-days)', '18');
    choose('Product, missing');
    type('What they gave', 'Scope notes');
    type('Received', '2026-11-12T15:10');
    await addFile();
    fireEvent.click(screen.getByRole('checkbox', { name: 'I confirm this input came from the team named above.' }));
    fireEvent.click(button('Record input'));
    await screen.findByText('Response recorded.');
    const body = posts('/response')[0].body!;
    expect(body).toMatchObject({ team: 'product', action: 'input', what: 'Scope notes' });
    expect(body).not.toHaveProperty('estimate_person_days');
  });

  it('a double press sends one claim and one response', async () => {
    await fillSecurity();
    fireEvent.click(button('Record input'));
    fireEvent.click(button(/Record input|Recording…/));
    await screen.findByText('Response recorded.');
    expect(posts('/claim')).toHaveLength(1);
    expect(posts('/response')).toHaveLength(1);
  });

  it('409 reloads and keeps every entry; 422 shows the server message and keeps them', async () => {
    answers.respond = (n) => (n === 0 ? json(409, STALE) : json(422, { code: 'invalid', message: 'Check these fields: what.' }));
    await fillSecurity();
    const before = gets();
    fireEvent.click(button('Record input'));
    await screen.findByText(/This changed while you were recording/);
    expect(gets()).toBe(before + 1);
    expect((screen.getByLabelText('Estimate (person-days)') as HTMLInputElement).value).toBe('18');
    expect((screen.getByLabelText('What they gave') as HTMLInputElement).value).toBe('  Security estimate and data-protection notes ');
    expect(screen.getByRole('radio', { name: 'Security, missing' }).getAttribute('aria-checked')).toBe('true');
    fireEvent.click(button('Record input'));
    await screen.findByText('Check these fields: what.');
    expect((screen.getByLabelText('What they gave') as HTMLInputElement).value).toContain('Security estimate');
    expect(posts('/response')).toHaveLength(2);
  });

  it('403 reloads and shows the not-open state when the task is no longer yours; 401 shows the signed-out callout', async () => {
    const after = item('W-2101');
    after.tasks[0].you_can_act = false;
    answers.respond = () => json(403, FORBIDDEN);
    answers.item = (n, c) => json(200, n === 0 ? item(c.path.split('/')[4]) : after);
    await fillSecurity();
    fireEvent.click(button('Record input'));
    await screen.findByText('This response isn’t open here');
    expect(screen.queryByRole('button', { name: 'Record input' })).toBeNull();
    cleanup();
    answers.item = (_, c) => json(200, item(c.path.split('/')[4]));
    answers.respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await fillSecurity();
    fireEvent.click(button('Record input'));
    await screen.findByText(/sign in/i);
  });

  it('a network error reloads once and never resends; when that reload fails Record stays off and Try again only reads', async () => {
    answers.respond = () => Promise.reject(new TypeError('Failed to fetch'));
    await fillSecurity();
    answers.item = () => Promise.reject(new TypeError('Failed to fetch'));
    const before = gets();
    fireEvent.click(button('Record input'));
    await screen.findByText(/couldn’t reload to check/);
    expect(gets()).toBe(before + 1);
    expect(button('Record input').disabled).toBe(true);
    answers.item = (_, c) => json(200, item(c.path.split('/')[4]));
    fireEvent.click(button('Try again'));
    await waitFor(() => expect(gets()).toBe(before + 2));
    expect(posts('/response')).toHaveLength(1);
  });

  it('W-2102 (not yours), a missing block or no input action shows the not-open state and writes nothing', async () => {
    await openTeam('W-2102', 'T-2102');
    expect(text()).toContain('This response isn’t open here');
    cleanup();
    const noAction = item('W-2101');
    noAction.tasks[0].response!.actions = [{ value: 'approved', label: 'Approved' }];
    answers.item = () => json(200, noAction);
    await openTeam();
    expect(text()).toContain('This response isn’t open here');
    cleanup();
    const noTeams = item('W-2101');
    noTeams.tasks[0].response!.teams = [];
    answers.item = () => json(200, noTeams);
    await openTeam();
    expect(text()).toContain('This response isn’t open here');
    cleanup();
    const noBlock = item('W-2101');
    delete noBlock.tasks[0].response;
    answers.item = () => json(200, noBlock);
    await openTeam();
    expect(text()).toContain('This response isn’t open here');
    expect(writes()).toHaveLength(0);
  });

  it('at 390: "← RFP" with no note, h1 "Record team input", no frame, the full team names', async () => {
    phone();
    await openTeam();
    const back = screen.getByRole('link', { name: 'Back to RFP' });
    expect(back.getAttribute('href')).toBe('/work/W-2101');
    expect(back.closest('.psl-phonebar')!.textContent).not.toMatch(/OUTCOME|WON|LOST/);
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Record team input']);
    expect(screen.queryByRole('navigation', { name: 'RFP' })).toBeNull();
    expect(screen.getByRole('radio', { name: 'Engineering, given' })).toBeTruthy();
    expect(document.querySelector('.resp-phonebar')!.textContent).toBe('Record input');
  });
});

describe('entry links on the work item', () => {
  it('"Record team input" only with the grant; "Record the outcome" only with rfp_outcome', () => {
    const view = render(<WorkItemOverview id="W-2101" item={item('W-2101') as WorkItem} />);
    expect(screen.getByRole('link', { name: 'Record team input' }).getAttribute('href')).toBe('/work/W-2101/respond?task=T-2101');
    expect(screen.queryByRole('link', { name: 'Record the outcome' })).toBeNull();
    view.unmount();
    const notYours = render(<WorkItemOverview id="W-2102" item={item('W-2102') as WorkItem} />);
    expect(screen.queryByRole('link', { name: 'Record team input' })).toBeNull();
    notYours.unmount();
    const outcome = render(<WorkItemOverview id="W-2103" item={item('W-2103') as WorkItem} />);
    expect(screen.getByRole('link', { name: 'Record the outcome' }).getAttribute('href')).toBe('/work/W-2103/outcome');
    outcome.unmount();
    render(<WorkItemOverview id="W-2109" item={item('W-2109') as WorkItem} />);
    expect(screen.queryByRole('link', { name: 'Record the outcome' })).toBeNull();
  });
});

const WHEN = '2026-12-04T11:00';
async function fillOutcome(result: string, extra?: () => void | Promise<void>) {
  choose(result);
  type(result === 'Unknown' ? 'Last contact with the client' : 'When you learned it', WHEN);
  await extra?.();
  await addFile(file('tamarind-award-letter.pdf', 310 * 1024));
  fireEvent.change(screen.getByLabelText('You are recording as'), { target: { value: 'relationship_owner' } });
}
const BASE = { expected_revision: 5, case_revision: 4, submission_id: 'SUB-0031', learned_at: '2026-12-04T11:00:00+01:00', record_as: 'relationship_owner', evidence_id: 'EV-C-2103-1' };

describe('outcome form: options and gating', () => {
  it('W-2103 offers the four results with none chosen, both roles, and Record off until result, time, proof and role', async () => {
    await openOutcome();
    expect(screen.getByRole('heading', { level: 2, name: 'Record the outcome' })).toBeTruthy();
    expect(text()).toContain('What Tamarind Loans decided about our response.');
    expect(text()).toContain('Submission pack v1 · emailed 26 Nov 15:42 · delivery confirmed');
    const radios = within(screen.getByRole('radiogroup', { name: 'Result' })).getAllByRole('radio');
    expect(radios.map((r) => r.textContent)).toEqual(['Won', 'Lost', 'Pending', 'Unknown']);
    expect(radios.some((r) => r.getAttribute('aria-checked') === 'true')).toBe(false);
    expect([...(screen.getByLabelText('You are recording as') as HTMLSelectElement).options].map((o) => o.text)).toEqual(['Choose…', 'Relationship owner', 'PM']);
    expect(button('Record the outcome').disabled).toBe(true);
    expect(screen.queryByLabelText('When you learned it')).toBeNull();
    choose('Won');
    expect(button('Record won').disabled).toBe(true);
    type('When you learned it', WHEN);
    await addFile();
    expect(button('Record won').disabled).toBe(true);
    expect(screen.getByRole('alert').textContent).toBe('Choose who you are recording as to record this.');
    fireEvent.change(screen.getByLabelText('You are recording as'), { target: { value: 'pm' } });
    expect(button('Record won').disabled).toBe(false);
  });

  it('shows each result’s fields and nothing else', async () => {
    await openOutcome();
    const shown = () =>
      ['Awarded amount', 'Main reason they gave', 'Lessons (what we’d do differently)', 'Expected decision date', 'Remind me on', 'Last contact with the client', 'When you learned it'].filter(
        (label) => screen.queryByLabelText(label) !== null || screen.queryByRole('radiogroup', { name: label }) !== null,
      );
    choose('Won');
    expect(shown()).toEqual(['Awarded amount', 'When you learned it']);
    choose('Lost');
    expect(shown()).toEqual(['Main reason they gave', 'Lessons (what we’d do differently)', 'When you learned it']);
    expect(within(screen.getByRole('radiogroup', { name: 'Main reason they gave' })).getAllByRole('radio').map((r) => r.textContent)).toEqual([
      'Price',
      'Timeline',
      'Scope fit',
      'Other',
    ]);
    choose('Pending');
    expect(shown()).toEqual(['Expected decision date', 'Remind me on', 'When you learned it']);
    choose('Unknown');
    expect(shown()).toEqual(['Remind me on', 'Last contact with the client']);
    expect(screen.getByRole('group', { name: 'Proof' })).toBeTruthy();
    expect(text()).not.toContain('No proof needed');
  });

  it('W-2104 offers Won and Lost only and its single role is chosen without a select', async () => {
    await openOutcome('W-2104');
    expect(within(screen.getByRole('radiogroup', { name: 'Result' })).getAllByRole('radio').map((r) => r.textContent)).toEqual(['Won', 'Lost']);
    expect(screen.queryByRole('combobox', { name: 'You are recording as' })).toBeNull();
    expect(text()).toContain('Relationship owner');
    choose('Lost');
    type('When you learned it', WHEN);
    await addFile();
    fireEvent.click(button('Record lost'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body).toMatchObject({ record_as: 'relationship_owner', result: 'lost' });
  });

  it('no form on W-2109 (no block), without record_as or with empty results', async () => {
    await openOutcome('W-2109');
    expect(text()).toContain('This outcome isn’t open here');
    expect(screen.queryByRole('radiogroup')).toBeNull();
    for (const change of [(b: ResponseWorkItem) => (b.rfp_outcome!.record_as = []), (b: ResponseWorkItem) => (b.rfp_outcome!.results = [])]) {
      cleanup();
      const body = item('W-2103');
      change(body);
      answers.item = () => json(200, body);
      await openOutcome();
      expect(text()).toContain('This outcome isn’t open here');
      expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe('/work/W-2103');
    }
    expect(writes()).toHaveLength(0);
  });
});

describe('outcome request', () => {
  it('won sends the base fields and the awarded amount; a ₦ amount with separators becomes a decimal string', async () => {
    await openOutcome();
    await fillOutcome('Won', () => type('Awarded amount', '₦40,951,000.00'));
    fireEvent.click(button('Record won'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0]).toEqual({
      method: 'POST',
      path: '/api/v1/work/W-2103/rfp-outcome',
      csrf: 'mock-csrf-pm',
      body: { ...BASE, result: 'won', awarded_amount: { currency: 'NGN', amount: '40951000.00', unknown: false } },
    });
  });

  it('lost sends the reason and the lessons as text; pending the expected date and reminder; unknown the reminder', async () => {
    const cases: [string, string, () => void, Record<string, unknown>][] = [
      ['Lost', 'Record lost', () => {
        choose('Price');
        type('Lessons (what we’d do differently)', ' Our total was 18% above the winning bid. ');
      }, { result: 'lost', reason: 'price', lessons: 'Our total was 18% above the winning bid.' }],
      ['Pending', 'Record pending', () => {
        type('Expected decision date', '2026-12-12');
        type('Remind me on', '2026-12-12T09:00');
      }, { result: 'pending', expected_decision_on: '2026-12-12', remind_at: '2026-12-12T09:00:00+01:00' }],
      ['Unknown', 'Save as unknown', () => type('Remind me on', '2026-12-10T09:00'), { result: 'unknown', remind_at: '2026-12-10T09:00:00+01:00' }],
    ];
    for (const [result, label, extra, expected] of cases) {
      calls = [];
      await openOutcome();
      await fillOutcome(result, extra);
      fireEvent.click(button(label));
      await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
      expect(posts('/rfp-outcome')[0].body).toEqual({ ...BASE, ...expected, evidence_id: expect.stringMatching(/^EV-C-2103-\d+$/) });
      cleanup();
    }
  });

  it('fields typed under another result are not sent', async () => {
    await openOutcome();
    choose('Lost');
    choose('Price');
    type('Lessons (what we’d do differently)', 'Too expensive');
    choose('Pending');
    type('Expected decision date', '2026-12-12');
    choose('Won');
    type('Awarded amount', '1000');
    await fillOutcome('Unknown');
    fireEvent.click(button('Save as unknown'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body).toEqual({ ...BASE, result: 'unknown' });
  });

  it('a note over 2000 characters is refused before any request; a shorter one is trimmed and sent', async () => {
    await openOutcome();
    await fillOutcome('Unknown');
    type(/^Note/, 'x'.repeat(2001));
    expect(button('Save as unknown').disabled).toBe(true);
    fireEvent.click(button('Save as unknown'));
    expect(posts('/rfp-outcome')).toHaveLength(0);
    type(/^Note/, ' Chased by phone ');
    fireEvent.click(button('Save as unknown'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body).toMatchObject({ note: 'Chased by phone' });
  });
});

describe('unknown stays unknown (INV-UNKNOWN)', () => {
  async function wonWith(setup: () => void) {
    await openOutcome();
    await fillOutcome('Won', setup);
  }
  it('blank sends no awarded_amount; "Amount not known" sends unknown with no amount', async () => {
    await wonWith(() => {});
    fireEvent.click(button('Record won'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body).not.toHaveProperty('awarded_amount');
    cleanup();
    calls = [];
    await wonWith(() => {
      type('Awarded amount', '500');
      fireEvent.click(screen.getByRole('checkbox', { name: 'Amount not known' }));
    });
    expect((screen.getByLabelText('Awarded amount') as HTMLInputElement).value).toBe('');
    fireEvent.click(button('Record won'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body!.awarded_amount).toEqual({ currency: 'NGN', unknown: true });
  });

  it('"40,951,000" sends 40951000.00; "abc" and "1.234" send nothing and show a message', async () => {
    await wonWith(() => type('Awarded amount', '40,951,000'));
    fireEvent.click(button('Record won'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    expect(posts('/rfp-outcome')[0].body!.awarded_amount).toEqual({ currency: 'NGN', amount: '40951000.00', unknown: false });
    for (const bad of ['abc', '1.234']) {
      cleanup();
      calls = [];
      await wonWith(() => type('Awarded amount', bad));
      expect(screen.getByRole('alert').textContent).toBe('Enter the amount in naira with at most two decimals, for example 40,951,000.');
      expect(button('Record won').disabled).toBe(true);
      fireEvent.click(button('Record won'));
      expect(posts('/rfp-outcome')).toHaveLength(0);
    }
    expect(text()).not.toMatch(/₦0|0\.00/);
  });
});

describe('outcome guards', () => {
  it('409 keeps every entry and the uploaded proof, reloads, and the next press carries the reloaded revisions', async () => {
    const reloaded = item('W-2103');
    reloaded.revision = 9;
    reloaded.case_revision = 12;
    answers.outcome = (n, c) => (n === 0 ? json(409, STALE) : json(200, { work_id: 'W-2103', result: c.body!.result, state: 'waiting', revision: 10 }));
    answers.item = (n) => json(200, n === 0 ? item('W-2103') : reloaded);
    await openOutcome();
    await fillOutcome('Won', () => type('Awarded amount', '1000'));
    const before = gets();
    fireEvent.click(button('Record won'));
    await screen.findByText(/This changed while you were recording/);
    expect(gets()).toBe(before + 1);
    expect((screen.getByLabelText('Awarded amount') as HTMLInputElement).value).toBe('1000');
    expect(screen.getByRole('radio', { name: 'Won' }).getAttribute('aria-checked')).toBe('true');
    expect(text()).toContain('tamarind-award-letter.pdf');
    fireEvent.click(button('Record won'));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(2));
    expect(posts('/rfp-outcome')[1].body).toMatchObject({ expected_revision: 9, case_revision: 12, evidence_id: 'EV-C-2103-1' });
  });

  it('422 shows the server message and keeps the entries; nothing reloads', async () => {
    answers.outcome = () => json(422, INVALID);
    await openOutcome();
    await fillOutcome('Unknown');
    const before = gets();
    fireEvent.click(button('Save as unknown'));
    await screen.findByText('Check these fields: learned_at.');
    expect(gets()).toBe(before);
    expect((screen.getByLabelText('Last contact with the client') as HTMLInputElement).value).toBe(WHEN);
  });

  it('403 reloads and removes the form with the server message', async () => {
    answers.outcome = () => json(403, FORBIDDEN);
    await openOutcome();
    await fillOutcome('Unknown');
    fireEvent.click(button('Save as unknown'));
    await screen.findByText('Your role does not allow this.');
    expect(text()).toContain('This outcome isn’t open here');
    expect(screen.queryByRole('radiogroup', { name: 'Result' })).toBeNull();
  });

  it('a network or 5xx error reloads once and never resends; a failed reload keeps Record off and Try again only reads', async () => {
    for (const fail of [() => Promise.reject(new TypeError('Failed to fetch')), () => json(502, { code: 'bad_gateway', message: 'Down.' })]) {
      calls = [];
      answers.outcome = fail;
      answers.item = (_, c) => json(200, item(c.path.split('/')[4]));
      await openOutcome();
      await fillOutcome('Unknown');
      const before = gets();
      fireEvent.click(button('Save as unknown'));
      await screen.findByText(/We couldn’t confirm the outcome was recorded/);
      expect(gets()).toBe(before + 1);
      expect(posts('/rfp-outcome')).toHaveLength(1);
      cleanup();
    }
    calls = [];
    answers.outcome = () => Promise.reject(new TypeError('Failed to fetch'));
    await openOutcome();
    await fillOutcome('Unknown');
    answers.item = () => Promise.reject(new TypeError('Failed to fetch'));
    fireEvent.click(button('Save as unknown'));
    await screen.findByText(/couldn’t reload to check/);
    expect(button('Save as unknown').disabled).toBe(true);
    const before = gets();
    answers.item = (_, c) => json(200, item(c.path.split('/')[4]));
    fireEvent.click(button('Try again'));
    await waitFor(() => expect(gets()).toBe(before + 1));
    expect(posts('/rfp-outcome')).toHaveLength(1);
  });

  it('a double press makes one request', async () => {
    await openOutcome();
    await fillOutcome('Unknown');
    fireEvent.click(button('Save as unknown'));
    fireEvent.click(button(/Save as unknown|Recording…/));
    await waitFor(() => expect(posts('/rfp-outcome')).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText('Recording…')).toBeNull());
    expect(posts('/rfp-outcome')).toHaveLength(1);
  });

  it('200 reloads once and shows the recorded state; if that reload fails, "Outcome recorded." with the returned result only', async () => {
    answers.item = (n) => json(200, n === 0 ? item('W-2103') : { ...item('W-2107'), id: 'W-2103' });
    await openOutcome();
    await fillOutcome('Pending');
    const before = gets();
    fireEvent.click(button('Record pending'));
    await screen.findByRole('heading', { level: 2, name: 'Decision pending' });
    expect(gets()).toBe(before + 1);
    cleanup();
    let reads = 0;
    answers.item = () => (reads++ === 0 ? json(200, item('W-2103')) : Promise.reject(new TypeError('Failed to fetch')));
    await openOutcome();
    await fillOutcome('Won');
    fireEvent.click(button('Record won'));
    await screen.findByText('Outcome recorded.');
    expect(screen.getByRole('status').textContent).toBe('Outcome recorded. Won');
    expect(text()).not.toContain('What’s recorded');
  });

  it('401 shows the signed-out callout; 403 and 404 on the read show no reference, title or client', async () => {
    answers.item = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await openOutcome();
    expect(screen.getByRole('link', { name: /sign in/i }).getAttribute('href')).toContain(encodeURIComponent('/work/W-2103/outcome'));
    for (const status of [403, 404]) {
      cleanup();
      answers.item = () => json(status, status === 403 ? FORBIDDEN : { code: 'not_found', message: 'We could not find that record.' });
      await openOutcome();
      expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['You can’t open this work item']);
      for (const secret of ['W-2103', 'TL-RFP-2026-014', 'Tamarind', 'loan origination']) expect(text()).not.toContain(secret);
    }
  });
});
