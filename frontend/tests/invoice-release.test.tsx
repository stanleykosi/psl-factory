// @vitest-environment jsdom
// F-90: releasing an invoice from the live work item. A money action: one request per press, the server's offer alone decides
// whether the button exists, an unknown result locks it (also across a reload), and a null amount reads Unknown.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import type { LiveWorkItem } from '@/api/types';
import { adapterFor } from '@/features/workspace/adapter';
import { invoiceAdapter } from '@/features/workspace/invoiceAdapter';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';
import { workItemCommands } from '@/features/workspace/workItemCommands';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { needsPolling } from '@/features/work-item/live/model';
import { readMark, resetReleaseMarks } from '@/features/work-item/live/releaseMark';

// @ts-expect-error plain ESM module without type declarations
import { invoiceReleaseLive, invoiceReleaseLog, resetInvoiceRelease } from '../mock/invoice-release-live.mjs';
// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/work/4140',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
const reply = (method: string, url: URL, scenario: string | undefined, rawBytes?: Buffer) =>
  invoiceReleaseLive({ method, url, scenario, csrfOk: true, persona: 'finance_lead', rawBytes }) as [number | string, unknown];
const item = (id: number): LiveWorkItem => reply('get', new URL(`/api/v1/work/${id}`, 'http://m.local'), undefined)[1] as LiveWorkItem;

let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const releasePosts = () => invoiceReleaseLog().filter((l: { body: { action?: string } }) => l.body.action === 'release_invoice');
const sessionReads = () => fetchStub.mock.calls.filter(([r]) => new URL(r.url).pathname === '/api/v1/session').length;

beforeEach(() => {
  resetScopedWriteLocks();
  resetReleaseMarks();
  resetInvoiceRelease();
  scenario = undefined;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const method = request.method.toLowerCase();
    const answer = /^\/api\/v1\/(work\/414\d|projects\/[^/]+\/billing-invoices\/\d+)/.test(url.pathname) && !/\/work\/414\d\/(tracking|history)/.test(url.pathname)
      ? reply(method, url, scenario, rawBytes)
      : (workLive({ method, url, scenario, csrfOk: true, persona: 'finance_lead', rawBytes }) as [number | string, unknown]);
    if (answer[0] === 'drop') throw new TypeError('network down');
    return json(answer[0] as number, answer[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const open = (id: number) => render(<ToastProvider><LiveWorkItemView id={String(id)} tab="overview" /></ToastProvider>);
const releaseButton = () => screen.queryByRole('button', { name: /^Release invoice$|Working/ }) as HTMLButtonElement | null;
const findRelease = async () => (await screen.findByRole('button', { name: 'Release invoice' })) as HTMLButtonElement;
/** Press "Release invoice", then the dialog's confirm. */
async function confirm(id: number) {
  void id;
  fireEvent.click(await findRelease());
  const dialog = await screen.findByRole('alertdialog', { name: 'Release this invoice?' });
  await act(async () => {
    fireEvent.click(within(dialog).getByRole('button', { name: 'Release invoice' }));
  });
}
const noRetry = async (seconds = 60) => {
  const before = posts().length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(seconds * 1000);
  });
  expect(posts().length).toBe(before);
};

describe('the release descriptor (workItemCommands)', () => {
  it('is listed only by actions[]: id, label, url, exact body, no key, success 202', () => {
    const release = workItemCommands(item(4140)).find((c) => c.id === 'invoice.release')!;
    expect(release).toMatchObject({ label: 'Release invoice', url: '/api/v1/work/4140/actions', successStatuses: [202], idempotency: { field: null, value: null } });
    expect(release.body({})).toEqual({ action: 'release_invoice', expected_revision: 9 });
    // an input can neither add an amount nor a recipient nor change the action
    expect(release.body({ amount: '1', recipient: 'x', case_revision: 4, action: 'cancel' })).toMatchObject({ action: 'release_invoice', expected_revision: 9 });
    expect(Object.keys(release.body({})).sort()).toEqual(['action', 'expected_revision']);
  });

  it('a null revision stays null (never 0) and holds the command with the reason', () => {
    const release = workItemCommands(item(4142)).find((c) => c.id === 'invoice.release')!;
    expect(release.disabledReason).toBe('We don’t have this item’s current version yet. Reload and try again.');
    expect(release.body({}).expected_revision).toBeNull();
  });

  it('nothing but release_invoice in actions[] builds it: not the state, not available_control, not the words of a role', () => {
    const base = item(4143);
    expect(base.state).toBe('ready');
    expect(workItemCommands(base).map((c) => c.id)).toEqual([]);
    expect(workItemCommands({ ...base, state: 'ready', actions: [], available_control: ['resume'] } as LiveWorkItem).map((c) => c.id)).toEqual(['work.resume']);
    for (const state of ['ready', 'verified', 'action_needed', 'waiting'] as const) expect(workItemCommands({ ...item(4140), state } as LiveWorkItem).map((c) => c.id)).toContain('invoice.release');
    expect(workItemCommands({ ...item(4140), actions: [], owner: 'Finance Lead' } as LiveWorkItem).map((c) => c.id)).toEqual([]);
  });

  it('a fresh descriptor each time: nothing is shared between two builds', () => {
    const [a] = workItemCommands(item(4140));
    const [b] = workItemCommands(item(4140));
    expect(a).not.toBe(b);
  });
});

describe('when the button exists', () => {
  it('4140 draws it; 4143 draws no button, no controls row, no reason and no gap', async () => {
    open(4140);
    await findRelease();
    cleanup();
    open(4143);
    await screen.findByRole('heading', { level: 1 });
    expect(releaseButton()).toBeNull();
    expect(screen.queryByRole('group', { name: 'Controls' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/release/i);
    expect(posts()).toHaveLength(0);
  });

  it('nothing is sent by loading the page or by polling it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open(4140);
    await findRelease();
    await noRetry(60);
    expect(posts()).toHaveLength(0);
  });

  it('4142 (null revision) draws it disabled with the reason, sends nothing and has no dialog to open', async () => {
    open(4142);
    const button = await findRelease();
    expect(button.disabled).toBe(true);
    expect(screen.getByText('We don’t have this item’s current version yet. Reload and try again.')).toBeTruthy();
    fireEvent.click(button);
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(posts()).toHaveLength(0);
  });
});

describe('the confirmation and the one request', () => {
  it('pressing opens a plain yes/no dialog and sends nothing; Keep it closes it with no request', async () => {
    open(4140);
    fireEvent.click(await findRelease());
    const dialog = await screen.findByRole('alertdialog', { name: 'Release this invoice?' });
    expect(within(dialog).getByText('This sends the invoice onward and can’t be undone from here.')).toBeTruthy();
    expect(dialog.textContent).not.toMatch(/\d/);
    expect(posts()).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Keep it' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(posts()).toHaveLength(0);
    expect(readMark(4140)).toBeNull();
  });

  it('confirming sends exactly one POST with the two keys; the 202 is "requested", never "released", until the re-read says verified', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open(4140);
    await confirm(4140);
    expect(posts()).toHaveLength(1);
    expect(new URL(posts()[0][0].url).pathname).toBe('/api/v1/work/4140/actions');
    expect(releasePosts()).toEqual([{ route: 'actions', work_id: 4140, body: { action: 'release_invoice', expected_revision: 9 } }]);
    expect((await screen.findByText('Release requested. The invoice is being sent; this page will update.')).closest('[role="status"]')).not.toBeNull(); // the toast (D-151)
    await waitFor(() => expect(document.querySelector('.work-state')?.textContent).toBe('Processing'));
    expect(document.body.textContent).not.toMatch(/Released|\bSent\b/);
    expect(screen.getByRole('status').textContent).not.toMatch(/Released|Sent|Delivered/);
    // the button is gone while the server offers nothing; the page polls (reads only) until the server says verified
    expect(releaseButton()).toBeNull();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    await waitFor(() => expect(document.querySelector('.work-state')?.textContent).toBe('Verified'));
    expect(posts()).toHaveLength(1);
    // the invoice block is read again after the revision moved: issued and delivered are now filled, paid is the server's 0.00
    await waitFor(() => expect(screen.queryByText('Not issued yet')).toBeNull());
    expect(screen.queryByText('No delivery recorded')).toBeNull();
    expect(screen.getByText('NGN 0.00')).toBeTruthy();
  });

  it('a double click on the confirm button sends one request, and a second press while it runs sends nothing', async () => {
    let release: (r: Response) => void = () => undefined;
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? new Promise<Response>((resolve) => (release = resolve)) : base(request)));
    open(4140);
    fireEvent.click(await findRelease());
    const confirmButton = within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Release invoice' });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);
    await waitFor(() => expect(posts()).toHaveLength(1));
    // while it runs every control in the row is disabled and the pressed button says Working
    const row = screen.getByRole('group', { name: 'Controls' });
    for (const b of within(row).getAllByRole('button')) expect((b as HTMLButtonElement).disabled || b.getAttribute('aria-busy') === 'true').toBe(true);
    expect(posts()).toHaveLength(1);
    await act(async () => {
      release(json(202, { work_id: 4140, state: 'processing', revision: 10 }));
    });
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    expect(posts()).toHaveLength(1);
  });

  it('a poll landing mid-write does not clear the lock or open a second send', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let release: (r: Response) => void = () => undefined;
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? new Promise<Response>((resolve) => (release = resolve)) : base(request)));
    open(4140);
    await confirm(4140);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(posts()).toHaveLength(1);
    expect(readMark(4140)).toMatchObject({ revision: 9, kind: 'uncertain' });
    await act(async () => {
      release(json(202, { work_id: 4140, state: 'processing', revision: 10 }));
    });
    expect(posts()).toHaveLength(1);
  });
});

describe('after a 202 the server has not caught up (4141)', () => {
  it('stays disabled with "Waiting for the server" and sends no second POST over 60 s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open(4141);
    await confirm(4141);
    await screen.findByText('Release requested. Waiting for the server.');
    expect((await findRelease()).disabled).toBe(true);
    await noRetry(60);
    expect(releasePosts()).toHaveLength(1);
    expect(readMark(4141)).toMatchObject({ revision: 9, kind: 'requested' });
    // the page keeps reading while it waits
    expect(fetchStub.mock.calls.filter(([r]) => r.method === 'GET' && new URL(r.url).pathname === '/api/v1/work/4141').length).toBeGreaterThan(3);
  });

  it('a reload keeps it locked: the new page is disabled and there is nothing to confirm', async () => {
    open(4141);
    await confirm(4141);
    await screen.findByText('Release requested. Waiting for the server.');
    cleanup();
    resetScopedWriteLocks(); // a full page load forgets the in-memory locks; the browser's mark stays
    open(4141);
    const button = await findRelease();
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(releasePosts()).toHaveLength(1);
  });
});

describe('an unknown result locks the release and nothing sends it again', () => {
  it.each([
    ['a dropped connection', 'wdrop'],
    ['a 500', 'w500'],
    ['a 503 that is not read_limited', 'w503'],
  ])('%s: the words, a disabled button with its reason, no retry button, no request over 60 s', async (_name, name) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    scenario = name;
    open(4140);
    await confirm(4140);
    if (name !== 'w503') expect(await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.')).toBeTruthy();
    const button = await findRelease();
    expect(button.disabled).toBe(true);
    expect(screen.getByText('Check the page before trying again.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /try again|retry/i })).toBeNull();
    await noRetry(60);
    expect(releasePosts()).toHaveLength(1);
    fireEvent.click(button);
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(releasePosts()).toHaveLength(1);
  });

  it('a reload keeps it locked while the server still offers it at the same revision', async () => {
    scenario = 'wdrop';
    open(4140);
    await confirm(4140);
    await screen.findByText('Check the page before trying again.');
    cleanup();
    resetScopedWriteLocks();
    scenario = undefined;
    open(4140);
    const button = await findRelease();
    expect(button.disabled).toBe(true);
    expect(screen.getByText('Check the page before trying again.')).toBeTruthy();
    expect(readMark(4140)).toMatchObject({ revision: 9, kind: 'uncertain' });
    expect(releasePosts()).toHaveLength(1);
  });

  it('a mark left by a page that closed mid-send holds the release too (written before the request)', async () => {
    window.localStorage.setItem('psl.release-invoice.4140', JSON.stringify({ revision: 9, kind: 'uncertain' }));
    open(4140);
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(true);
    // an unreadable mark holds as well
    cleanup();
    window.localStorage.setItem('psl.release-invoice.4140', 'not json');
    open(4140);
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(true);
    expect(posts()).toHaveLength(0);
  });

  it('it unlocks when a re-read shows a different revision, or no longer lists the action, and then the mark is gone', async () => {
    window.localStorage.setItem('psl.release-invoice.4140', JSON.stringify({ revision: 8, kind: 'uncertain' }));
    open(4140);
    // the mark is for revision 8; the item is at 9
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(false);
    await waitFor(() => expect(readMark(4140)).toBeNull());
    cleanup();
    window.localStorage.setItem('psl.release-invoice.4143', JSON.stringify({ revision: 9, kind: 'uncertain' }));
    open(4143);
    await screen.findByRole('heading', { level: 1 });
    expect(releaseButton()).toBeNull();
    await waitFor(() => expect(readMark(4143)).toBeNull());
  });

  it('on 4144 "Check what happened" stays available and sends a reconcile, never a release; the revision it moves unlocks the release', async () => {
    scenario = 'w500';
    open(4144);
    await confirm(4144);
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    scenario = undefined;
    const check = (await screen.findByRole('button', { name: 'Check what happened' })) as HTMLButtonElement;
    expect(check.disabled).toBe(false);
    fireEvent.click(check);
    await waitFor(() => expect(invoiceReleaseLog()).toHaveLength(2));
    expect(invoiceReleaseLog()[1]).toEqual({ route: 'actions', work_id: 4144, body: { action: 'reconcile', expected_revision: 9 } });
    await waitFor(() => expect(readMark(4144)).toBeNull());
    expect(releasePosts()).toHaveLength(1);
  });
});

describe('answers that say it did not happen', () => {
  it('403 forbidden: "You can’t do this." plus the server’s words, one POST, the press is not repeated', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    scenario = 'w403';
    open(4140);
    await confirm(4140);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('You can’t do this.');
    expect(alert.textContent).toContain('Your role does not allow releasing this invoice.');
    await noRetry(30);
    expect(releasePosts()).toHaveLength(1);
    expect(readMark(4140)).toBeNull();
  });

  it('403 csrf_failed: one session refresh, "Press the button again.", no second POST, and the button is pressable again', async () => {
    scenario = 'w403csrf';
    open(4140);
    await confirm(4140);
    expect((await screen.findByRole('alert')).textContent).toContain('Press the button again.');
    expect(sessionReads()).toBe(1);
    expect(posts()).toHaveLength(1);
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(false);
  });

  it('409 stale_version: re-reads, says it changed, the button is gone because the re-read no longer lists it', async () => {
    scenario = 'w409';
    open(4140);
    await confirm(4140);
    expect((await screen.findByRole('alert')).textContent).toContain('This changed while you were working. Showing the latest version.');
    await waitFor(() => expect(releaseButton()).toBeNull());
    expect(releasePosts()).toHaveLength(1);
  });

  it('422 setup_required: the server’s message and the first field message as given', async () => {
    scenario = 'w422';
    open(4140);
    await confirm(4140);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('A release setting is missing.');
    expect(alert.textContent).toContain('Ask the Finance Lead to set it.');
    expect(releasePosts()).toHaveLength(1);
  });

  it.each(['w429'])('%s says try again shortly and sends nothing by itself over 30 s', async (name) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    scenario = name;
    open(4140);
    await confirm(4140);
    expect((await screen.findByRole('alert')).textContent).toContain('Try again shortly.');
    await noRetry(30);
    expect(releasePosts()).toHaveLength(1);
  });

  it('read_limited (503 read_limited) says try again shortly and does not lock', async () => {
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? json(503, { code: 'read_limited', message: 'Busy.' }) : base(request)));
    open(4140);
    await confirm(4140);
    expect((await screen.findByRole('alert')).textContent).toContain('Try again shortly.');
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(false);
  });

  it('a 404 on the write replaces the page with "This record is unavailable."', async () => {
    scenario = 'w404';
    open(4140);
    await confirm(4140);
    expect(await screen.findByText('This record is unavailable.')).toBeTruthy();
    expect(releasePosts()).toHaveLength(1);
  });

  it('a 401 on the write shows the signed-out state with a sign-in link back to this page', async () => {
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'POST' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : base(request)));
    open(4140);
    await confirm(4140);
    const link = (await screen.findByRole('link', { name: /sign in/i })) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toContain('/sign-in?next=');
    expect(posts()).toHaveLength(1);
  });
});

describe('a re-read that fails after the send', () => {
  it('says so, keeps the release held and sends nothing more', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    open(4140);
    await findRelease();
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (request.method === 'GET' && new URL(request.url).pathname === '/api/v1/work/4140' ? json(500, { code: 'server_error', message: 'x' }) : base(request)));
    await confirm(4140);
    expect(await screen.findByText('Sent. We couldn’t reload the item; reload the page to see its state.')).toBeTruthy();
    expect(readMark(4140)).toMatchObject({ kind: 'requested' });
    await noRetry(60);
    expect(releasePosts()).toHaveLength(1);
  });
});

describe('polling', () => {
  it('a held release polls even when the item is not processing, and nothing else makes it', () => {
    window.localStorage.setItem('psl.release-invoice.4141', JSON.stringify({ revision: 9, kind: 'requested' }));
    expect(needsPolling(item(4141))).toBe(true);
    expect(needsPolling(item(4140))).toBe(false);
  });
});

describe('the invoice block', () => {
  it('shows each value as served; null paid and owed read Unknown, never 0; no links or controls', async () => {
    open(4143);
    const panel = (await screen.findByRole('heading', { name: 'Invoice' })).closest('section')!;
    const text = panel.textContent ?? '';
    expect(text).toContain('INV-0415');
    expect(text).toContain('v2');
    expect(text).toContain('NGN 1250000.00');
    expect(within(panel).getByText('Not issued yet')).toBeTruthy();
    expect(within(panel).getByText('No delivery recorded')).toBeTruthy();
    expect(within(panel).getAllByText('Unknown')).toHaveLength(2);
    expect(text).not.toMatch(/\b0\.00\b/);
    expect(within(panel).queryAllByRole('link')).toHaveLength(0);
    expect(within(panel).queryAllByRole('button')).toHaveLength(0);
  });

  it('the reference of 4140 is INV-0412 and the amount is the server’s string', async () => {
    open(4140);
    const panel = (await screen.findByRole('heading', { name: 'Invoice' })).closest('section')!;
    expect(panel.textContent).toContain('INV-0412');
    expect(panel.textContent).toContain('NGN 1250000.00');
  });

  it('an invoice read that answers 404 omits the block and leaves the release control working', async () => {
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (request: Request) => (new URL(request.url).pathname.includes('/billing-invoices/') ? json(404, { code: 'not_found', message: 'No.' }) : base(request)));
    open(4140);
    expect(((await findRelease()) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByRole('heading', { name: 'Invoice' })).toBeNull();
    expect(screen.queryByText(/couldn’t load this part/)).toBeNull();
  });
});

describe('invoiceAdapter', () => {
  it('is registered for the invoice key', () => {
    expect(adapterFor('invoice')).toBe(invoiceAdapter);
  });

  it.each([
    '/api/v1/projects/C-1/billing-invoices/abc',
    '/api/v1/projects/C-1/billing-invoices/812/extra',
    '/api/v1/projects/C-1/billing-invoices/812?x=1',
    '/api/v1/projects/../billing-invoices/812',
    '/api/v1/projects//billing-invoices/812',
    '//evil.example/api/v1/projects/C-1/billing-invoices/812',
    'https://evil.example/api/v1/projects/C-1/billing-invoices/812',
    '/api/v1/work/4140/weekly-report',
    '/api/v1/projects/C-1/billing-invoices/812%2F..%2Fx',
  ])('does not fetch %s and omits the block', async (url) => {
    expect(await invoiceAdapter.read({ key: 'invoice', url })).toBeNull();
    expect(invoiceAdapter.sections(null, { workId: 1, caseId: 'C', revision: 1, caseRevision: null })).toEqual([]);
    expect(fetchStub).not.toHaveBeenCalled();
  });

  it('a 403 or 404 omits it; any other failure is thrown so the page offers Try again', async () => {
    const url = `/api/v1/projects/00000000-0000-4000-8000-000000004140/billing-invoices/812`;
    const base = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async () => json(403, { code: 'forbidden', message: 'No.' }));
    expect(await invoiceAdapter.read({ key: 'invoice', url })).toBeNull();
    fetchStub.mockImplementation(async () => json(429, { code: 'rate_limited', message: 'Slow.' }));
    await expect(invoiceAdapter.read({ key: 'invoice', url })).rejects.toMatchObject({ kind: 'rate_limited' });
    fetchStub.mockImplementation(base);
    const readback = await invoiceAdapter.read({ key: 'invoice', url });
    expect(readback).toMatchObject({ id: 812, reference: 'INV-0412' });
  });
});

describe('the mock keeps the contract’s shapes', () => {
  const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, { responses: Record<string, { content?: { 'application/json': { schema: object } } }> }>> };
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  const validator = (path: string, method: string, status: string) => ajv.compile(contract.paths[path][method].responses[status].content!['application/json'].schema);

  it.each([4140, 4141, 4142, 4143, 4144])('work %i and its invoice are valid answers', (id) => {
    const work = validator('/api/v1/work/{work_id}', 'get', '200');
    expect(work(item(id)), JSON.stringify(work.errors)).toBe(true);
    const invoice = validator('/api/v1/projects/{case_id}/billing-invoices/{invoice_id}', 'get', '200');
    const [status, body] = reply('get', new URL(`/api/v1/projects/00000000-0000-4000-8000-00000000${id}/billing-invoices/${812 + id - 4140}`, 'http://m.local'), undefined);
    expect(status).toBe(200);
    expect(invoice(body), JSON.stringify(invoice.errors)).toBe(true);
  });

  it('the release answers a valid 202 and a body that is not the exact two keys is refused', () => {
    const valid = validator('/api/v1/work/{work_id}/actions', 'post', '202');
    const url = new URL('/api/v1/work/4140/actions', 'http://m.local');
    const [code, answer] = reply('post', url, undefined, Buffer.from(JSON.stringify({ action: 'release_invoice', expected_revision: 9 })));
    expect(code).toBe(202);
    expect(valid(answer), JSON.stringify(valid.errors)).toBe(true);
    for (const bad of [{ action: 'release_invoice' }, { action: 'release_invoice', expected_revision: 0 }, { action: 'release_invoice', expected_revision: null }, { action: 'release_invoice', expected_revision: 9, amount: '1' }]) {
      expect(reply('post', url, undefined, Buffer.from(JSON.stringify(bad)))[0]).toBe(400);
    }
  });
});
