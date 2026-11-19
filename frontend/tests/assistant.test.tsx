// @vitest-environment jsdom
// F-24: the Assistant page against the real contract mocks, in process (PROPOSAL D-ASSISTANT-VIEW and
// D-CONVERSATION-MODEL, contract mock only). Nothing here reaches a provider, a client or a backend.
import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { AssistantFrame } from '@/features/assistant/AssistantFrame';
import { AssistantHome } from '@/features/assistant/AssistantHome';
import { poseFor } from '@/features/assistant/SidePanel';
import { ThreadPage } from '@/features/assistant/ThreadPage';
import { AppShell } from '@/shell/AppShell';

import fixture2404 from '../mock/fixtures/assistant/CV-2404.json';
import { json, startBridge } from './assistant-bridge';
import { violations } from './components/a11y';

configure({ asyncUtilTimeout: 5000 });

const nav = vi.hoisted(() => ({ pathname: '/assistant', search: '', push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: nav.replace, prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(nav.search),
}));

let bridge: ReturnType<typeof startBridge>;

const phone = () =>
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));

/** The page as the route layout renders it: the frame, then the home or the thread, inside the app shell. */
async function open(path: string, persona = 'pm', prepare?: (made: ReturnType<typeof startBridge>) => void) {
  const [pathname, search = ''] = path.split('?');
  nav.pathname = pathname;
  nav.search = search;
  bridge = startBridge(persona);
  prepare?.(bridge);
  vi.stubGlobal('fetch', bridge.stub);
  setCsrfToken(`mock-csrf-${persona}`);
  const id = /^\/assistant\/([^/]+)/.exec(pathname)?.[1];
  const view = render(
    <AppShell>
      <AssistantFrame>{id ? <ThreadPage key={id} id={id} /> : <AssistantHome />}</AssistantFrame>
    </AppShell>,
  );
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
  return view;
}

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const box = () => screen.getByRole('textbox', { name: /^Message / });
const type = (text: string) => fireEvent.change(box(), { target: { value: text } });
const send = () => fireEvent.click(screen.getByRole('button', { name: 'Send' }));
const list = () => screen.getByRole('complementary', { name: 'Conversations' });
const thread = () => screen.findByRole('region', { name: 'Conversation' });
const assistantPosts = () => bridge.posts(/\/assistant\//);

describe('agents come from E-ME only', () => {
  it('pm talks to Tola, Chidi and Zainab; Tola is pressed', async () => {
    await open('/assistant');
    const chips = within(screen.getByRole('group', { name: 'Talk to' })).getAllByRole('button');
    expect(chips.map((c) => c.textContent)).toEqual(['Tola· PMO', 'Chidi· Finance', 'Zainab· HR']);
    expect(chips.map((c) => c.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false']);
  });

  it('finance_lead sees only Chidi, and ?agent=tola selects Chidi', async () => {
    await open('/assistant?agent=tola', 'finance_lead');
    const chips = within(screen.getByRole('group', { name: 'Talk to' })).getAllByRole('button');
    expect(chips.map((c) => c.textContent)).toEqual(['Chidi· Finance']);
    expect(chips[0].getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Hi, I’m Chidi. What do you need from Finance?');
  });

  it('?agent= picks a listed agent', async () => {
    await open('/assistant?agent=zainab');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Hi, I’m Zainab. How can I help with people and payroll?');
    expect(screen.getByRole('textbox', { name: 'Message Zainab' })).toBeTruthy();
  });

  it('admin (an empty list) sees "No agents are available to you." and no composer; nothing is written', async () => {
    await open('/assistant', 'admin');
    expect(screen.getByText('No agents are available to you.')).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.queryByRole('group', { name: 'Talk to' })).toBeNull();
    expect(assistantPosts()).toEqual([]);
  });

  it('a person whose E-ME has no assistant_agents field at all is the same', async () => {
    await open('/assistant', 'finance_lead', (made) => {
      const rest = Object.fromEntries(Object.entries(made.me).filter(([key]) => key !== 'assistant_agents'));
      made.override((request, url) => (url.pathname === '/api/v1/me' ? json(200, rest) : undefined));
    });
    expect(screen.getByText('No agents are available to you.')).toBeTruthy();
    expect(screen.queryByRole('textbox')).toBeNull();
  });
});

describe('default state (SCR-05-desktop)', () => {
  it('rows with their status lines under TODAY, the hello, the ability line, the composer, the side panel', async () => {
    const { container } = await open('/assistant');
    await screen.findByText('Planning packet · Tamarind Loans');
    expect(within(list()).getByText('TODAY')).toBeTruthy();
    const rows = within(list()).getAllByRole('link').slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      'Invoice · Harmattan Bank M2Drafted · ready to start',
      'SOW · Kora Logistics phase 2Drafted · 3 open questions',
      'Can we bill Harmattan stage 3?Answered',
      'A staff member’s salaryCan’t share',
      'Planning packet · Tamarind LoansWorking · step 3 of 5',
    ]);
    expect(rows[0].getAttribute('href')).toBe('/assistant/CV-2401');
    expect(rows.some((r) => r.getAttribute('aria-current'))).toBe(false);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Hi Tunde, I’m Tola. What should we get moving?');
    expect(screen.getByText('I draft plans, SOWs, status reports and minutes, chase sign-offs, and explain where any project stands.')).toBeTruthy();
    expect(box().getAttribute('placeholder')).toBe('Ask Tola to draft a SOW, plan or report, or ask about a project…');
    const side = screen.getByRole('complementary', { name: 'Agent and context' });
    expect(within(side).getByText('Tola is ready.')).toBeTruthy();
    expect(within(side).getByText('Pick a project with @')).toBeTruthy();
    expect(within(side).getByText('Records you can see')).toBeTruthy();
    expect(within(side).getByText('Agents draft, read and explain. They cannot approve, send, pay or change a record.')).toBeTruthy();
    expect(within(list()).getByText(/^Agents use only records you can see\./)).toBeTruthy();
    expect(container.querySelectorAll('h1')).toHaveLength(1);
    expect(await violations()).toEqual([]);
  });

  it('draws no attach button, no shortcut prompts, and a held microphone', async () => {
    await open('/assistant');
    expect(screen.queryByRole('button', { name: /attach/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /create an invoice|draft a sow|ask about/i })).toBeNull();
    expect(screen.getByRole('button', { name: 'Speak your request' }).getAttribute('aria-disabled')).toBe('true');
  });

  it('the list is empty in words when there are no conversations', async () => {
    await open('/assistant', 'ceo');
    expect(await screen.findByText('No conversations yet.')).toBeTruthy();
  });

  it('a list that fails shows Try again and the page still works', async () => {
    await open('/assistant', 'pm', (made) => {
      let failed = false;
      made.override((request, url) => {
        if (failed || request.method !== 'GET' || url.pathname !== '/api/v1/assistant/conversations') return undefined;
        failed = true;
        return json(500, { code: 'server_error', message: 'x' });
      });
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Invoice · Harmattan Bank M2')).toBeTruthy();
    expect(box()).toBeTruthy();
  });

  it('signed out: the callout with next = this page', async () => {
    await open('/assistant', 'pm', (made) =>
      made.override((request, url) => (url.pathname === '/api/v1/assistant/conversations' ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined)),
    );
    const link = await within(list()).findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain(`next=${encodeURIComponent('/assistant')}`);
  });
});

describe('starting a conversation', () => {
  it('one conversation and one message, typed fields only, with CSRF; then the thread', async () => {
    await open('/assistant');
    type('Draft the SOW for Kora');
    send();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/assistant/CV-N1'));
    const [made, message] = assistantPosts();
    expect(made.path).toBe('/api/v1/assistant/conversations');
    expect(made.body).toEqual({ agent: 'tola' });
    expect(message.path).toBe('/api/v1/assistant/conversations/CV-N1/messages');
    expect(message.body).toEqual({ text: 'Draft the SOW for Kora' });
    expect(made.headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(message.headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(assistantPosts()).toHaveLength(2);
  });

  it('a double click or a double Enter sends one of each', async () => {
    await open('/assistant');
    type('Hello');
    send();
    send();
    fireEvent.keyDown(box(), { key: 'Enter' });
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(assistantPosts().map((p) => p.path)).toEqual(['/api/v1/assistant/conversations', '/api/v1/assistant/conversations/CV-N1/messages']);
  });

  it('Shift+Enter adds a line and sends nothing; blank text cannot be sent; "+ New request" posts nothing', async () => {
    await open('/assistant');
    fireEvent.keyDown(box(), { key: 'Enter', shiftKey: true });
    type('   ');
    send();
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(screen.getByRole('button', { name: 'Send' }).getAttribute('aria-disabled')).toBe('true');
    expect(within(list()).getByRole('link', { name: '+ New request' }).getAttribute('href')).toBe('/assistant');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(assistantPosts()).toEqual([]);
  });

  it('4,001 characters shows "Keep it under 4,000 characters." and sends nothing; 4,000 is sent', async () => {
    await open('/assistant');
    type('a'.repeat(4001));
    expect(screen.getByRole('alert').textContent).toBe('Keep it under 4,000 characters.');
    send();
    fireEvent.keyDown(box(), { key: 'Enter' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(assistantPosts()).toEqual([]);
    type('a'.repeat(4000));
    expect(screen.queryByRole('alert')).toBeNull();
    send();
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect((assistantPosts()[1].body as { text: string }).text).toHaveLength(4000);
  });

  it('a 403 on E-CONVERSATION-NEW shows the returned message and keeps the text', async () => {
    await open('/assistant');
    bridge.override((request, url) => (request.method === 'POST' && url.pathname === '/api/v1/assistant/conversations' ? json(403, { code: 'forbidden', message: 'That agent is not available to you.' }) : undefined));
    type('Hello');
    send();
    expect((await screen.findByRole('alert')).textContent).toBe('That agent is not available to you.');
    expect(box()).toHaveProperty('value', 'Hello');
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it('401 on a write shows the signed-out callout', async () => {
    await open('/assistant');
    bridge.override((request) => (request.method === 'POST' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : undefined));
    type('Hello');
    send();
    expect(await screen.findByText('You’re signed out.')).toBeTruthy();
  });
});

describe('errors keep the text and never resend on their own', () => {
  it('[422]: the returned message under the composer, the text kept', async () => {
    await open('/assistant/CV-2401');
    await thread();
    type('Please check [422]');
    send();
    expect((await screen.findByRole('alert')).textContent).toBe('The mock refused this message: check the text and try again.');
    expect(box()).toHaveProperty('value', 'Please check [422]');
    expect(assistantPosts()).toHaveLength(1);
  });

  it('[409]: one re-read and "This conversation changed. Showing the latest.", text kept', async () => {
    await open('/assistant/CV-2401');
    await thread();
    const reads = () => bridge.gets(/\/assistant\/conversations\/CV-2401$/).length;
    const before = reads();
    type('Stale [409]');
    send();
    expect(await screen.findByText('This conversation changed. Showing the latest.')).toBeTruthy();
    expect(reads()).toBe(before + 1);
    expect(box()).toHaveProperty('value', 'Stale [409]');
  });

  it('[500]: no resend in 60 s, one re-read, and "Try again" because the message is not on the re-read', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2401');
    await thread();
    const before = bridge.gets(/\/assistant\/conversations\/CV-2401$/).length;
    type('Lost [500]');
    send();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t confirm that was sent.');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(assistantPosts()).toHaveLength(1);
    expect(bridge.gets(/\/assistant\/conversations\/CV-2401$/).length).toBe(before + 1);
    expect(box()).toHaveProperty('value', 'Lost [500]');
    // the person decides: Try again is a new press, and the mock answers 500 once only
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByText('Lost [500]')).toBeTruthy());
    expect(assistantPosts()).toHaveLength(2);
  });

  it('a network error is the same: one POST, one re-read, Try again', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2401');
    await thread();
    bridge.override((request) => (request.method === 'POST' ? Promise.reject(new TypeError('fetch failed')) : undefined));
    type('Offline');
    send();
    const alert = await screen.findByRole('alert');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(assistantPosts()).toHaveLength(1);
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('an uncertain send whose message is already on the re-read is shown, not resent', async () => {
    await open('/assistant/CV-2401');
    await thread();
    let first = true;
    bridge.override(async (request, url) => {
      if (request.method !== 'POST' || !first) return undefined;
      first = false;
      // the server took it, then the answer was lost
      const answer = bridge.assistant.handle({ operationId: 'E-MESSAGE', url, raw: await request.clone().text(), persona: 'pm', agents: [] });
      void answer;
      return json(502, { code: 'bad_gateway', message: 'Lost on the way.' });
    });
    type('Went through');
    send();
    await waitFor(() => expect(screen.getByText('Went through')).toBeTruthy());
    expect(box()).toHaveProperty('value', '');
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(assistantPosts()).toHaveLength(1);
  });

  it('a lost send is not taken for a delivered one just because the same words were sent before', async () => {
    await open('/assistant/CV-2401');
    await thread();
    // the thread already has "Create the invoice for Harmattan Bank milestone 2. ..." from the person
    type('Create the invoice for Harmattan Bank milestone 2. UAT was signed off on Friday. [500]'.replace(' [500]', ''));
    bridge.override((request) => (request.method === 'POST' ? Promise.reject(new TypeError('fetch failed')) : undefined));
    send();
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(box()).toHaveProperty('value', 'Create the invoice for Harmattan Bank milestone 2. UAT was signed off on Friday.');
  });

  it('a new conversation whose first message is lost reuses the same conversation on Try again', async () => {
    await open('/assistant');
    type('Plan it [500]');
    send();
    const alert = await screen.findByRole('alert');
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/assistant/CV-N1'));
    expect(assistantPosts().map((p) => p.path)).toEqual([
      '/api/v1/assistant/conversations',
      '/api/v1/assistant/conversations/CV-N1/messages',
      '/api/v1/assistant/conversations/CV-N1/messages',
    ]);
  });
});

describe('thread (SCR-05-desktop-thread)', () => {
  it('the ask, Chidi, the hand-off, 3 STEPS · DONE with records, the answer, three sources, the draft card', async () => {
    const { container } = await open('/assistant/CV-2401');
    const section = await thread();
    expect(container.querySelectorAll('h1')).toHaveLength(1);
    expect(container.querySelector('h1')?.textContent).toBe('Invoice · Harmattan Bank M2');
    const parts = [...section.children];
    expect(parts[0].textContent).toBe('Create the invoice for Harmattan Bank milestone 2. UAT was signed off on Friday.');
    const agent = within(parts[1] as HTMLElement);
    const body = (parts[1] as HTMLElement).querySelector('.cmp-chat__body')!;
    expect([...body.children].map((c) => c.className.split(' ')[0])).toEqual(['cmp-chat__handoff', 'psl-agent', 'cmp-chat__answer', 'cmp-chat__sources', 'cmp-draft']);
    expect(agent.getByText('Chidi')).toBeTruthy();
    expect(agent.getByText('· Finance agent')).toBeTruthy();
    expect(agent.getByText('Invoices are prepared by Chidi, the Finance agent, so Tola passed this to him.')).toBeTruthy();
    expect(agent.getByText('3 STEPS · DONE')).toBeTruthy();
    const steps = within(agent.getByRole('list')).getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    expect(steps[0].textContent).toContain('MILESTONE · HB-M2');
    expect(agent.getByText(/^I drafted the invoice from stage 2/)).toBeTruthy();
    const sources = body.querySelector('.cmp-chat__sources')!;
    expect([...sources.children].map((s) => s.textContent)).toEqual(['MILESTONE · HB-M2', 'SIGNED SOW v2 · stage 2', 'CLIENT · Harmattan Bank']);
    expect(within(sources as HTMLElement).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/projects/C-0102', '/projects/C-0102', '/projects/C-0102']);
    const draft = agent.getByRole('region', { name: 'Draft' });
    expect(within(draft).getByText('Invoice draft · Harmattan Bank · Milestone 2')).toBeTruthy();
    expect(within(draft).getByText('DRAFTED · NOT REVIEWED')).toBeTruthy();
    expect(within(draft).getByText('Amount').nextElementSibling?.textContent).toBe('₦6,800,000.00 (contract stage 2 of 3)');
    expect(within(draft).getByText('To')).toBeTruthy();
    expect(within(draft).getByText('Due terms')).toBeTruthy();
    expect(within(draft).getByText('Invoice · TEST TEMPLATE')).toBeTruthy();
    expect(within(draft).getByText('Next: Finance review by a Finance Lead')).toBeTruthy();
    expect(within(draft).getByRole('button', { name: 'Start this invoice' })).toBeTruthy();
    // what the board draws and this feature leaves out, and what an agent never offers
    expect(screen.queryByRole('button', { name: /edit draft|attach/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /approve|pay|send for/i })).toBeNull();
    const side = screen.getByRole('complementary', { name: 'Agent and context' });
    expect(within(side).getByText('Chidi has a draft ready for you to check.')).toBeTruthy();
    expect(within(side).getByText('Harmattan Bank · mobile onboarding')).toBeTruthy();
    expect(within(side).getByText('PMO on this project')).toBeTruthy();
    expect(within(list()).getByRole('link', { name: /^Invoice · Harmattan Bank M2/ }).getAttribute('aria-current')).toBe('page');
    expect(await violations()).toEqual([]);
  });

  it('opening a thread only reads: no write is sent', async () => {
    await open('/assistant/CV-2401');
    await thread();
    expect(bridge.seen.filter((s) => s.method !== 'GET')).toEqual([]);
  });

  it('agent text is text: markup and markdown render literally and make no element', async () => {
    const { container } = await open('/assistant/CV-2401', 'pm', (made) =>
      made.override((request, url) =>
        url.pathname === '/api/v1/assistant/conversations/CV-2401'
          ? json(200, {
              conversation_id: 'CV-2401',
              agent: 'chidi',
              title: '<b>title</b>',
              status: 'answered',
              context: { project: { case_id: 'C-1', title: '<u>project</u>' }, access: ['<i>access</i>'] },
              messages: [
                { role: 'person', text: '<script>alert(1)</script>', steps: [], sources: [] },
                {
                  role: 'agent',
                  text: '<img src=x onerror=alert(1)> and **bold**',
                  steps: ['<i>step</i>'],
                  sources: [{ kind: '<u>k</u>', reference: 'r', restricted: false }],
                  handoff: { note: '<a href=x>note</a>' },
                  cannot_reason: '<b>why</b>',
                  draft: { title: '<em>draft</em>', status_label: '<s>label</s>', rows: [{ label: '<b>l</b>', value: '<img src=y>' }], next: '<br>next' },
                },
              ],
            })
          : undefined,
      ),
    );
    const section = await thread();
    expect(section.textContent).toContain('<script>alert(1)</script>');
    expect(section.textContent).toContain('<img src=x onerror=alert(1)> and **bold**');
    expect(section.textContent).toContain('<i>step</i>');
    expect(section.textContent).toContain('<a href=x>note</a>');
    expect(section.textContent).toContain('<img src=y>');
    expect(screen.getByRole('complementary', { name: 'Agent and context' }).textContent).toContain('<u>project</u>');
    // the only images are the avatars and mascots; nothing was made from the text
    expect([...container.querySelectorAll('img')].every((img) => img.getAttribute('src')?.startsWith('/agents/'))).toBe(true);
    expect(container.querySelector('script, b, i, u, em, s, br, a[href="x"]')).toBeNull();
    expect(container.querySelector('h1')?.textContent).toBe('<b>title</b>');
  });

  it('CV-2402 (a draft with no start) has no start button', async () => {
    await open('/assistant/CV-2402');
    const draft = await screen.findByRole('region', { name: 'Draft' });
    expect(within(draft).queryByRole('button')).toBeNull();
    expect(within(draft).getByText('Next: estimates, then PMO → PMO Lead → CEO')).toBeTruthy();
  });

  it('CV-2403: the restricted source shows a lock and "Restricted" only; its label is nowhere in the page and it is not a link', async () => {
    const { container } = await open('/assistant/CV-2403');
    await thread();
    const body = document.body.textContent ?? '';
    expect(body).not.toContain('FINANCE MEMO');
    expect(body).toContain('Restricted');
    const tag = container.querySelector('.cmp-source--restricted')!;
    expect(tag.textContent).toBe('Restricted');
    expect(tag.closest('a')).toBeNull();
    expect(container.querySelector('a[href*="0042"]')).toBeNull();
    expect(within(screen.getByRole('complementary', { name: 'Agent and context' })).getByText('Chidi answered from records you can see.')).toBeTruthy();
  });

  it('CV-2404 reads through the generic renderer: the access sentence and the reason', async () => {
    await open('/assistant/CV-2404');
    await thread();
    expect(screen.getByText('Individual pay is restricted to HR roles.')).toBeTruthy();
    expect(screen.getByText('Zainab can’t do that with your access.')).toBeTruthy();
  });

  it('CV-2404 shows the cant pose in the side panel and no phone pose card at 1440', async () => {
    await open('/assistant/CV-2404');
    await thread();
    const pose = within(screen.getByRole('complementary', { name: 'Agent and context' })).getByAltText('Zainab pose');
    expect(pose.getAttribute('src')).toBe('/agents/zainab-cant.png');
    expect(screen.queryByAltText('Zainab, can’t do this')).toBeNull();
    expect(screen.getByText('PMO · no payroll access')).toBeTruthy();
    // text and reason are separate lines; no new control
    const reason = screen.getByText('Individual pay is restricted to HR roles.');
    expect(reason.closest('.cmp-chat__cannot')).toBe(reason);
    expect(screen.getByText(/I can’t share an individual’s pay/).closest('.cmp-chat__cannot')).toBeNull();
    expect(screen.queryByRole('button', { name: /start this|edit draft|staff-cost|ask hr/i })).toBeNull();
    expect(bridge.seen.filter((s) => s.method !== 'GET')).toEqual([]);
  });

  it('CV-2404: the restricted record label is nowhere in the page, at 1440 and 390', async () => {
    await open('/assistant/CV-2404');
    await thread();
    expect(document.body.textContent).not.toContain('ACCESS · payroll');
    expect(document.body.textContent).toContain('Restricted');
    cleanup();
    phone();
    await open('/assistant/CV-2404');
    await thread();
    expect(document.body.textContent).not.toContain('ACCESS · payroll');
    expect(document.body.textContent).toContain('Restricted');
  });

  it('cannot_reason is text: markup and markdown render literally and make no element', async () => {
    const reason = '<img src=x onerror=alert(1)> and **bold**';
    const { container } = await open('/assistant/CV-2404', 'pm', (made) =>
      made.override((request, url) => {
        if (url.pathname !== '/api/v1/assistant/conversations/CV-2404') return undefined;
        const base = JSON.parse(JSON.stringify(fixture2404));
        base.messages[1].cannot_reason = reason;
        return json(200, base);
      }),
    );
    await thread();
    const line = screen.getByText(reason);
    expect(line.closest('.cmp-chat__cannot')).toBe(line);
    expect(container.querySelector('.as__thread img[src="x"]')).toBeNull();
    expect(container.querySelector('.cmp-chat__cannot b, .cmp-chat__cannot img')).toBeNull();
  });

  it('on a phone only the cannot_answer thread has the inline pose card', async () => {
    phone();
    await open('/assistant/CV-2404');
    await thread();
    expect(screen.getByAltText('Zainab, can’t do this').getAttribute('src')).toBe('/agents/zainab-cant.png');
    expect(screen.queryByRole('complementary', { name: 'Agent and context' })).toBeNull();
    cleanup();
    for (const id of ['CV-2401', 'CV-2403']) {
      await open(`/assistant/${id}`);
      await thread();
      expect(screen.queryByAltText(/can’t do this/)).toBeNull();
      cleanup();
    }
  });

  it('poseFor maps each status', () => {
    expect(poseFor({ status: 'cannot_answer' })).toBe('cant');
    expect(poseFor({ status: 'working' })).toBe('working');
    expect(poseFor({ status: 'drafted' })).toBe('done');
    expect(poseFor({ status: 'answered' })).toBe('idle');
  });

  it('CV-2406: an unknown amount is the amber "Unknown", never 0 or blank', async () => {
    const { container } = await open('/assistant/CV-2406');
    const draft = await screen.findByRole('region', { name: 'Draft' });
    const amount = within(draft).getByText('Amount').nextElementSibling!;
    expect(amount.textContent).toBe('Unknown');
    expect(amount.querySelector('.psl-unknown')).toBeTruthy();
    expect(draft.textContent).not.toMatch(/₦0|\b0\b/);
    expect(container.querySelector('.cmp-draft button')).toBeNull();
  });
});

describe('wrong user, unknown id, signed out', () => {
  it('finance_lead opening CV-2401 and anyone opening CV-2499 see nothing of the conversation', async () => {
    const { container } = await open('/assistant/CV-2401', 'finance_lead');
    expect(await screen.findByText('We could not find that conversation.')).toBeTruthy();
    expect(container.textContent).not.toContain('Invoice · Harmattan Bank M2');
    expect(container.textContent).not.toContain('Create the invoice');
    expect(container.textContent).not.toContain('Finance agent');
    expect(screen.queryByRole('region', { name: 'Conversation' })).toBeNull();
    expect(container.querySelectorAll('h1')).toHaveLength(1);
  });

  it('CV-2499 is the reserved no-access id', async () => {
    await open('/assistant/CV-2499');
    expect(await screen.findByText('We could not find that conversation.')).toBeTruthy();
  });

  it('finance_lead opening CV-2404 sees nothing of the refusal', async () => {
    const { container } = await open('/assistant/CV-2404', 'finance_lead');
    expect(await screen.findByText('We could not find that conversation.')).toBeTruthy();
    expect(container.textContent).not.toContain('A staff member');
    expect(container.textContent).not.toContain('Individual pay is restricted');
    expect(container.textContent).not.toContain('Zainab');
    expect(screen.queryByAltText(/can’t do this/)).toBeNull();
  });

  it('anyone opening an unknown id next to CV-2404 sees nothing of it', async () => {
    const { container } = await open('/assistant/CV-2498');
    expect(await screen.findByText('We could not find that conversation.')).toBeTruthy();
    expect(container.textContent).not.toContain('Individual pay');
  });

  it('401 on the read shows the signed-out callout with next = this URL', async () => {
    bridge = startBridge();
    nav.pathname = '/assistant/CV-2401';
    vi.stubGlobal('fetch', bridge.stub);
    bridge.override((request, url) => (url.pathname.startsWith('/api/v1/assistant/conversations/') ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined));
    setCsrfToken('mock-csrf-pm');
    render(
      <AppShell>
        <AssistantFrame>
          <ThreadPage id="CV-2401" />
        </AssistantFrame>
      </AppShell>,
    );
    const links = await screen.findAllByRole('link', { name: 'Sign in' });
    expect(links[0].getAttribute('href')).toContain(`next=${encodeURIComponent('/assistant/CV-2401')}`);
  });
});

describe('working and polling (SCR-05-desktop-working)', () => {
  const reads = () => bridge.gets(/\/assistant\/conversations\/CV-2405$/).length;
  const listReads = () => bridge.gets(/\/assistant\/conversations$/).length;

  it('shows WORKING · STEP 3 OF 5, the five steps in words with their records, and the side sentence', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2405');
    const section = await thread();
    expect(within(section).getByText('WORKING · STEP 3 OF 5')).toBeTruthy();
    const steps = within(section).getAllByRole('listitem');
    expect(steps.map((s) => s.textContent)).toEqual([
      'Done: Read the award letterRead: AWARD LETTER · 04 DEC',
      'Done: Pulled the approved response and costingRead: RESPONSE v3 · COSTING v2',
      'In progress: Matching team estimates to the scopeRead: ENGINEERING 210D · SECURITY 18D',
      '4To do: List what is still unknown',
      '5To do: Hand the packet to you',
    ]);
    expect(screen.getByText('Tola is working on it. You can leave; you’ll be alerted.')).toBeTruthy();
  });

  it('reads again every 5 s, waits while the tab is hidden, resumes when visible, and stops after the answer (list re-read once)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2405');
    const section = await thread();
    expect(reads()).toBe(1);
    const lists = listReads();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(reads()).toBe(2);
    expect(within(section).getByText('WORKING · STEP 4 OF 5')).toBeTruthy();

    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(reads()).toBe(2);
    visibility.mockReturnValue('visible');
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(reads()).toBe(3);
    expect(within(section).getByText('WORKING · STEP 5 OF 5')).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(reads()).toBe(4);
    expect(screen.queryByText(/You can leave/)).toBeNull();
    expect(screen.getByText('Sample answer from the contract mock. No agent ran.')).toBeTruthy();
    expect(screen.getByText('Tola answered from records you can see.')).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(reads()).toBe(4);
    expect(listReads()).toBe(lists + 1);
    expect(within(list()).getByRole('link', { name: /^Planning packet/ }).textContent).toContain('Answered');
  });

  it('a failed poll keeps the last good data with a quiet line, no error page', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2405');
    const section = await thread();
    bridge.override((request, url) => (url.pathname.endsWith('/CV-2405') ? json(500, { code: 'server_error', message: 'x' }) : undefined));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(screen.getByText('Couldn’t refresh. Retrying.')).toBeTruthy();
    expect(within(section).getByText('WORKING · STEP 3 OF 5')).toBeTruthy();
    bridge.override(undefined);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(screen.queryByText('Couldn’t refresh. Retrying.')).toBeNull();
  });

  it('a reload shows the advanced step, not step 3, and sends no write', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const first = await open('/assistant/CV-2405');
    await thread();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    first.unmount();
    // the mock keeps the run across the "reload"; a fresh page reads the current state
    const again = render(
      <AppShell>
        <AssistantFrame>
          <ThreadPage id="CV-2405" />
        </AssistantFrame>
      </AppShell>,
    );
    expect(await within(again.container).findByText('WORKING · STEP 5 OF 5')).toBeTruthy();
    expect(bridge.seen.filter((s) => s.method !== 'GET')).toEqual([]);
  });

  it('on a phone the card names the task, the agent and step, WORKING and when it started', async () => {
    phone();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2405');
    const section = await thread();
    expect(within(section).getByText('Planning packet · Tamarind Loans')).toBeTruthy();
    expect(within(section).getByText('Tola · PMO agent · step 3 of 5')).toBeTruthy();
    expect(within(section).getByText('WORKING')).toBeTruthy();
    expect(within(section).getByText('Started 14:02')).toBeTruthy();
    // phones draw no side panel
    expect(screen.queryByRole('complementary', { name: 'Agent and context' })).toBeNull();
  });
});

describe('mentions', () => {
  it('no request for an empty query; one GET after the pause; choose a project; Send carries it; remove takes it off', async () => {
    await open('/assistant');
    fireEvent.click(screen.getByRole('button', { name: '@ Mention a project or record' }));
    const search = screen.getByRole('searchbox', { name: 'Search projects and records' });
    await waitFor(() => expect(document.activeElement).toBe(search));
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(bridge.gets(/\/assistant\/mentions/)).toEqual([]);
    fireEvent.change(search, { target: { value: 'harm' } });
    const option = await screen.findByRole('button', { name: /^Harmattan Bank · mobile onboarding/ });
    expect(bridge.gets(/\/assistant\/mentions/).map((s) => s.search)).toEqual(['?q=harm']);
    expect(within(option).getByText('SAMPLE DATA')).toBeTruthy();
    // Harriet Eze also matches "harm"? no: only returned items are listed
    expect(screen.getAllByRole('button').filter((b) => b.classList.contains('as-mention__item')).map((b) => b.querySelector('strong')?.textContent)).toEqual(['Harmattan Bank · mobile onboarding', 'Harmattan Bank go-live report', 'Harmattan Bank signed SOW v2']);
    fireEvent.click(option);
    expect(screen.getByText('@Harmattan Bank · mobile onboarding')).toBeTruthy();
    type('Where are we');
    send();
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(assistantPosts()[1].body).toEqual({ text: 'Where are we', mentions: [{ kind: 'project', id: 'P-0102' }] });
  });

  it('removing the chip removes it from the body', async () => {
    await open('/assistant');
    fireEvent.click(screen.getByRole('button', { name: '@ Mention a project or record' }));
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search projects and records' }), { target: { value: 'harm' } });
    fireEvent.click(await screen.findByRole('button', { name: /^Harmattan Bank signed SOW v2/ }));
    expect(screen.getByText('#Harmattan Bank signed SOW v2')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Remove #Harmattan Bank signed SOW v2' }));
    type('Hello');
    send();
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(assistantPosts()[1].body).toEqual({ text: 'Hello' });
  });

  it('nothing matching and a failed load are said in words; Escape closes and returns focus', async () => {
    await open('/assistant');
    const opener = screen.getByRole('button', { name: '@ Mention a project or record' });
    fireEvent.click(opener);
    const search = screen.getByRole('searchbox', { name: 'Search projects and records' });
    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(await screen.findByText('Nothing you can mention matches.')).toBeTruthy();
    bridge.override((request, url) => (url.pathname === '/api/v1/assistant/mentions' ? json(500, { code: 'server_error', message: 'x' }) : undefined));
    fireEvent.change(search, { target: { value: 'harm' } });
    expect(await screen.findByText('Couldn’t load. Try again.')).toBeTruthy();
    fireEvent.keyDown(search, { key: 'Escape' });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await waitFor(() => expect(screen.queryByRole('searchbox')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe('the held microphone', () => {
  it('pressing it by click or keyboard sends nothing and changes nothing; no speech API is used', async () => {
    await open('/assistant');
    type('Keep this');
    const mic = screen.getByRole('button', { name: 'Speak your request' });
    mic.focus();
    fireEvent.click(mic);
    fireEvent.keyDown(mic, { key: 'Enter' });
    fireEvent.keyDown(mic, { key: ' ' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(assistantPosts()).toEqual([]);
    expect(box()).toHaveProperty('value', 'Keep this');
    expect(Object.keys(window).filter((key) => /speech|getUserMedia/i.test(key))).toEqual([]);
  });
});

describe('phone home', () => {
  it('shows "5 earlier", which opens the conversation list as a sheet; no mic, no side panel', async () => {
    phone();
    await open('/assistant');
    await screen.findByRole('button', { name: '5 earlier' });
    expect(screen.queryByRole('button', { name: 'Speak your request' })).toBeNull();
    expect(screen.queryByRole('complementary', { name: 'Agent and context' })).toBeNull();
    expect(screen.getByRole('button', { name: '@ Mention' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '5 earlier' }));
    const sheet = await screen.findByRole('dialog', { name: 'Earlier conversations' });
    expect(within(sheet).getAllByRole('link')).toHaveLength(5);
    expect(within(sheet).getByText('TODAY')).toBeTruthy();
  });
});

describe('"Start this invoice" opens the normal Start work drawer, prefilled', () => {
  const dialog = () => screen.getByRole('dialog');
  const shown = (name: string) => within(dialog()).getByRole('combobox', { name }).querySelector('.sw-picker__value')!.textContent;
  const startsRequests = () => bridge.posts(/^\/api\/v1\/work$/);

  async function openDrawer() {
    await open('/assistant/CV-2401');
    await thread();
    fireEvent.click(screen.getByRole('button', { name: 'Start this invoice' }));
    await screen.findByRole('dialog', { name: 'Invoice preparation and delivery' });
    await waitFor(() => expect(shown('Completed milestone')).toBe('Milestone 2 · beta signed 30 Oct'));
  }

  it('shows the project and milestone chosen and sends nothing until the person presses the drawer’s own button', async () => {
    await openDrawer();
    expect(shown('Project')).toBe('Harmattan Bank · mobile onboarding');
    expect(startsRequests()).toEqual([]);
    expect(assistantPosts()).toEqual([]);
    expect(within(dialog()).getByRole('button', { name: 'Start the invoice' })).toBeTruthy();
    // the agent offers no start of its own, and the page's button waits behind the drawer
    expect(bridge.seen.filter((s) => s.method === 'POST')).toEqual([]);
  });

  it('one POST /api/v1/work with the typed body and CSRF; the drawer closes, the thread re-reads and shows "Started INV-0415." with focus on it', async () => {
    await openDrawer();
    const reads = bridge.gets(/\/assistant\/conversations\/CV-2401$/).length;
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Start the invoice' }));
    const line = await screen.findByText(/^Started INV-0415\./);
    expect(screen.queryByRole('dialog')).toBeNull();
    const [start] = startsRequests();
    expect(startsRequests()).toHaveLength(1);
    expect(start.body).toEqual({ line: 'invoice', case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' }, idempotency_key: expect.any(String) });
    expect(start.headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(bridge.gets(/\/assistant\/conversations\/CV-2401$/).length).toBe(reads + 1);
    expect(nav.push).not.toHaveBeenCalled();
    const status = line.closest('p')!;
    expect(status.getAttribute('role')).toBe('status');
    expect(within(status).getByRole('link', { name: 'Open the work item' }).getAttribute('href')).toBe('/work/W-1401');
    await waitFor(() => expect(document.activeElement).toBe(status));
    expect(screen.queryByRole('button', { name: 'Start this invoice' })).toBeNull();
    expect(within(screen.getByRole('complementary', { name: 'Agent and context' })).getByText('Chidi answered from records you can see.')).toBeTruthy();
    // the list row follows the data, and the assistant wrote nothing itself
    expect(await within(list()).findByText('Started · INV-0415')).toBeTruthy();
    expect(assistantPosts()).toEqual([]);
  });

  it('closing the drawer without a start puts focus back on the draft button', async () => {
    await openDrawer();
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Start this invoice' })));
    expect(startsRequests()).toEqual([]);
  });

  it('an uncertain start shows Start work’s own notice; the assistant sends nothing and never retries', async () => {
    await openDrawer();
    bridge.override((request, url) => (request.method === 'POST' && url.pathname === '/api/v1/work' ? Promise.reject(new TypeError('fetch failed')) : undefined));
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Start the invoice' }));
    expect(await within(dialog()).findByText(/We couldn’t confirm the start/)).toBeTruthy();
    expect(startsRequests()).toHaveLength(1);
    expect(assistantPosts()).toEqual([]);
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(startsRequests()).toHaveLength(1);
  });

  it('a second tab that still shows the button gets the 409 through the drawer, then re-reads and shows the started line; one 201 exists', async () => {
    await openDrawer();
    // another tab started it first
    const [first] = [
      await bridge.stub(
        new Request('http://localhost/api/v1/work', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ line: 'invoice', case_id: 'C-0102', case_revision: 3, intake: { project: 'P-0102', milestone: 'M-0202' }, idempotency_key: 'other-tab' }),
        }),
      ),
    ];
    expect(first.status).toBe(201);
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Start the invoice' }));
    expect(await within(dialog()).findByText(/changed since you opened the form/)).toBeTruthy();
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Close' }));
    const line = await screen.findByText(/^Started INV-0415\./);
    expect(screen.queryByRole('button', { name: 'Start this invoice' })).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(line.closest('p')));
    // one 201 exists: the other tab's; this tab's press was refused
    expect(startsRequests()).toHaveLength(2);
  });

  it('a draft whose line this person cannot start opens the drawer with "You can’t start this here." and no form', async () => {
    await open('/assistant/CV-2411', 'finance_lead');
    await thread();
    fireEvent.click(screen.getByRole('button', { name: 'Start this report' }));
    expect(await screen.findByText('You can’t start this here.')).toBeTruthy();
    expect(within(dialog()).queryByRole('combobox')).toBeNull();
    expect(within(dialog()).queryByRole('button', { name: /^Start the/ })).toBeNull();
    expect(startsRequests()).toEqual([]);
  });
});

const dialog = () => screen.getByRole('dialog');

describe('phone: the bar and the footer', () => {
  it('the home bar reads "← Home" and "5 earlier" (a button that opens the list)', async () => {
    phone();
    await open('/assistant');
    expect(await screen.findByRole('link', { name: 'Back to Home' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '5 earlier' }).className).toContain('shell-phonenote');
  });

  it('the thread bar carries "← Assistant" and the title; the working card is the only byline', async () => {
    phone();
    await open('/assistant/CV-2405');
    const section = await thread();
    expect(screen.getByRole('link', { name: 'Back to Assistant' })).toBeTruthy();
    expect(within(section).queryByText('· PMO agent')).toBeNull();
    expect(within(section).getAllByText(/Tola · PMO agent/)).toHaveLength(1);
  });

  it('after the start the footer is a full-width "Open INV-0415" link to the work item, in place of the composer', async () => {
    phone();
    await open('/assistant/CV-2401');
    await thread();
    fireEvent.click(screen.getByRole('button', { name: 'Start this invoice' }));
    await screen.findByRole('dialog');
    await waitFor(() => expect((within(dialog()).getByRole('button', { name: 'Start the invoice' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(dialog()).getByRole('button', { name: 'Start the invoice' }));
    const footer = await screen.findByRole('link', { name: 'Open INV-0415' });
    expect(footer.getAttribute('href')).toBe('/work/W-1401');
    expect(footer.className).toContain('psl-btn--block');
    expect(screen.queryByRole('textbox')).toBeNull();
  });
});
