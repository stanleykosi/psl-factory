// @vitest-environment jsdom
// F-117: the handover page on the live work item against the live-shaped mock (mock/handover-live.mjs): what is read, Publish, Record
// Support's reply, Support's own acknowledgement, and each safety rule: one request per press, no automatic retry, a lost answer locks,
// the result from the re-read, no client rule about who may act, choices from served lists, unknown stays Unknown.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { HANDOVER_PATH, handoverLive, resetHandoverLive } from '../mock/handover-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/6101', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let gate: Promise<void> | null = null;
const calls = () => fetchStub.mock.calls.map(([r]) => ({ method: r.method, path: new URL(r.url).pathname }));
const WRITES = /\/work\/\d+\/(support-publication|support-replies|support-receipt|actions)$/;
const writes = (path: RegExp = WRITES) => fetchStub.mock.calls.filter(([r]) => r.method === 'POST' && path.test(new URL(r.url).pathname));
const sent = async () => Promise.all(writes().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetHandoverLive();
  scenario = undefined;
  gate = null;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const args = { method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes };
    if (!HANDOVER_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = handoverLive(args) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /Waiting to be published|Queued for Support|Not recorded|Support found|Support received it/) => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const choose = (label: string | RegExp, option: RegExp) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: option }));
};
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const fill = (status: 'Received' | 'Gaps found' = 'Received') => {
  type('Who replied', 'Femi Ojo');
  choose('How they replied', /^Email$/);
  type('When they replied', '2026-11-25T11:00');
  fireEvent.click(screen.getByRole('radio', { name: status }));
  if (status === 'Gaps found') type('Gaps', ' First gap \n\n  Second gap  \n');
  type(/^Note/, 'We read it');
  choose('Proof', /signature v1/);
};
const BODY = { expected_revision: 8, case_revision: 41, receipt_id: 8101, previous_id: null, status: 'received', evidence_id: 7301, note: 'We read it', party: 'Femi Ojo', channel: 'email', responded_at: new Date('2026-11-25T11:00').toISOString(), role: 'Support lead' };

describe('reading', () => {
  it('6101 opens with reads only: the state, the board\'s consequence line and Publish; 6104 has no Publish', async () => {
    await open(6101, 'Waiting to be published');
    expect(calls().filter((c) => c.method !== 'GET')).toEqual([]);
    expect(screen.getByText('Publishing sends it to Support. Then you record whether they received it or found gaps.')).toBeTruthy();
    expect(button('Publish to Support').disabled).toBe(false);
    cleanup();
    await open(6104, 'Support found 2 gaps');
    expect(screen.queryByRole('button', { name: 'Publish to Support' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Tola|Review needed|Open question for PSL|Replaced/);
  });
  it('6104 lists the two gaps as numbered rows tagged Open, and the reply row', async () => {
    await open(6104);
    expect(screen.getByText('Support listed 2 gaps on 25 Nov')).toBeTruthy();
    expect(screen.getByText('1. No contact for the credit bureau outage')).toBeTruthy();
    expect(screen.getAllByText('Open')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Ask Tola/ })).toBeNull();
  });
  it('6105 (received): no gaps list and no Open tag', async () => {
    await open(6105, 'Support received it');
    expect(screen.queryByText(/Support listed/)).toBeNull();
    expect(screen.queryByText('Open')).toBeNull();
  });
  it('6102 (queued) says Queued for Support, with no publish or record control', async () => {
    await open(6102, 'Queued for Support');
    expect(screen.queryByRole('button', { name: /Publish|Record reply/ })).toBeNull();
  });
  it('6106 (uncertain): the page\'s own Check what happened sends one reconcile and no publish is offered', async () => {
    await open(6106, /We couldn’t confirm whether Support got it/);
    expect(screen.queryByRole('button', { name: /Publish/ })).toBeNull();
    fireEvent.click(button('Check what happened'));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(await sent()).toEqual([{ path: '/api/v1/work/6106/actions', body: { expected_revision: 8, action: 'reconcile' } }]);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Check what happened' })).toBeNull());
  });
  it('6107 (the recipient): the document and the acknowledge form; no PM controls; the 403 reads do not break the page', async () => {
    await open(6107, 'Not recorded');
    expect(screen.getByText('Support handover · version 1')).toBeTruthy();
    expect(screen.getByText(/Where the runbook lives and who keeps it current\./)).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Support’s own acknowledgement' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Publish|Record reply/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/couldn’t load/);
  });
  it('6101 as the PM draws no document and no recipient view', async () => {
    await open(6101);
    expect(screen.queryByText(/Support handover · version/)).toBeNull();
    expect(screen.queryByText(/Support’s own acknowledgement/)).toBeNull();
  });
  it('6108 reads "This record is unavailable."', async () => {
    render(<ToastProvider><LiveWorkItemView id="6108" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
});

describe('publish', () => {
  it('sends one request with the version the read named, then says Queued from the re-read', async () => {
    await open(6101);
    fireEvent.click(button('Publish to Support'));
    await screen.findAllByText('Queued for Support');
    expect(await sent()).toEqual([{ path: '/api/v1/work/6101/support-publication', body: { expected_revision: 8, case_revision: 41, version_id: 9101 } }]);
    expect(screen.queryByRole('button', { name: 'Publish to Support' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/delivered/i);
  });
  it('a double click sends one request, and the button is off while the re-read runs', async () => {
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await open(6101);
    const b = button('Publish to Support');
    fireEvent.click(b);
    fireEvent.click(b);
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(screen.getAllByRole('button', { name: /Working/ }).every((x) => (x as HTMLButtonElement).disabled)).toBe(true);
    release();
    await screen.findAllByText('Queued for Support');
    expect(writes()).toHaveLength(1);
  });
  it('409 says the item changed and re-reads, with no second request', async () => {
    await open(6101);
    scenario = 'w409';
    fireEvent.click(button('Publish to Support'));
    await screen.findByText(/This changed while you were working/);
    expect(writes()).toHaveLength(1);
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
  it('422 shows the server\'s message and its first field message; 403 csrf asks for another press; 403 says so', async () => {
    await open(6101);
    scenario = 'w422';
    fireEvent.click(button('Publish to Support'));
    await screen.findByText(/The request was not accepted\./);
    scenario = 'w403csrf';
    fireEvent.click(button('Publish to Support'));
    await screen.findByText('Press the button again.');
    scenario = 'w403';
    fireEvent.click(button('Publish to Support'));
    await screen.findByText(/You can’t do this\./);
    expect(writes()).toHaveLength(3);
  });
  it('a lost answer says so, locks Publish and never sends again on its own', async () => {
    await open(6101);
    scenario = 'wdrop0';
    fireEvent.click(button('Publish to Support'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(button('Publish to Support').disabled).toBe(true);
    fireEvent.click(button('Publish to Support'));
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
});

describe('record Support\'s reply', () => {
  it('6101 and 6102 (can_record false) draw no form', async () => {
    await open(6101);
    expect(screen.queryByRole('region', { name: 'Record Support’s reply' })).toBeNull();
  });
  it('6103: the form has the board\'s fields, a fixed role and five channels in words; Record stays off until each field is filled', async () => {
    await open(6103);
    expect(screen.getByText('Recording as Support lead')).toBeTruthy();
    expect((screen.getByLabelText('Who replied') as HTMLInputElement).value).toBe('');
    fireEvent.click(screen.getByRole('combobox', { name: 'How they replied' }));
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Email', 'WhatsApp', 'Client portal', 'Signed document', 'Meeting']);
    fireEvent.click(screen.getAllByRole('option')[0]);
    expect(button('Record reply').disabled).toBe(true);
    fill();
    expect(button('Record reply').disabled).toBe(false);
    expect(screen.queryByLabelText('Gaps')).toBeNull();
  });
  it('sends the eleven keys once, with no gaps key for Received, then re-reads and closes the form', async () => {
    await open(6103);
    fill();
    fireEvent.click(button('Record reply'));
    await screen.findAllByText('Support received it');
    const [one, ...rest] = await sent();
    expect(rest).toEqual([]);
    expect(one.path).toBe('/api/v1/work/6103/support-replies');
    expect(one.body).toEqual(BODY);
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Record Support’s reply' })).toBeNull());
    expect(screen.getByRole('button', { name: 'Record another reply' })).toBeTruthy();
  });
  it('Gaps found sends the trimmed lines in order', async () => {
    await open(6103);
    fill('Gaps found');
    fireEvent.click(button('Record reply'));
    await screen.findAllByText('Support found 2 gaps');
    expect((await sent())[0].body).toMatchObject({ status: 'gaps', gaps: ['First gap', 'Second gap'] });
  });
  it('6105: two roles are chosen, never defaulted; the replacement names the record it replaces', async () => {
    await open(6105, 'Support received it');
    fill();
    expect(screen.getByRole('combobox', { name: 'Role' }).textContent).toMatch(/Choose your role/);
    expect(button('Record reply').disabled).toBe(true);
    choose('Role', /PMO Lead/);
    fireEvent.click(button('Record reply'));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body).toMatchObject({ previous_id: 9002, role: 'PMO Lead' });
  });
  it('a refusal keeps what was typed: 403 and 409, with one request each and no resend', async () => {
    await open(6103);
    fill();
    scenario = 'w403';
    fireEvent.click(button('Record reply'));
    await screen.findByText(/You can’t do this\./);
    expect((screen.getByLabelText('Who replied') as HTMLInputElement).value).toBe('Femi Ojo');
    scenario = 'w409';
    fireEvent.click(button('Record reply'));
    await screen.findByText(/This changed while you were working/);
    expect((screen.getByLabelText(/^Note/) as HTMLTextAreaElement).value).toBe('We read it');
    expect(writes()).toHaveLength(2);
  });
  it('a future time keeps Record off with its reason', async () => {
    await open(6103);
    fill();
    type('When they replied', '2999-01-01T10:00');
    expect(button('Record reply').disabled).toBe(true);
    expect(screen.getAllByText('The time they replied can’t be in the future.').length).toBeGreaterThan(0);
  });
  it('a double click sends one request', async () => {
    await open(6103);
    fill();
    const b = button('Record reply');
    fireEvent.click(b);
    fireEvent.click(b);
    await screen.findAllByText('Support received it');
    expect(writes()).toHaveLength(1);
  });
});

describe('Support\'s own acknowledgement', () => {
  it('6107 sends the receipt, a listed proof, status and note once; the result is the re-read\'s', async () => {
    await open(6107, 'Not recorded');
    fireEvent.click(screen.getByRole('radio', { name: 'Gaps found' }));
    type('Acknowledgement note', 'Two gaps');
    choose('Acknowledgement proof', /support_acknowledgement v1/);
    fireEvent.click(button('Acknowledge'));
    await screen.findByText('Acknowledged by Support: Gaps found');
    expect(await sent()).toEqual([{ path: '/api/v1/work/6107/support-receipt', body: { expected_revision: 8, case_revision: 41, receipt_id: 8101, evidence_id: 7401, status: 'gaps', note: 'Two gaps' } }]);
    expect(screen.queryByRole('region', { name: 'Support’s own acknowledgement' })).toBeNull();
  });
});
