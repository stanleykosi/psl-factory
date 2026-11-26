// @vitest-environment jsdom
// F-116: the archive page on the live work item against the live-shaped mock (mock/archive-live.mjs): what is read, the start, the file
// checks and each safety rule: one request per press, no automatic retry, a lost answer locks, the result from the re-read, no client rule
// about who may act, the source list chosen from the served one, unknown stays unknown.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { ARCHIVE_PATH, archiveLive, resetArchiveLive } from '../mock/archive-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/5303', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let gate: Promise<void> | null = null;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const reads = (path: RegExp) => fetchStub.mock.calls.filter(([r]) => r.method === 'GET' && path.test(new URL(r.url).pathname));
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetArchiveLive();
  scenario = undefined;
  gate = null;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const args = { method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes };
    if (!ARCHIVE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = archiveLive(args) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /Archive index|Start the archive|Nothing is waiting/) => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const BANNED = /mark (each|found)|never purge|no approval|Ask Tola|step 3 of 4/i;

describe('reading', () => {
  it('5302 working: the count from the job states, Copying rows, no Start, no banned board text', async () => {
    await open(5302);
    expect(screen.getByText('Archiving in progress. 28 of 42 files copied.')).toBeTruthy();
    expect(screen.getAllByText(/Copying/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Start archive' })).toBeNull();
    expect(document.body.textContent).not.toMatch(BANNED);
    expect(posts()).toHaveLength(0);
  });
  it('5301 verified: the sentence, every group Archived, the next block, no Start control and no placeholder', async () => {
    await open(5301);
    expect(screen.getByText('Archived and verified: 42 files, each matched in the archive index.')).toBeTruthy();
    expect(screen.getByText('Handover can start now that the archive is verified.')).toBeTruthy();
    expect(screen.getByText('Store: archive-store')).toBeTruthy();
    expect(screen.queryByText(/Start the archive|Start archive/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Look up|Copy again/ })).toBeNull();
  });
  it('5308 every file confirmed but not verified: no verified sentence and no next block', async () => {
    await open(5308);
    expect(document.body.textContent).not.toMatch(/Archived and verified|Handover can start/);
    expect(screen.getAllByText('Every file is copied. The archive index has not been matched yet.').length).toBeGreaterThan(0);
  });
  it('5304 ready: three sources, two checked, one not; unchecking all holds Start with its reason', async () => {
    await open(5304);
    const box = (name: string) => screen.getByRole('checkbox', { name }) as HTMLInputElement;
    expect(screen.getByText('Review the list, then start the archive.')).toBeTruthy();
    expect([box('RFP response').checked, box('Costing and SOW').checked, box('Planning').checked]).toEqual([true, true, false]);
    expect(screen.queryByText('Nothing is waiting to be archived.')).toBeNull();
    fireEvent.click(box('RFP response'));
    fireEvent.click(box('Costing and SOW'));
    expect(button('Start archive').disabled).toBe(true);
    expect(screen.getByText('Choose at least one source.')).toBeTruthy();
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });
  it('5305 and a missing id read "This record is unavailable."', async () => {
    await open(5305, 'This record is unavailable.');
    cleanup();
    await open(5399, 'This record is unavailable.');
  });
  it('5306 held: two files on hold, the copy limit, and no button on a held row', async () => {
    await open(5306);
    expect(screen.getByText(/2 files are on hold\./)).toBeTruthy();
    expect(screen.getByText('Copy limit reached')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Look up|Copy again/ })).toBeNull();
  });
});

describe('start (5304)', () => {
  it('one press is one POST with the checked ids and the read’s tokens; Queued, then the re-read says the state', async () => {
    await open(5304);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Planning' }));
    const start = button('Start archive');
    fireEvent.click(start);
    fireEvent.click(start);
    await screen.findByText(/Queued\./);
    expect(await sent()).toEqual([{ path: '/api/v1/work/5304/archive-files', body: { source_ids: [11, 12, 13], expected_revision: 7, case_revision: 41 } }]);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Start archive' })).toBeNull());
    expect(screen.getByText('Archiving in progress. 0 of 3 files copied.')).toBeTruthy();
  });
  it('the button is held while the write runs', async () => {
    let release: () => void = () => undefined;
    gate = new Promise<void>((resolve) => (release = resolve));
    await open(5304);
    fireEvent.click(button('Start archive'));
    await waitFor(() => expect(button(/Working/).disabled).toBe(true));
    release();
    await screen.findByText(/Queued\./);
    expect(posts()).toHaveLength(1);
  });
  it('409: the lasting words, a re-read, and no second POST', async () => {
    scenario = 'w409';
    await open(5304);
    const before = reads(/\/work\/5304\/archive-files$/).length;
    fireEvent.click(button('Start archive'));
    await screen.findByText(/This changed while you were working/);
    expect(posts()).toHaveLength(1);
    await waitFor(() => expect(reads(/\/work\/5304\/archive-files$/).length).toBeGreaterThan(before));
    expect(posts()).toHaveLength(1);
  });
  it('422 shows the message and the first field message; 403 csrf says press again; 429 and 503 say try again shortly; no second POST', async () => {
    for (const [name, words] of [['w422', /The request was not accepted\./], ['w403csrf', /Press the button again\./], ['w429', /Try again shortly\./], ['w503', /Try again shortly\./]] as const) {
      cleanup();
      fetchStub.mockClear();
      resetArchiveLive();
      resetScopedWriteLocks();
      scenario = name;
      await open(5304);
      fireEvent.click(button('Start archive'));
      await screen.findByText(words);
      if (name === 'w422') expect(screen.getByText(/Choose at least one source\./)).toBeTruthy();
      expect(posts()).toHaveLength(1);
    }
  });
  it('a lost answer: the words, a lock on every archive control, and no second POST until the page is re-read at a new version', async () => {
    scenario = 'wdrop';
    await open(5304);
    fireEvent.click(button('Start archive'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(posts()).toHaveLength(1);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Start archive' })).toBeNull());
  });
  it('a lost answer when nothing ran leaves the Start locked at the same version', async () => {
    scenario = 'wdrop0';
    await open(5304);
    fireEvent.click(button('Start archive'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    await waitFor(() => expect(button('Start archive').disabled).toBe(true));
    fireEvent.click(button('Start archive'));
    expect(posts()).toHaveLength(1);
  });
});

describe('checks (5303)', () => {
  it('six files the store did not confirm: the sentence, the group state, six Look up buttons and no Copy again', async () => {
    await open(5303);
    expect(screen.getByText(/The archive store didn’t confirm 6 of 42 files\./)).toBeTruthy();
    expect(screen.getByText('Look each file up first. Only files the archive confirms missing can be copied again.')).toBeTruthy();
    expect(screen.getByText('Not confirmed · 6')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Look up' })).toHaveLength(6);
    expect(screen.queryByRole('button', { name: 'Copy again' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Check what happened' })).toBeTruthy();
  });
  it('Look up posts that row’s revision and action to that row’s job; Copy again appears only on the re-read’s retry rows; one press, one POST', async () => {
    await open(5303);
    fireEvent.click(screen.getAllByRole('button', { name: 'Look up' })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: 'Look up' })[0]);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Look up' })).toHaveLength(5));
    expect(await sent()).toEqual([{ path: '/api/v1/work/5303/archive-files/620300/recovery', body: { revision: 1, action: 'lookup' } }]);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Copy again' })).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: 'Copy again' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Copy again' })).toBeNull());
    expect((await sent()).map((s) => s.body)).toEqual([{ revision: 1, action: 'lookup' }, { revision: 2, action: 'retry' }]);
  });
  it('a lookup whose answer is lost locks every row; nothing is sent again and no Copy again is guessed', async () => {
    scenario = 'wdrop0';
    await open(5303);
    fireEvent.click(screen.getAllByRole('button', { name: 'Look up' })[0]);
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    for (const b of screen.getAllByRole('button', { name: 'Look up' })) {
      expect((b as HTMLButtonElement).disabled).toBe(true);
      fireEvent.click(b);
    }
    expect(posts()).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Copy again' })).toBeNull();
  });
  it('409 on a recovery refreshes with no repeat; Check what happened sends the action and the version only', async () => {
    scenario = 'w409';
    await open(5303);
    fireEvent.click(screen.getAllByRole('button', { name: 'Look up' })[0]);
    await screen.findByText(/This changed while you were working/);
    expect(posts()).toHaveLength(1);
    scenario = undefined;
    fireEvent.click(button('Check what happened'));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect((await sent())[1]).toEqual({ path: '/api/v1/work/5303/actions', body: { expected_revision: 7, action: 'reconcile' } });
  });
});

describe('unknown is not zero (5307)', () => {
  it('a work read with no revision sends nothing: Start is held and no POST happens', async () => {
    await open(5307);
    expect(document.body.textContent).not.toMatch(/\bnull\b|undefined|NaN/);
    expect(screen.queryByRole('button', { name: 'Start archive' })).toBeNull();
    expect(posts()).toHaveLength(0);
  });
});
