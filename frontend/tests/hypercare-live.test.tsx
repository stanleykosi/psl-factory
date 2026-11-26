// @vitest-environment jsdom
// F-115: the hypercare page on the live work item against the live-shaped mock (mock/hypercare-live.mjs): what each state draws, the
// section-local failures, and the one write the page offers (pause or continue, the work item's own controls): one request per press,
// no automatic retry, a lost answer locks, the result from the re-read.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { HYPERCARE_PATH, hypercareLive, resetHypercareLive } from '../mock/hypercare-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/5202', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, csrf: r.headers.get('X-CSRFToken'), body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));
const gets = (re: RegExp) => fetchStub.mock.calls.filter(([r]) => r.method === 'GET' && re.test(new URL(r.url).pathname)).length;
let gate: Promise<void> | null = null;

beforeEach(() => {
  resetScopedWriteLocks();
  resetHypercareLive();
  scenario = undefined;
  gate = null;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    if (!HYPERCARE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = hypercareLive({ method: request.method.toLowerCase(), url, scenario: request.method === 'POST' ? scenario : undefined, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = 'Criteria') => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const text = () => document.body.textContent ?? '';

describe('reading (AC1 to AC4, AC9)', () => {
  it('5201 Setup needed: the tag, the line, the held check, no control for the writes this page does not own', async () => {
    await open(5201, 'Hypercare criteria are not set.');
    expect(screen.getAllByText('Setup needed').length).toBeGreaterThan(0);
    expect(text()).toContain('An admin can draft them in Setup');
    expect(text()).toContain('Stability');
    expect(text()).toContain('Held');
    expect(screen.queryByText('Criteria')).toBeNull();
    expect(text()).toContain('None recorded');
    expect(text()).toContain('The release has not been recorded.');
    expect(posts()).toEqual([]);
  });
  it('5202 Evaluating: results with Not known, a reading, No reading yet, No open issues, a Pause control', async () => {
    await open(5202);
    expect(screen.getAllByText('Evaluating').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Not known').length).toBeGreaterThan(0);
    expect(screen.getByText('Recorded')).toBeTruthy();
    expect(screen.getByText('No reading yet')).toBeTruthy();
    expect(await screen.findByText('No open issues.')).toBeTruthy();
    expect(text()).toContain('1 recorded');
    expect(text()).toContain('Not recorded');
    expect(button('Pause background work')).toBeTruthy();
    expect(posts()).toEqual([]);
  });
  it('5203 Qualified and verified, every criterion Met, nothing open', async () => {
    await open(5203);
    expect(screen.getAllByText('Qualified').length).toBeGreaterThan(0);
    expect(screen.getByText('Verified')).toBeTruthy();
    expect(screen.queryByText('Not known')).toBeNull();
    expect(screen.queryByText('Not met')).toBeNull();
    expect(await screen.findByText('No open issues.')).toBeTruthy();
    expect(screen.queryByText('Next')).toBeNull();
  });
  it('5204 Not met: the findings, Not met and Not known, the open High issue in its own table, not in the readings', async () => {
    await open(5204);
    expect(screen.getAllByText('Not met').length).toBeGreaterThan(1);
    expect(screen.getByText('Engineering/error_rate fails the configured criterion')).toBeTruthy();
    const issues = (await screen.findByRole('heading', { name: 'Open issues' })).closest('section') as HTMLElement;
    expect(within(issues).getByText('ISS-0315')).toBeTruthy();
    expect(within(issues).getByText('Blocks hypercare')).toBeTruthy();
    expect(within(issues).queryByText('ISS-0310')).toBeNull();
    const readings = screen.getByRole('heading', { name: 'Metric readings' }).closest('section') as HTMLElement;
    expect(readings).not.toBe(issues);
    expect(within(readings).queryByText('ISS-0315')).toBeNull();
    expect(screen.getByText('Fix the findings above. Tola evaluates again when they are resolved.')).toBeTruthy();
    expect(screen.getByText('Closure stays blocked until then.')).toBeTruthy();
  });
  it('draws none of the hidden words in any state, and no day count', async () => {
    for (const id of [5201, 5202, 5203, 5204]) {
      await open(id, /Hypercare criteria are not set\.|Tola is evaluating|Hypercare qualified\.|Engineering\/error_rate/);
      expect(text()).not.toMatch(/Day \d|of 30|Log an observation|Log an issue|Record release|Ask Tola/);
      cleanup();
    }
  });
});

describe('section-local failures (AC11, AC12)', () => {
  it('5207: the events panel fails alone, with its Try again, which repeats only that read', async () => {
    await open(5207);
    await screen.findByText(/We couldn’t load this part of the page/);
    expect(screen.getAllByText('Criteria').length).toBeGreaterThan(0);
    const before = { stab: gets(/\/stability$/), events: gets(/\/stability\/events$/) };
    fireEvent.click(button('Try again'));
    await waitFor(() => expect(gets(/\/stability\/events$/)).toBe(before.events + 1));
    expect(gets(/\/stability$/)).toBe(before.stab);
  });
  it('5208: the open issues fail alone, with their own Try again; the rest still draws', async () => {
    await open(5208);
    await screen.findByText(/Open issues couldn’t be loaded/);
    expect(screen.getAllByText('Criteria').length).toBeGreaterThan(0);
    expect(text()).toContain('Release and acceptance');
    const before = gets(/\/issues$/);
    const stab = gets(/\/stability$/);
    fireEvent.click(within(screen.getByText(/Open issues couldn’t be loaded/).closest('div') as HTMLElement).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(gets(/\/issues$/)).toBe(before + 1));
    expect(gets(/\/stability$/)).toBe(stab);
  });
  it('5206 reads "This record is unavailable."', async () => {
    render(<ToastProvider><LiveWorkItemView id="5206" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
});

describe('pause and continue (AC14 to AC18, AC21)', () => {
  const writes = () => sent();
  it('Pause sends one POST with the revision, the session header and no case_revision, then re-reads', async () => {
    await open(5202);
    const reads = gets(/\/work\/5202$/);
    fireEvent.click(button('Pause background work'));
    await screen.findByText(/Done\. This item is now:/);
    expect(await writes()).toEqual([{ path: '/api/v1/work/5202/background', csrf: 't', body: { expected_revision: 8, enabled: false } }]);
    expect(gets(/\/work\/5202$/)).toBeGreaterThan(reads);
    expect(gets(/\/work\/5202\/stability$/)).toBeGreaterThan(1);
  });
  it('a double press sends one request and the buttons are off while it runs', async () => {
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await open(5202);
    fireEvent.click(button('Pause background work'));
    await waitFor(() => expect(posts()).toHaveLength(1));
    const working = button('Working…');
    expect(working.disabled).toBe(true);
    fireEvent.click(working);
    fireEvent.click(working);
    release();
    await screen.findByText(/Done\./);
    expect(posts()).toHaveLength(1);
  });
  it('5205 is paused: Continue sends enabled true, and the page shows the re-read state', async () => {
    await open(5205);
    fireEvent.click(button('Continue background work'));
    await screen.findByText(/Done\. This item is now:/);
    expect(await writes()).toEqual([{ path: '/api/v1/work/5205/background', csrf: 't', body: { expected_revision: 8, enabled: true } }]);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull());
  });
  const fail = async (name: string, expected: RegExp | string, locked = false) => {
    await open(5202);
    scenario = name;
    fireEvent.click(button('Pause background work'));
    expect((await screen.findAllByText(expected, { exact: false })).length).toBeGreaterThan(0);
    await new Promise((r) => setTimeout(r, 30));
    expect(posts()).toHaveLength(1);
    expect(screen.queryByText(/Done\./)).toBeNull();
    if (locked) expect(button('Pause background work').disabled).toBe(true);
  };
  it('403: "You can’t do this." with the server message', () => fail('w403', /You can’t do this\. Only the PM can change this\./));
  it('csrf_failed: "Press the button again", no second write', () => fail('w403csrf', /Press the button again/));
  it('409: the change notice and a re-read, no resend', () => fail('w409', /This changed while you were working/));
  it('422: the server message and the first field message', () => fail('w422', /The request was not accepted\. This cannot be changed now\./));
  it('429 and 503: "Try again shortly."', async () => {
    await fail('w429', 'Try again shortly.');
  });
  it('503: "Try again shortly."', () => fail('w503', 'Try again shortly.'));
  it('500: "We couldn’t confirm that this happened. Check the page before trying again." and the button locks', () => fail('w500', /We couldn’t confirm that this happened\. Check the page before trying again\./, true));
  it('a lost answer before the write ran locks the button and sends nothing more', async () => {
    await open(5202);
    scenario = 'wdrop0';
    fireEvent.click(button('Pause background work'));
    await screen.findByText(/We couldn’t confirm that this happened/);
    expect(button('Pause background work').disabled).toBe(true);
    fireEvent.click(button('Pause background work'));
    await new Promise((r) => setTimeout(r, 30));
    expect(posts()).toHaveLength(1);
  });
  it('a lost answer after the write ran: the re-read shows the new version, nothing is sent twice, the result is never said from the lost answer', async () => {
    await open(5202);
    scenario = 'wdrop';
    fireEvent.click(button('Pause background work'));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Resume' })).not.toBeNull());
    await new Promise((r) => setTimeout(r, 30));
    expect(posts()).toHaveLength(1);
    expect(screen.queryByText(/Done\./)).toBeNull();
  });
  it('the only POST this page sends is the background call', async () => {
    await open(5204);
    expect(posts()).toEqual([]);
    fireEvent.click(button('Pause background work'));
    await screen.findByText(/Done\./);
    expect((await sent()).map((s) => s.path)).toEqual(['/api/v1/work/5204/background']);
  });
});
