// @vitest-environment jsdom
// F-41 SCR-32: Chidi's payment reminder on the F-17 line workspace (PROPOSAL D-LINE-WORKSPACE, contract mock fixtures
// W-3801 to W-3813). The fetch stub stands in for the backend. Nothing here proves a real email, a real delivery, the
// backend's idempotency or its resend refusal: it proves the page sends one write per press, shows only what the re-read
// item says, and never sends again by itself while delivery is uncertain.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { reloadPage } from '@/features/response';
import type { WorkItem } from '@/features/work-item/labels';
import { WorkItemView } from '@/features/work-item/WorkItemView';
import { AppShell } from '@/shell/AppShell';
import { withoutBellFeed } from './bell-feed';

configure({ asyncUtilTimeout: 5000 });

vi.mock('next/navigation', () => ({
  usePathname: () => '/work/W-3801',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/features/response/reload', () => ({ reloadPage: vi.fn() }));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const item = (name: string): WorkItem => read(`work/${name}.json`);
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validStepBody = ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.requestBody.content['application/json'].schema);

type Sent = { method: string; path: string; body: Record<string, unknown> | undefined; csrf: string | null };
let sent: Sent[];
let itemAnswers: (WorkItem | (() => Response | Promise<Response>))[];
let stepAnswers: (Response | (() => Response | Promise<Response>))[];
let persona: string;

const posts = (suffix = '/steps') => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const ok = (extra: Record<string, unknown> = {}) => json(200, { work_id: 'W-3801', state: 'action_needed', revision: 2, outcome: 'done', ...extra });

beforeEach(() => {
  sent = [];
  itemAnswers = [];
  stepAnswers = [];
  persona = 'finance_lead';
  vi.stubGlobal(
    'fetch',
    withoutBellFeed(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      sent.push({ method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') });
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${persona}.json`));
      if (request.method === 'GET' && url.pathname.startsWith('/api/v1/work/')) {
        const next = itemAnswers.length > 1 ? itemAnswers.shift()! : itemAnswers[0];
        return typeof next === 'function' ? next() : json(200, next);
      }
      if (url.pathname.endsWith('/steps')) {
        const answer = stepAnswers.length > 1 ? stepAnswers.shift()! : (stepAnswers[0] ?? ok());
        return typeof answer === 'function' ? answer() : answer;
      }
      if (url.pathname.endsWith('/actions')) return json(200, { work_id: 'W-3803', state: 'followup_needed', revision: 3 });
      return json(404, { code: 'not_found', message: 'Not here.' });
    }),
  );
  vi.mocked(reloadPage).mockClear();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open(first: WorkItem, ...later: (WorkItem | (() => Response))[]) {
  itemAnswers = [first, ...later];
  const view = render(
    <AppShell>
      <WorkItemView id={first.id} tab="overview" />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: first.title });
  return view;
}
const wsEl = () => document.querySelector('.ws') as HTMLElement;
const ws = () => within(wsEl());
const button = (name: string) => ws().getByRole('button', { name });
const isOff = (el: HTMLElement) => el.getAttribute('aria-disabled') === 'true';
const fact = (label: string) => (ws().getByText(label, { selector: 'dt' }).nextElementSibling as HTMLElement).textContent;
const statusTag = () => document.querySelector('.work-state')!.textContent;

describe('the draft from data (AC 12, 13, 14)', () => {
  it('W-3801: crumbs, title, subtitle, To / Copy / Subject, the four paragraphs, the attachment, the invoice facts and Chidi’s one line', async () => {
    await open(item('W-3801'));
    expect(within(screen.getByRole('navigation', { name: 'Where this sits' })).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['FINANCE', 'PAYMENTS', 'INV-0391 · REMINDER']);
    expect(screen.getByText('Chidi drafted this from the invoice and the SOW payment terms. Nothing is sent until you press Send.')).toBeTruthy();
    expect(fact('To')).toBe('finance@harmattanbank.example');
    expect(fact('Copy')).toBe('Kunle Ade (PM)');
    expect(fact('Subject')).toBe('Reminder: invoice INV-0391 is 21 days overdue');
    const text = wsEl().textContent!;
    for (const p of ['Dear Harmattan Bank Finance team,', 'Our records show invoice INV-0391 for ₦6,800,000.00 (Milestone 1, mobile onboarding) was due on 22 Oct', 'If you\'ve already paid, please send the payment reference', 'Kind regards,']) expect(text, p).toContain(p);
    expect(wsEl().querySelector('.ws-attachment')!.textContent).toBe('INV-0391.pdf · Uploaded · 84 KB');
    expect(wsEl().querySelector('.ws-attachment a')).toBeNull();
    // UI-2-2: the board's dashed box with the paperclip, never a link
    expect(wsEl().querySelector('.ws-attachment svg.psl-icon')).not.toBeNull();
    expect(ws().getByRole('heading', { name: 'This invoice' })).toBeTruthy();
    expect([fact('Amount'), fact('Due'), fact('Overdue by'), fact('Reminders sent'), fact('Last payment')]).toEqual(['₦6,800,000.00', '22 Oct 2026', '21 days', 'None yet', 'None']);
    expect(ws().getByText('After you send it, I\'ll check it was delivered.')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/7 days|second reminder/);
    expect(ws().getByText('Draft v1')).toBeTruthy();
    // the controls are the three returned steps; Send says it reaches the client
    expect(['Send reminder', 'Edit', 'Not now'].map((n) => isOff(button(n)))).toEqual([false, false, false]);
    expect(ws().getByText('This sends to the client.')).toBeTruthy();
  });

  it('agent work is not a send: Chidi’s note is agent text, no status says sent, delivered or verified, and nothing is posted on load', async () => {
    await open(item('W-3801'));
    expect(ws().getByText('After you send it, I\'ll check it was delivered.').closest('.ws-agentnote')).not.toBeNull();
    expect(statusTag()).not.toMatch(/SENT|DELIVERED|VERIFIED|RECEIVED/i);
    expect(ws().queryByText(/^(Sent|Delivered|Received|Verified)$/)).toBeNull();
    expect(sent.filter((r) => r.method !== 'GET')).toHaveLength(0);
  });

  it('W-3812 draws no attachment line; W-3813 (sample: false) has no SAMPLE DATA label', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    const view = await open(item('W-3812'));
    expect(wsEl().querySelector('.ws-attachment')).toBeNull();
    expect(document.body.textContent).not.toContain('INV-0391.pdf');
    view.unmount();
    await open(item('W-3813'));
    expect(document.querySelector('.work-lineend')!.textContent).not.toContain('SAMPLE DATA');
    vi.unstubAllEnvs();
  });

  it('W-3810: Amount, Overdue by and Last payment read Unknown, never None, ₦0.00 or blank', async () => {
    await open(item('W-3810'));
    expect([fact('Amount'), fact('Overdue by'), fact('Last payment')]).toEqual(['Unknown', 'Unknown', 'Unknown']);
    expect(ws().getByText('Amount', { selector: 'dt' }).nextElementSibling!.querySelector('.psl-unknown')).not.toBeNull();
    expect(fact('Reminders sent')).toBe('None yet');
    expect(wsEl().textContent).not.toContain('₦0.00');
  });
});

describe('send (AC 15)', () => {
  it('one press is one POST with the CSRF header and a schema-valid body; a double press sends one; the page says sent only from the re-read', async () => {
    await open(item('W-3801'), item('W-3801.next.send_reminder'));
    await act(async () => {
      fireEvent.click(button('Send reminder'));
      fireEvent.click(button('Send reminder'));
    });
    await waitFor(() => expect(statusTag()).toBe('SENT · CHECKING DELIVERY'));
    expect(posts()).toHaveLength(1);
    const [post] = posts();
    expect(post.path).toBe('/api/v1/work/W-3801/steps');
    expect(post.csrf).toBe('mock-csrf-finance_lead');
    expect(Object.keys(post.body!).sort()).toEqual(['expected_revision', 'idempotency_key', 'step']);
    expect(post.body).toMatchObject({ expected_revision: 1, step: 'send_reminder' });
    expect(post.body!.idempotency_key).toMatch(UUID);
    expect(validStepBody(post.body), ajv.errorsText(validStepBody.errors)).toBe(true);
    const delivery = within(ws().getByRole('heading', { name: 'Delivery' }).closest('section') as HTMLElement);
    expect(delivery.getAllByText('Not yet')).toHaveLength(2);
    expect(delivery.queryByText('Received')).toBeNull();
    expect(fact('Reminders sent')).toBe('1 · 12 Nov');
    expect(ws().queryByRole('button', { name: 'Send reminder' })).toBeNull();
  });

  it('a 200 whose re-read still serves the draft says nothing is sent', async () => {
    await open(item('W-3801'), item('W-3801'));
    fireEvent.click(button('Send reminder'));
    await waitFor(() => expect(posts()).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3801').length).toBeGreaterThanOrEqual(2));
    expect(statusTag()).not.toMatch(/SENT/);
    expect(document.body.textContent).not.toMatch(/\bSent\b|Delivered|Received/);
  });

  it('TECH-1-1: no "Done: Send reminder." while the re-read is in flight; the notice comes only after it lands', async () => {
    let land: (r: Response) => void = () => {};
    const held = () => new Promise<Response>((resolve) => (land = resolve));
    await open(item('W-3801'), held as unknown as () => Response, item('W-3801.next.send_reminder'));
    fireEvent.click(button('Send reminder'));
    await waitFor(() => expect(posts()).toHaveLength(1));
    await waitFor(() => expect(sent.filter((r) => r.method === 'GET' && r.path === '/api/v1/work/W-3801').length).toBe(2));
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(document.body.textContent).not.toContain('Done: Send reminder.');
    expect(statusTag()).not.toMatch(/SENT/);
    await act(async () => land(json(200, item('W-3801.next.send_reminder'))));
    await waitFor(() => expect(statusTag()).toBe('SENT · CHECKING DELIVERY'));
    expect(screen.getByText('Done: Send reminder.')).toBeTruthy();
  });

  it('W-3802: "Received" for each recipient only from receipt: received, with its time; the status is the backend’s DELIVERED', async () => {
    await open(item('W-3802'));
    expect(statusTag()).toBe('DELIVERED');
    const delivery = within(ws().getByRole('heading', { name: 'Delivery' }).closest('section') as HTMLElement);
    expect(delivery.getAllByText('Received')).toHaveLength(2);
    expect(delivery.getAllByText('12 Nov 11:06')).toHaveLength(2);
    expect(ws().queryAllByRole('button')).toEqual([]);
  });

  it('a recipient whose receipt is not received never reads Received, whatever the status says', async () => {
    const body = item('W-3802');
    const section = body.workspace!.sections.find((s) => s.kind === 'recipients')!;
    (section.items[1] as { receipt: string }).receipt = 'not_yet';
    await open(body);
    const delivery = within(ws().getByRole('heading', { name: 'Delivery' }).closest('section') as HTMLElement);
    const second = within(delivery.getByText('Kunle Ade (PM)').closest('li') as HTMLElement);
    expect(second.getByText('Not yet')).toBeTruthy();
    expect(second.queryByText('Received')).toBeNull();
  });
});

describe('an uncertain send is never sent again by the page (AC 16, INV-RESEND)', () => {
  const lockedAll = () => ['Send reminder', 'Edit', 'Not now'].every((n) => isOff(button(n)));

  it('W-3803: effect_uncertain re-reads, shows the notice and each recipient Uncertain, turns every step off and offers reconcile only', async () => {
    stepAnswers = [ok({ outcome: 'effect_uncertain', message: 'Delivery to Harmattan Bank couldn’t be confirmed.' })];
    await open(item('W-3803'), item('W-3803.next'));
    fireEvent.click(button('Send reminder'));
    await screen.findByText('Delivery to Harmattan Bank couldn’t be confirmed.');
    await waitFor(() => expect(statusTag()).toBe('DELIVERY UNCERTAIN'));
    // UX-2-1: the re-read's subtitle no longer says nothing is sent until Send is pressed
    expect(document.body.textContent).not.toContain('Nothing is sent until you press Send.');
    const delivery = within(ws().getByRole('heading', { name: 'Delivery' }).closest('section') as HTMLElement);
    expect(delivery.getAllByText('Uncertain')).toHaveLength(2);
    expect(lockedAll()).toBe(true);
    expect(await screen.findByRole('group', { name: 'Confirm what happened' })).toBeTruthy();
    // pressing an off step sends nothing
    fireEvent.click(button('Send reminder'));
    fireEvent.click(button('Not now'));
    expect(posts()).toHaveLength(1);
    // reconcile: one E-WORK-ACTION with the chosen outcome; the reload decides the view, nothing is resent
    fireEvent.click(screen.getByRole('radio', { name: /It didn’t arrive/ }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Record and continue' }));
      fireEvent.click(screen.getByRole('button', { name: /Record and continue|Recording/ }));
    });
    await waitFor(() => expect(posts('/actions')).toHaveLength(1));
    expect(posts('/actions')[0].body).toEqual({ expected_revision: 2, action: 'reconcile', outcome: 'not_delivered' });
    expect(vi.mocked(reloadPage)).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(1);
  });

  it.each([
    ['W-3804 a 500', () => json(500, { code: 'server_error', message: 'x' })],
    ['a routed network abort', () => Promise.reject(new TypeError('offline'))],
  ])('%s on send re-reads, shows the uncertain item and sends nothing again', async (_name, answer) => {
    stepAnswers = [answer as () => Response];
    await open(item('W-3804'), item('W-3804.next'));
    fireEvent.click(button('Send reminder'));
    await waitFor(() => expect(statusTag()).toBe('DELIVERY UNCERTAIN'));
    expect(screen.getByText('We couldn’t confirm this step. Check the page before trying again.')).toBeTruthy();
    expect(lockedAll()).toBe(true);
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    fireEvent.click(button('Send reminder'));
    expect(posts()).toHaveLength(1);
  });

  it('a send that hangs for 60 s stays one POST: the page waits and never sends again by itself', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stepAnswers = [() => new Promise<Response>(() => {})];
    await open(item('W-3801'));
    fireEvent.click(button('Send reminder'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(posts()).toHaveLength(1);
    expect(button('Send reminder…')).toBeTruthy();
    fireEvent.click(button('Send reminder…'));
    fireEvent.click(button('Not now'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(1);
  });

  it('W-3805 opened fresh (the reload case): every step off, reconcile offered, Send sends nothing', async () => {
    await open(item('W-3805'));
    expect(lockedAll()).toBe(true);
    expect(await screen.findByRole('group', { name: 'Confirm what happened' })).toBeTruthy();
    expect(screen.getByText('Confirm what happened first.')).toBeTruthy();
    fireEvent.click(button('Send reminder'));
    expect(posts()).toHaveLength(0);
  });

  it('W-3806: no reconcile for this person; the page says who must confirm and draws no reconcile control', async () => {
    await open(item('W-3806'));
    expect(screen.getByText('Someone with reconcile access needs to confirm what happened first.')).toBeTruthy();
    expect(screen.queryByRole('group', { name: 'Confirm what happened' })).toBeNull();
    expect(lockedAll()).toBe(true);
    fireEvent.click(button('Send reminder'));
    expect(sent.filter((r) => r.method === 'POST')).toHaveLength(0);
  });
});

describe('edit makes a new version; Send follows it (AC 17)', () => {
  it('opens with Subject and Message from the step values; an empty Message sends nothing and is told; a save sends one edit_draft; Send then carries revision 2', async () => {
    await open(item('W-3801'), item('W-3801.next.edit_draft'), item('W-3801.next.send_reminder'));
    fireEvent.click(button('Edit'));
    const form = within(await screen.findByRole('form', { name: 'Edit' }));
    const subject = form.getByRole('textbox', { name: /Subject/ }) as HTMLInputElement;
    const message = form.getByRole('textbox', { name: /Message/ }) as HTMLTextAreaElement;
    expect(subject.value).toBe('Reminder: invoice INV-0391 is 21 days overdue');
    expect(message.value.split('\n\n')).toHaveLength(4);
    expect(message.value.startsWith('Dear Harmattan Bank Finance team,')).toBe(true);
    // UX-2-3: the submit button carries the step's returned submit label
    expect(form.queryByRole('button', { name: 'Edit' })).toBeNull();
    expect(form.getByRole('button', { name: 'Save draft' })).toBeTruthy();

    fireEvent.change(message, { target: { value: '' } });
    fireEvent.click(form.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(message.getAttribute('aria-invalid')).toBe('true'));
    await waitFor(() => expect(document.activeElement).toBe(message));
    const describedBy = message.getAttribute('aria-describedby')!.split(' ').map((id) => document.getElementById(id)?.textContent ?? '');
    expect(describedBy.join(' ')).toMatch(/\S/);
    expect(posts()).toHaveLength(0);

    fireEvent.change(message, { target: { value: 'Dear team,\n\nPlease pay INV-0391.' } });
    fireEvent.change(subject, { target: { value: 'Reminder: INV-0391' } });
    fireEvent.click(form.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(ws().getByText('Draft v2')).toBeTruthy());
    expect(posts()).toHaveLength(1);
    expect(posts()[0].body).toMatchObject({ expected_revision: 1, step: 'edit_draft', inputs: { subject: 'Reminder: INV-0391', message: 'Dear team,\n\nPlease pay INV-0391.' } });
    expect(validStepBody(posts()[0].body)).toBe(true);

    fireEvent.click(button('Send reminder'));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 2, step: 'send_reminder' });
    expect(posts()[1].body!.idempotency_key).not.toBe(posts()[0].body!.idempotency_key);
  });

  it('Cancel sends nothing and returns focus to Edit', async () => {
    await open(item('W-3801'));
    fireEvent.click(button('Edit'));
    const form = within(await screen.findByRole('form', { name: 'Edit' }));
    fireEvent.click(form.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('form', { name: 'Edit' })).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(button('Edit')));
    expect(posts()).toHaveLength(0);
  });

  it('W-3811: the 422 shows the message under Message with the text kept', async () => {
    stepAnswers = [json(422, { code: 'invalid', message: 'Check these fields: message.', fields: [{ name: 'message', message: 'The message must name the invoice reference.' }] })];
    await open(item('W-3811'));
    fireEvent.click(button('Edit'));
    const form = within(await screen.findByRole('form', { name: 'Edit' }));
    const message = form.getByRole('textbox', { name: /Message/ }) as HTMLTextAreaElement;
    fireEvent.change(message, { target: { value: 'Please pay.' } });
    fireEvent.click(form.getByRole('button', { name: 'Save draft' }));
    await screen.findByText('The message must name the invoice reference.');
    expect(message.value).toBe('Please pay.');
    expect(message.getAttribute('aria-invalid')).toBe('true');
    expect(posts()).toHaveLength(1);
  });
});

describe('stale and not now (AC 18, 19)', () => {
  it('W-3807: the 409 says it changed, shows Draft v2, sends nothing by itself; a new press sends with revision 2', async () => {
    stepAnswers = [json(409, { code: 'stale_revision', message: 'x' }), ok()];
    await open(item('W-3807'), item('W-3807.next'));
    fireEvent.click(button('Send reminder'));
    await screen.findByText('This changed while you were working. Showing version 2.');
    expect(ws().getByText('Draft v2')).toBeTruthy();
    expect(posts()).toHaveLength(1);
    expect(isOff(button('Send reminder'))).toBe(false);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(posts()).toHaveLength(1);
    fireEvent.click(button('Send reminder'));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].body).toMatchObject({ expected_revision: 2, step: 'send_reminder' });
  });

  it('Not now sends one set_aside; the re-read shows SET ASIDE and its sentence; no send', async () => {
    await open(item('W-3801'), item('W-3801.next.set_aside'));
    fireEvent.click(button('Not now'));
    await waitFor(() => expect(statusTag()).toBe('SET ASIDE'));
    expect(screen.getByText('Nothing was sent. The draft is kept.')).toBeTruthy();
    expect(posts()).toHaveLength(1);
    expect(posts()[0].body).toMatchObject({ step: 'set_aside', expected_revision: 1 });
    expect(posts().some((p) => p.body!.step === 'send_reminder')).toBe(false);
    expect(ws().queryByRole('button', { name: 'Send reminder' })).toBeNull();
  });
});

describe('controls only from the response (AC 20, 21)', () => {
  it('W-3808: Send is off with the returned reason and sends nothing; Edit and Not now stay; To reads Unknown', async () => {
    await open(item('W-3808'));
    expect(isOff(button('Send reminder'))).toBe(true);
    expect(ws().getByText('Harmattan Bank has no billing contact yet, so this can\'t be sent.')).toBeTruthy();
    expect(fact('To')).toBe('Unknown');
    fireEvent.click(button('Send reminder'));
    expect(posts()).toHaveLength(0);
    expect(isOff(button('Edit'))).toBe(false);
    expect(isOff(button('Not now'))).toBe(false);
  });

  it('W-3809: no Send, Edit or Not now', async () => {
    await open(item('W-3809'));
    for (const name of ['Send reminder', 'Edit', 'Not now']) expect(ws().queryByRole('button', { name })).toBeNull();
  });

  it.each(['finance_lead', 'ceo', 'pm'])('persona %s sees the same controls on W-3801 and W-3809 (no role rule in the page)', async (who) => {
    persona = who;
    const view = await open(item('W-3801'));
    expect(ws().getAllByRole('button').map((b) => b.textContent)).toEqual(['Send reminder', 'Edit', 'Not now']);
    view.unmount();
    await open(item('W-3809'));
    expect(ws().queryAllByRole('button')).toEqual([]);
  });

  it('401 on the read: signed out with next=/work/W-3801', async () => {
    itemAnswers = [() => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' })];
    render(
      <AppShell>
        <WorkItemView id="W-3801" tab="overview" />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain(`next=${encodeURIComponent('/work/W-3801')}`);
  });

  it.each([403, 404])('%s on the read: the not-open view with no title, client, amount or recipient', async (status) => {
    itemAnswers = [() => json(status, { code: 'x', message: 'Harmattan Bank' })];
    render(
      <AppShell>
        <WorkItemView id="W-3801" tab="overview" />
      </AppShell>,
    );
    await screen.findByRole('heading', { level: 1, name: 'You can’t open this work item' });
    for (const s of ['Harmattan', 'INV-0391', '₦', 'finance@']) expect(document.body.textContent).not.toContain(s);
  });

  it('a 401 on the send goes to signed out without a second write', async () => {
    stepAnswers = [json(401, { code: 'not_signed_in', message: 'Sign in to continue.' })];
    await open(item('W-3801'));
    fireEvent.click(button('Send reminder'));
    await screen.findByRole('link', { name: 'Sign in' });
    expect(posts()).toHaveLength(1);
  });
});
