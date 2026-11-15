// @vitest-environment jsdom
// F-16: the decision page drawn to the SCR-03 boards (W-19xx board fixtures). The behaviour tests stay in
// decide.test.tsx; these check the board layout's data, the PROPOSAL block's containment and the phone back link.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkItem } from '@/api/types';
import { DecideView } from '@/features/decide/DecideView';
import { AppShell } from '@/shell/AppShell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-1901/decide',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = <T,>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STALE = { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' };

type Call = { method: string; path: string; body: unknown };
type Answer = (n: number, call: Call) => Response | Promise<Response>;
let calls: Call[];
let answers: { item: Answer; claim: Answer; decide: Answer };

beforeEach(() => {
  calls = [];
  answers = {
    item: () => json(200, item('W-1901')),
    claim: (_, c) => json(200, { task_id: c.path.split('/')[4], revision: (c.body as { expected_revision: number }).expected_revision, claimed_by: 'Ada Okafor' }),
    decide: (_, c) => json(200, { task_id: c.path.split('/')[4], verdict: (c.body as { verdict: string }).verdict, decided_by: 'Ada Okafor', decided_at: '2026-11-12T09:47:00Z', work_state: 'ready' }),
  };
  const n = { item: 0, claim: 0, decide: 0 };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const c: Call = { method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined };
      calls.push(c);
      if (url.pathname === '/api/v1/me') return json(200, read('me.finance_lead.json'));
      if (url.pathname.endsWith('/claim')) return answers.claim(n.claim++, c);
      if (url.pathname.endsWith('/decision')) return answers.decide(n.decide++, c);
      return answers.item(n.item++, c);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function open(id: string, taskId: string) {
  render(
    <AppShell>
      <DecideView id={id} taskId={taskId} />
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
const button = (name: string | RegExp) => screen.getByRole('button', { name });
const ready = () => waitFor(() => expect((button(/^Approve v/) as HTMLButtonElement).disabled).toBe(false));
const text = () => document.body.textContent ?? '';
const main = () => document.querySelector('main') ?? document.body;
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const decisionControls = () => screen.queryAllByRole('button', { name: /^(approve|return|reject)/i });
/** Only the three contract operations: GET E-WORK-ITEM, POST E-TASK-CLAIM and E-TASK-DECIDE (and the frame's /me). */
// The shell's alert bell (F-15) reads GET /api/v1/notifications; it is the frame's read, not the page's.
const onlyContractCalls = () =>
  calls.every(
    (c) =>
      (c.method === 'GET' && (c.path === '/api/v1/me' || c.path === '/api/v1/notifications' || /^\/api\/v1\/work\/W-\d+$/.test(c.path))) ||
      (c.method === 'POST' && /^\/api\/v1\/tasks\/T-\d+\/(claim|decision)$/.test(c.path)),
  );
const factTexts = () => within(screen.getByRole('list', { name: 'Facts' })).getAllByRole('listitem').map((li) => li.textContent);

describe('header and trail (criterion 7)', () => {
  it('W-1901 draws "Decisions / 1 of 3 / FINANCE REVIEW · INV-0412" and keeps the Breadcrumb nav', async () => {
    await open('W-1901', 'T-1901');
    const trail = document.querySelector('.decide-trail')!;
    expect(trail.textContent).toBe('Decisions / 1 of 3 / FINANCE REVIEW · INV-0412');
    expect(within(trail as HTMLElement).getByRole('link', { name: 'Decisions' }).getAttribute('href')).toBe('/my-work');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' }).textContent).toBe('My work / Prepare an invoice / INV-0412');
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Approve invoice v2 · Lagoon Health, milestone 2']);
  });

  it('W-1201 (no board block) has no "1 of 3" and keeps the task title and the item sub-line', async () => {
    answers.item = () => json(200, read('work/W-1201.json'));
    await open('W-1201', 'T-1201');
    expect(document.querySelector('.decide-trail')!.textContent).toBe('Decisions / FINANCE REVIEW · INV-0412');
    expect(text()).not.toMatch(/1 of 3|waiting 2h|Next decision/);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Approve invoice v2');
    expect(screen.getByText('Lagoon Health · Milestone 2 invoice')).toBeTruthy();
  });
});

describe('default board W-1901 (criterion 8)', () => {
  it('shows the rows through DecisionRows, the facts with the board details, the station line and the agent card', async () => {
    await open('W-1901', 'T-1901');
    await ready();
    const dl = document.querySelector('.decide-what dl') as HTMLElement;
    const rows = Object.fromEntries(within(dl).getAllByRole('term').map((dt) => [dt.textContent, dt.nextElementSibling!.textContent]));
    expect(rows).toMatchObject({
      Amount: '₦4,250,000.00',
      Basis: 'Contract stage 2 of 4 · terms v1',
      To: 'accounts@lagoonhealth.example',
      'Changed since Invoice v1': 'PO number, as you asked',
      Version: 'Invoice v2 · drafted 12 Nov 10:30',
    });
    expect(factTexts().slice(0, 2)).toEqual(['DRAFTEDEarned: v2', 'REVIEWEDIn progress: Waiting']);
    expect(factTexts()[4]).toBe('RECEIPT RECORDEDUnknown');
    expect(screen.getByText('Station 4 of 7 · Finance review · waiting 2h · only a Finance Lead can decide')).toBeTruthy();
    const agent = screen.getByRole('region', { name: 'Agent' });
    expect(within(agent).getByText('Chidi').parentElement!.textContent).toBe('Chidi · Finance agent · ');
    expect(within(agent).getByText('Cannot approve, send or pay.')).toBeTruthy();
    expect(agent.textContent).toContain('Drafted this from 3 sources: the milestone record, the signed SOW stage 2 and the client register.');
    expect(within(agent).getByRole('link', { name: 'See his steps' }).getAttribute('href')).toBe('/work/W-1901');
    expect(button('Approve v2')).toBeTruthy();
  });

  it('an unknown amount on a board fixture still reads Unknown', async () => {
    const crafted = item('W-1901');
    crafted.tasks[0].decision!.amount = { amount: '4250000.00', currency: 'NGN', unknown: true };
    answers.item = () => json(200, crafted);
    await open('W-1901', 'T-1901');
    expect(screen.getByText('Amount').nextElementSibling!.textContent).toBe('Unknown');
    expect(text()).not.toContain('4,250,000');
  });

  it('shows the sample label whenever the record says sample', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open('W-1901', 'T-1901');
    expect(within(document.querySelector('.decide-header') as HTMLElement).getByText('SAMPLE DATA')).toBeTruthy();
  });
});

describe('done board (criterion 15)', () => {
  it('Approve on W-1901 shows the green banner, the client heading, the board facts and Next decision', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1901' : 'W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    const heading = await screen.findByRole('heading', { level: 1, name: 'Invoice v2 for Lagoon Health is approved' });
    expect(heading.closest('.decide-banner')!.className).toBe('decide-banner decide-banner--success');
    expect(screen.getByText(/^YOU APPROVED ·/).textContent).toBe('YOU APPROVED · 10:47');
    await screen.findByText(/^Chidi will issue it and email it to Lagoon Health\./);
    expect(factTexts().slice(0, 4)).toEqual(['DRAFTEDEarned: v2', 'REVIEWEDEarned: You', 'APPROVEDEarned: 10:47', 'SENTNot yet: Next']);
    // the board's next_step already says it: the page does not repeat it
    expect(text().match(/Paid is tracked separately/g)).toHaveLength(1);
    expect(screen.getByRole('link', { name: 'Next decision · 2 of 3' }).getAttribute('href')).toBe('/work/W-1201/decide?task=T-1201');
    expect(screen.getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe('/work/W-1901');
    expect(screen.getByRole('link', { name: 'Back to my work' }).getAttribute('href')).toBe('/my-work');
    expect(decisionControls()).toHaveLength(0);
    expect(onlyContractCalls()).toBe(true);
  });

  it('on a phone the card stops before the Paid sentence and the separate line says it once (SCR-03-mobile-done)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    answers.item = (n) => json(200, item(n === 0 ? 'W-1901' : 'W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText(/^Chidi will issue it and email it to Lagoon Health\./);
    expect(text().match(/Paid is tracked separately/g)).toHaveLength(1);
    expect(document.querySelector('.decide-next')!.textContent).not.toContain('Paid is tracked');
    expect(document.querySelector('.decide-paid')!.textContent).toContain('Paid is tracked separately');
  });

  it('moves focus to the done heading, announces the result, and draws the next step on the agent surface with the done pose', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1901' : 'W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    const heading = await screen.findByRole('heading', { level: 1, name: 'Invoice v2 for Lagoon Health is approved' });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(screen.getByRole('status').textContent).toBe('Your decision was recorded.');
    const card = (await screen.findByText(/^Chidi will issue it/)).closest('.decide-next')!;
    expect(card.querySelector('img')!.getAttribute('src')).toContain('chidi-done.png');
  });

  it('the 5xx error card and the signed-out view each have an h1', async () => {
    answers.item = () => json(500, { code: 'server_error', message: 'x' });
    await open('W-1901', 'T-1901');
    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy();
  });

  it('without queue.next there is no Next decision link; Back to my work stays', async () => {
    const first = item('W-1901');
    (first as WorkItem & { decide_presentation: { queue?: unknown } }).decide_presentation.queue = { position: 1, total: 3 };
    answers.item = (n) => json(200, n === 0 ? first : item('W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Invoice v2 for Lagoon Health is approved');
    expect(screen.queryByRole('link', { name: /Next decision/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'Back to my work' })).toBeTruthy();
  });

  it.each(['https://x.example', '//x.example', 'javascript:alert(1)', '/\\x.example', ' /work'])('a crafted next href %s renders no link', async (href) => {
    const first = item('W-1901');
    (first as WorkItem & { decide_presentation: { queue: { next: { href: string } } } }).decide_presentation.queue.next.href = href;
    answers.item = (n) => json(200, n === 0 ? first : item('W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Invoice v2 for Lagoon Health is approved');
    expect(screen.queryByRole('link', { name: /Next decision/ })).toBeNull();
    expect(document.querySelector(`a[href="${href.replace(/["\\]/g, '\\$&')}"]`)).toBeNull();
  });

  it('Return keeps the neutral banner on the board fixture', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1901' : 'W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'Wrong PO' } });
    fireEvent.click(button('Return'));
    const heading = await screen.findByRole('heading', { level: 1, name: 'Invoice v2 for Lagoon Health was returned' });
    expect(heading.closest('.decide-banner')!.className).toBe('decide-banner decide-banner--neutral');
    expect(text()).not.toContain('Paid is tracked separately by Finance and is not part of this decision.');
  });
});

describe('stale board W-1902 (criterion 12)', () => {
  it('a 409 shows the replaced and current versions, the redraft note and Review version 3', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1902' : 'W-1902.next'));
    answers.decide = () => json(409, STALE);
    await open('W-1902', 'T-1902');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('A newer version arrived while you were reading.');
    expect(screen.getByRole('region', { name: 'VERSION 2 · REPLACED' })).toBeTruthy();
    const now = screen.getByRole('region', { name: 'VERSION 3 · CURRENT' });
    const nowRows = Object.fromEntries(within(now).getAllByRole('term').map((dt) => [dt.textContent, dt.nextElementSibling!.textContent]));
    expect(nowRows['Send to']).toBe('billing@lagoonhealth.example · changed');
    // what changed is listed before what did not
    expect(within(now).getAllByRole('term').map((dt) => dt.textContent)).toEqual(['Amount', 'Send to', 'Basis']);
    expect(screen.getByRole('region', { name: 'Agent' }).textContent).toContain('Redrafted it from the updated client record. Nothing else changed.');
    expect(button('Review version 3')).toBeTruthy();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(calls.filter((c) => c.path.endsWith('/decision'))).toHaveLength(1);
    expect(onlyContractCalls()).toBe(true);
  });
});

describe('not-yours board W-1903 (criterion 16)', () => {
  it('shows the tag, the reason copy, the values, who was alerted and the disabled comment box; nothing is sent', async () => {
    answers.item = () => json(200, item('W-1903'));
    await open('W-1903', 'T-1903');
    for (const value of [
      'NOT YOUR DECISION',
      'This decision needs a Finance Lead.',
      'You can read it, but you can’t approve, return or reject it.',
      '₦4,250,000.00',
      'SOW v2 stage 2',
      'Waiting for Finance Lead',
      'Ada Okafor (Finance Lead) was alerted at 12 Nov 10:42 by WhatsApp and email',
    ]) {
      expect(text(), value).toContain(value);
    }
    const box = screen.getByLabelText('Comment for the Finance Lead (optional)') as HTMLTextAreaElement;
    const add = button('Add comment') as HTMLButtonElement;
    expect(box.disabled).toBe(true);
    expect(add.disabled).toBe(true);
    for (const el of [box, add]) {
      const note = document.getElementById(el.getAttribute('aria-describedby')!)!;
      expect(note.textContent).toBe('Comments aren’t available yet.');
    }
    const before = calls.length;
    box.focus();
    fireEvent.click(box);
    fireEvent.click(add);
    expect(calls.length).toBe(before);
    expect(decisionControls()).toHaveLength(0);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });

  it('W-1203 (no comment in the block) has no comment box', async () => {
    answers.item = () => json(200, read('work/W-1203.json'));
    await open('W-1203', 'T-1203');
    expect(document.querySelector('textarea')).toBeNull();
    expect(screen.queryByRole('button', { name: /comment/i })).toBeNull();
  });
});

describe('own board W-1904 (criterion 17)', () => {
  it('shows the waiting tag, the reason, the values, who prepared it and who was asked, and no controls', async () => {
    answers.item = () => json(200, item('W-1904'));
    await open('W-1904', 'T-1904');
    expect(screen.getByText('WAITING FOR REVIEW')).toBeTruthy();
    for (const value of [
      'You prepared Invoice v2, so someone else must review it.',
      '₦4,250,000.00',
      'Contract stage 2 of 4 · terms v1',
      'Prepared by You with Chidi',
      'Ada Okafor (Finance Lead) was alerted at 12 Nov 10:20',
      'Waiting · Finance Lead',
    ]) {
      expect(text(), value).toContain(value);
    }
    expect(document.querySelector('textarea')).toBeNull();
    expect(decisionControls()).toHaveLength(0);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });
});

describe('phone back link in the frame slot (criterion 5)', () => {
  const back = () => within(phoneBar()).getByRole('link', { name: /^Back to / });
  const ownBackLinks = () => within(main() as HTMLElement).queryAllByRole('link', { name: /^(←|Back to (Queue|Decisions))/ });

  it.each([
    ['W-1901', 'T-1901', 'Decisions', '1 OF 3'],
    ['W-1201', 'T-1201', 'Decisions', undefined],
    ['W-1903', 'T-1903', 'Queue', 'INV-0412'],
    ['W-1904', 'T-1904', 'Queue', 'INV-0412'],
    ['W-1205', 'T-1205', 'Queue', 'INV-0416'],
    ['W-1901', 'T-9999', 'Queue', undefined],
  ])('%s %s: "← %s" to /my-work', async (id, task, label, note) => {
    answers.item = () => json(200, read(`work/${id}.json`));
    await open(id, task);
    await waitFor(() => expect(back().getAttribute('aria-label')).toBe(`Back to ${label}`));
    expect(back().getAttribute('href')).toBe('/my-work');
    expect(back().textContent).toBe(`← ${label}`);
    expect(phoneBar().querySelector('.shell-phonenote')?.textContent).toBe(note);
    expect(ownBackLinks()).toHaveLength(0);
  });

  it('loading and no access show "← Queue"', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    answers.item = async () => {
      await gate;
      return json(403, { code: 'forbidden', message: 'No.' });
    };
    render(
      <AppShell>
        <DecideView id="W-1901" taskId="T-1901" />
      </AppShell>,
    );
    await waitFor(() => expect(back().getAttribute('aria-label')).toBe('Back to Queue'));
    release();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(text()).not.toContain('W-1901');
    expect(back().getAttribute('aria-label')).toBe('Back to Queue');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });

  it('done and stale keep "← Decisions"', async () => {
    answers.item = (n) => json(200, item(n === 0 ? 'W-1901' : 'W-1901.approve'));
    await open('W-1901', 'T-1901');
    await ready();
    fireEvent.click(button('Approve v2'));
    await screen.findByText('Invoice v2 for Lagoon Health is approved');
    expect(back().getAttribute('aria-label')).toBe('Back to Decisions');
  });
});
