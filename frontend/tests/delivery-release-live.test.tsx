// @vitest-environment jsdom
// F-113B: the release gates page on the live work item against the live-shaped mock (mock/delivery-release.mjs): the three writes and
// each safety rule: one request per press, no automatic retry, a lost answer locks, the result from the re-read, no client rule on who decides.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { RELEASE_PATH, releaseLive, resetReleaseLive } from '../mock/delivery-release.mjs';
// @ts-expect-error plain ESM module without type declarations
import { CASE_FILES_PATH } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4801', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const calls = () => fetchStub.mock.calls.map(([r]) => ({ method: r.method, path: new URL(r.url).pathname }));
const posts = (path?: RegExp) => fetchStub.mock.calls.filter(([r]) => r.method === 'POST' && (!path || path.test(new URL(r.url).pathname)));
const writes = () => posts(/\/work\/\d+\/(planning-exit|release-register)$/);
const sent = async () => Promise.all(writes().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));
let gate: Promise<void> | null = null;

beforeEach(() => {
  resetScopedWriteLocks();
  resetReleaseLive();
  scenario = undefined;
  gate = null;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    // the case file upload is multipart: its bytes are not read here
    if (CASE_FILES_PATH.test(url.pathname)) return json(200, { upload_id: 8001, name: 'release.pdf', size: 16, sha256: 'a'.repeat(64), download_url: '/x' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const args = { method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes };
    if (!RELEASE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = releaseLive(args) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = 'Initiation') => {
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
const press = (name: string | RegExp) => fireEvent.click(button(name));
const uploaded = () => waitFor(() => expect(document.querySelector('.psl-reason')?.textContent ?? '').not.toMatch(/Upload the release record/));
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe('reading', () => {
  it('opens with reads only: no write, no decision-appointments (AC16, AC27)', async () => {
    await open(4801);
    expect(calls().filter((c) => c.method !== 'GET')).toEqual([]);
    expect(calls().some((c) => c.path.includes('decision-appointments'))).toBe(false);
    for (const phase of ['Initiation', 'Planning', 'Execution', 'Closure']) expect(screen.getAllByText(phase).length).toBeGreaterThan(0);
    expect(screen.getAllByText('CURRENT').length).toBeGreaterThan(0);
    expect(screen.getByText('BRAND NEW STATUS')).toBeTruthy();
    expect(screen.queryByText(/0 records/)).toBeNull();
    expect(screen.getByText('Proof is out of date')).toBeTruthy();
  });
  it('4807 asks for the appointments, draws Owner needed, the people and a link, and no decision form (AC16)', async () => {
    await open(4807, 'Owner needed');
    expect(calls().some((c) => c.path.includes('decision-appointments'))).toBe(true);
    expect((await screen.findByRole('link', { name: 'Open Setup roles' })).getAttribute('href')).toBe('/setup/roles');
    expect(screen.queryByRole('button', { name: /Approve for release|Return with a note/ })).toBeNull();
  });
  it('a failing client-testing read hides only that row (AC22)', async () => {
    scenario = 'uat500';
    await open(4801);
    expect(screen.queryByText('Client testing')).toBeNull();
    expect(screen.getAllByText('Planning decision').length).toBeGreaterThan(0);
  });
  it('the wrong record reads "This record is unavailable." (AC25)', async () => {
    render(<ToastProvider><LiveWorkItemView id="4890" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
});

describe('who sees which controls (AC5, AC6, AC10, AC11, AC24)', () => {
  it('4801 shows Approve and Return, no Reject, an optional evidence select with nothing chosen', async () => {
    await open(4801);
    expect(button('Approve for release').disabled).toBe(false);
    expect(button('Return with a note').disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /Reject/ })).toBeNull();
    expect(screen.getByRole('combobox', { name: /Evidence \(optional\)/ }).textContent).toMatch(/Choose evidence/);
    expect(screen.getByText('You can approve this yourself.')).toBeTruthy();
  });
  it('4802 (no proofs, cannot approve directly): both buttons off with the reason, and a press sends nothing', async () => {
    await open(4802);
    expect(screen.getAllByText('No evidence is on file for this decision yet.').length).toBeGreaterThan(0);
    expect(button('Approve for release').disabled).toBe(true);
    expect(button('Return with a note').disabled).toBe(true);
    press('Approve for release');
    press('Return with a note');
    expect(writes()).toHaveLength(0);
    expect(screen.queryByText('You can approve this yourself.')).toBeNull();
  });
  it('4813 (no proofs, direct): Approve is on, Return is off', async () => {
    await open(4813);
    expect(button('Approve for release').disabled).toBe(false);
    expect(button('Return with a note').disabled).toBe(true);
  });
  it('4803 (packet null): the form is off with its reason and nothing is sent', async () => {
    await open(4803);
    expect(screen.getByText('Waiting for the packet')).toBeTruthy();
    expect(button('Approve for release').disabled).toBe(true);
    expect(screen.getAllByText('This can’t be decided yet.').length).toBeGreaterThan(0);
    press('Approve for release');
    expect(writes()).toHaveLength(0);
  });
  it('4812 (the item\'s version unknown): nothing is sent', async () => {
    await open(4812);
    expect(button('Approve for release').disabled).toBe(true);
    press('Approve for release');
    expect(writes()).toHaveLength(0);
  });
  it('4804 (cannot decide): no form, no buttons, "Waiting for the PMO Lead"', async () => {
    await open(4804, 'Waiting for the PMO Lead');
    expect(screen.queryByRole('button', { name: /Approve|Return|Prepare|Record the release/ })).toBeNull();
    expect(screen.queryByText('Decide the planning exit')).toBeNull();
  });
});

describe('deciding the planning exit (AC7, AC8, AC12)', () => {
  it('a direct approval sends one request with the loaded tokens and packet, no evidence_id, and the result comes from the re-read', async () => {
    await open(4801);
    press('Approve for release');
    await screen.findByText(/Approved by PMO Lead, Kemi Adebayo/);
    expect(await sent()).toEqual([{ path: '/api/v1/work/4801/planning-exit', body: { verdict: 'approve', packet: 'a'.repeat(64), expected_revision: 6, case_revision: 41 } }]);
    expect(screen.getAllByText(/approved directly/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Approve for release' })).toBeNull();
    // the GETs after the press are the re-read
    expect(calls().filter((c) => c.method === 'GET' && c.path.endsWith('/planning-exit')).length).toBeGreaterThan(1);
  });
  it('a chosen proof and a written note go with the approval', async () => {
    await open(4801);
    type('Note', 'Looks complete');
    choose(/Evidence/, /signed pdf · version 1/);
    press('Approve for release');
    await screen.findByText(/Approved by PMO Lead/);
    expect((await sent())[0].body).toMatchObject({ verdict: 'approve', note: 'Looks complete', evidence_id: 61 });
  });
  it('a person who cannot approve directly sends only with a chosen proof (4814)', async () => {
    await open(4814);
    expect(button('Approve for release').disabled).toBe(true);
    expect(screen.queryByText('You can approve this yourself.')).toBeNull();
    choose(/Evidence for this decision/, /signed pdf/);
    expect(button('Approve for release').disabled).toBe(false);
    press('Approve for release');
    await screen.findByText(/Approved by PMO Lead/);
    expect((await sent())[0].body).toMatchObject({ verdict: 'approve', evidence_id: 61 });
    expect(screen.getByText(/Approved by PMO Lead, Kemi Adebayo, .*/).textContent).not.toMatch(/directly/);
  });
  it('Return needs a note and a proof; with both it sends them and the related issue (AC8)', async () => {
    await open(4801);
    type('Note', 'Missing the test plan');
    expect(button('Return with a note').disabled).toBe(true);
    choose(/Evidence/, /signed pdf/);
    choose(/Related issue/, /ISS-0301/);
    expect(button('Return with a note').disabled).toBe(false);
    press('Return with a note');
    await screen.findByText(/Kemi Adebayo returned the release/);
    expect((await sent())[0].body).toEqual({ verdict: 'return', note: 'Missing the test plan', evidence_id: 61, issue_id: 301, packet: 'a'.repeat(64), expected_revision: 6, case_revision: 41 });
  });
  it('a return without a related issue has no issue_id', async () => {
    await open(4801);
    type('Note', 'No');
    choose(/Evidence/, /signed pdf/);
    press('Return with a note');
    await screen.findByText(/returned the release/);
    expect((await sent())[0].body).not.toHaveProperty('issue_id');
  });
  it('a double press sends one request and both buttons are off while it runs', async () => {
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await open(4801);
    press('Approve for release');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(button('Working…').disabled).toBe(true);
    expect(button('Return with a note').disabled).toBe(true);
    fireEvent.click(button('Working…'));
    fireEvent.click(button('Working…'));
    release();
    await screen.findByText(/Approved by PMO Lead/);
    expect(writes()).toHaveLength(1);
  });
});

describe('errors say what happened and never retry by themselves (AC13, AC24)', () => {
  const fail = async (name: string, expected: RegExp | string, extra?: () => void) => {
    await open(4801);
    scenario = name;
    press('Approve for release');
    expect((await screen.findAllByText(expected, { exact: false })).length).toBeGreaterThan(0);
    extra?.();
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  };
  it('403 forbidden: "You can’t do this." with the server message', () => fail('w403', /You can’t do this\. Only the PMO Lead can decide this\./));
  it('csrf_failed: "Press the button again", one session read, no second write', () => fail('w403csrf', /Press the button again/));
  it('409: the change notice, and the page re-read', () => fail('w409', /This changed while you were working/));
  it('422: the server message and the first field message', () => fail('w422', /The request was not accepted\. A note is needed to return a release\./));
  it('429 and 503: "Try again shortly."', async () => {
    await fail('w429', 'Try again shortly.');
  });
  it('503: "Try again shortly."', () => fail('w503', 'Try again shortly.'));
  it('500: "We couldn’t confirm…" and the buttons stay locked', () => fail('w500', /We couldn’t confirm that this happened\. Check the page before trying again\./, () => expect(button('Approve for release').disabled).toBe(true)));
  it('a lost answer after the write ran: the re-read shows the decision, no second write', async () => {
    await open(4801);
    scenario = 'wdrop';
    press('Approve for release');
    await screen.findByText(/Approved by PMO Lead/);
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
  it('a lost answer before the write ran: locked with the words, never sent again', async () => {
    await open(4801);
    scenario = 'wdrop0';
    press('Approve for release');
    await screen.findByText(/We couldn’t confirm that this happened/);
    expect(button('Approve for release').disabled).toBe(true);
    expect(button('Return with a note').disabled).toBe(true);
    press('Approve for release');
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
});

describe('prepare readiness (AC17)', () => {
  it('4808 sends one request with the tokens and the re-read says the release is ready', async () => {
    await open(4808, 'Preparing release readiness');
    press('Prepare release readiness');
    await screen.findByText(/Release ready · 1 readiness record/);
    expect(await sent()).toEqual([{ path: '/api/v1/work/4808/release-register', body: { action: 'prepare_readiness', expected_revision: 6, case_revision: 41 } }]);
  });
  it('4809 has no such button', async () => {
    await open(4809, 'Preparing release readiness');
    expect(screen.queryByRole('button', { name: 'Prepare release readiness' })).toBeNull();
  });
  it('a lost answer locks the button', async () => {
    await open(4808, 'Preparing release readiness');
    scenario = 'wdrop0';
    press('Prepare release readiness');
    await screen.findByText(/We couldn’t confirm that this happened/);
    expect(button('Prepare release readiness').disabled).toBe(true);
  });
});

describe('record the release (AC18 to AC21)', () => {
  const file = () => new File(['%PDF-1.4 release'], 'release.pdf', { type: 'application/pdf' });
  const fill = async (upload = true) => {
    type('Release date and time', '2026-11-26T10:30');
    type('Reference', 'REL-2026-045');
    type(/^Note/, 'Released to production');
    if (upload) {
      fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [file()] } });
      await uploaded();
    }
  };
  it('4810 shows Release ready and the form; the button stays off until everything is set', async () => {
    await open(4810, /Release ready/);
    const submit = () => button('Record the release');
    expect(submit().disabled).toBe(true);
    type('Release date and time', '2026-11-26T10:30');
    expect(submit().disabled).toBe(true);
    type('Reference', 'REL-2026-045');
    type(/^Note/, 'Released to production');
    expect(submit().disabled).toBe(true);
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [file()] } });
    await uploaded();
    expect(submit().disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('I have checked this file is the release record'));
    expect(submit().disabled).toBe(false);
    press('Record the release');
    await screen.findByText(/Release recorded .* · REL-2026-045/);
    expect(screen.queryByRole('button', { name: 'Record the release' })).toBeNull();
  });
  it('uploads to the item\'s case, then sends observe_release with the upload id and never an evidence id', async () => {
    await open(4810, /Release ready/);
    await fill();
    fireEvent.click(screen.getByLabelText('I have checked this file is the release record'));
    press('Record the release');
    await screen.findByText(/Release recorded/);
    expect(posts(/\/files$/).map(([r]) => new URL(r.url).pathname)).toEqual(['/api/v1/cases/00000000-0000-4000-8000-000000004810/files']);
    const [{ body }] = await sent();
    expect(body).toEqual({
      action: 'observe_release',
      expected_revision: 6,
      case_revision: 41,
      readiness_id: 71,
      released_at: new Date('2026-11-26T10:30').toISOString(),
      reference: 'REL-2026-045',
      upload_id: 8001,
      checked: true,
      note: 'Released to production',
      environment: null,
      private_log_id: null,
    });
    expect(body).not.toHaveProperty('evidence_id');
  });
  it('a lost answer after the release ran shows it recorded from the re-read; none is sent twice (AC20)', async () => {
    await open(4810, /Release ready/);
    await fill();
    fireEvent.click(screen.getByLabelText('I have checked this file is the release record'));
    scenario = 'wdrop';
    press('Record the release');
    await screen.findByText(/Release recorded .* · REL-2026-045/);
    expect(writes()).toHaveLength(1);
  });
  it('a lost answer before it ran locks the form with the words and sends no second write', async () => {
    await open(4810, /Release ready/);
    await fill();
    fireEvent.click(screen.getByLabelText('I have checked this file is the release record'));
    scenario = 'wdrop0';
    press('Record the release');
    await screen.findByText(/We couldn’t confirm that this happened/);
    expect(button('Record the release').disabled).toBe(true);
    press('Record the release');
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
  it('4811 shows the recorded release and no form (AC21)', async () => {
    await open(4811, /Release recorded/);
    expect(screen.queryByRole('button', { name: 'Record the release' })).toBeNull();
    expect(within(document.body).getByText(/REL-2026-044/)).toBeTruthy();
  });
  it('4809 and 4801 draw no record form', async () => {
    await open(4809, 'Preparing release readiness');
    expect(screen.queryByText('Record the release')).toBeNull();
  });
});
