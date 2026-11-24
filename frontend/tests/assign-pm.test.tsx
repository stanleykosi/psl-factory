// @vitest-environment jsdom
// F-88 SCR-24: the Unassigned list of received RFPs and the Assign PM drawer on the live API. The fetch stand-in is the mock itself
// (mock/received-bids.mjs), so the 409, uncertain and 422 answers are its own shapes.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { assignProblems } from '@/features/rfp/AssignPmDrawer';
import { deadlineText, UnassignedBids } from '@/features/rfp/UnassignedBids';

// @ts-expect-error plain ESM module without type declarations
import { receivedBids, receivedBidsLog, resetReceivedBids } from '../mock/received-bids.mjs';

import { useNodeUploads } from './assistant-bridge';

vi.mock('next/navigation', () => ({ usePathname: () => '/my-work', useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const TOKEN = 'mock-csrf-pm';
const CASE = '2f0c8a54-6b0e-4f7a-9d1a-0c5b2f6f1a11';
let scenario: string | undefined;
let gate: Promise<void> | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let makeFile: (name: string, type?: string, size?: number) => File;
const requests = () => fetchStub.mock.calls.map(([r]) => r);
const order = () => requests().filter((r) => /received-bids/.test(r.url)).map((r) => `${r.method} ${new URL(r.url).pathname.replace('/api/v1/received-bids', '') || '/'}`);
const posts = () => requests().filter((r) => r.method === 'POST' && /\/assignment$/.test(new URL(r.url).pathname));
const bodyOf = async (r: Request) => JSON.parse(await r.clone().text());

beforeEach(async () => {
  makeFile = await useNodeUploads();
  resetReceivedBids();
  scenario = undefined;
  gate = undefined;
  setCsrfToken(TOKEN);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
    if (/\/cases\/[^/]+\/files$/.test(url.pathname)) return json(200, { upload_id: 7001, name: 'proof.pdf', size: 12, sha256: 'a'.repeat(64), download_url: '/x' });
    if (gate && url.pathname.endsWith('/assignments')) await gate;
    const raw = request.method === 'GET' ? '' : await request.clone().text();
    const [status, body] = receivedBids({ method: request.method.toLowerCase(), url, raw, rawBytes: new Uint8Array(), contentType: null, scenario, csrfOk: request.headers.get('x-csrftoken') === TOKEN, persona: 'pm' });
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const mountList = (openId?: string) => render(<UnassignedBids openId={openId} hrefFor={(id) => `/my-work?queue=unassigned&assign=${id}`} onClose={vi.fn()} pathname="/my-work?queue=unassigned" />);
/** The drawer over the list, as MyWork draws it. */
async function drawer() {
  const view = mountList(CASE);
  await screen.findByRole('dialog', { name: 'Assign accountable PM' });
  return view;
}
async function choose(name: string, option: string) {
  fireEvent.click(await screen.findByRole('combobox', { name }));
  fireEvent.click(await screen.findByRole('option', { name: option }));
}
/** A valid form on the recorded-proof route. */
async function fill() {
  await choose('Accountable PM', 'Amara Okoye');
  await choose('You are assigning as', 'Head of PMO');
  fireEvent.click(await screen.findByRole('radio', { name: 'Use a recorded proof' }));
  await choose('Use a recorded proof', 'Delegation email, 18 Nov');
  fireEvent.change(screen.getByLabelText('Reason for choosing this PM'), { target: { value: 'Led the last Northwind bid.' } });
}
const press = () => fireEvent.click(screen.getByRole('button', { name: /^(Assign PM|Check again)$/ }));

describe('the Unassigned list (AC9, AC16)', () => {
  it('reads GET /received-bids/assignments, pages by cursor, and gives a restricted row no Assign button', async () => {
    mountList();
    const items = await screen.findAllByRole('listitem');
    expect(items).toHaveLength(12);
    expect(items[0].getAttribute('data-case')).toBe(CASE);
    expect(within(items[0]).getByRole('link', { name: 'Assign PM' }).getAttribute('href')).toBe(`/my-work?queue=unassigned&assign=${CASE}`);
    expect(within(items[2]).queryByRole('link')).toBeNull();
    expect(within(items[2]).getByText('You need access to this RFP’s owner first')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(13));
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
    expect(order()).toEqual(['GET /assignments', 'GET /assignments']);
    expect(new URL(requests()[1].url).searchParams.get('cursor')).toBe('12');
    expect(requests().some((r) => /\/api\/v1\/work/.test(r.url))).toBe(false);
  });

  it('says what each deadline is without inventing one', () => {
    expect(deadlineText({ deadline: null, deadline_status: 'unknown' })).toBe('Deadline not known');
    expect(deadlineText({ deadline: null, deadline_status: 'not_stated' })).toBe('No deadline stated');
    expect(deadlineText({ deadline: '2026-12-05T17:00:00Z', deadline_status: 'stated' })).toMatch(/^Deadline 05 Dec 2026|^Deadline 5 Dec 2026/);
  });

  it('a 401 is the signed-out state; a 403 is the plain not-open message; other failures retry', async () => {
    scenario = '401';
    const { unmount } = mountList();
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('/sign-in?next=');
    unmount();
    scenario = '403';
    const second = mountList();
    expect(await screen.findByText('This queue isn’t open to your role.')).toBeTruthy();
    second.unmount();
    scenario = '500';
    mountList();
    expect(await screen.findByRole('button', { name: 'Retry' })).toBeTruthy();
  });
});

describe('reading the assignment (AC10, AC14, AC15)', () => {
  it('shows nominees, roles and proofs as served, preselects nothing, and no role or hint beside a nominee', async () => {
    await drawer();
    fireEvent.click(await screen.findByRole('combobox', { name: 'Accountable PM' }));
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['Amara Okoye', 'Tunde Bello']);
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    expect(screen.getByRole('combobox', { name: 'Accountable PM' }).textContent).toContain('Choose a PM');
    expect(screen.getByRole('combobox', { name: 'You are assigning as' }).textContent).toContain('Choose a role');
    expect(screen.queryByText(/optional/i)).toBeNull();
    expect(screen.getByText('The PM prepares the RFP response')).toBeTruthy();
    expect(screen.getByText('What happens next:')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/alerted/i);
    expect(order().sort()).toEqual([`GET /${CASE}/assignment`, 'GET /assignments']);
  });

  it('one role is plain text; no proofs offers only the upload; no next steps hides the block', async () => {
    scenario = 'rb_one_role';
    const first = await drawer();
    expect(screen.queryByRole('combobox', { name: 'You are assigning as' })).toBeNull();
    expect(screen.getByText('Head of PMO')).toBeTruthy();
    first.unmount();
    scenario = 'rb_no_proofs';
    await drawer();
    expect(screen.queryByRole('radio', { name: 'Use a recorded proof' })).toBeNull();
    expect(await screen.findByText(/choose a file/)).toBeTruthy();
  });

  it('no next steps: no "What happens next" block', async () => {
    scenario = 'rb_no_steps';
    await drawer();
    await screen.findByRole('combobox', { name: 'Accountable PM' });
    expect(screen.queryByText('What happens next:')).toBeNull();
  });

  it('setup required says so in plain words with no form; no nominees says so; an assignment shows Already assigned with its steps', async () => {
    scenario = 'rb_setup';
    const a = await drawer();
    expect(await screen.findByText('Nobody is set up to assign yet. Ask a PSL admin to finish setup.')).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
    a.unmount();
    scenario = 'rb_no_nominees';
    const b = await drawer();
    expect(await screen.findByText('No one can be chosen for this RFP yet.')).toBeTruthy();
    b.unmount();
    scenario = 'rb_assigned';
    await drawer();
    expect(await screen.findByText('Already assigned: Amara Okoye')).toBeTruthy();
    expect(screen.getByText('The PM prepares the RFP response')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Assign PM' })).toBeNull();
  });

  it('403 and 404 on the read say their own words and keep the list', async () => {
    scenario = undefined;
    const real = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (r) => (/\/assignment$/.test(r.url) ? json(403, { code: 'forbidden', message: 'x' }) : real(r)));
    const a = mountList(CASE);
    expect(await screen.findByText('You can’t assign a PM for this RFP.')).toBeTruthy();
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0);
    a.unmount();
    fetchStub.mockImplementation(async (r) => (/\/assignment$/.test(r.url) ? json(404, { code: 'not_found', message: 'x' }) : real(r)));
    mountList(CASE);
    expect(await screen.findByText('This RFP isn’t available.')).toBeTruthy();
  });
});

describe('assigning (AC10, AC11, AC12, AC13, AC19)', () => {
  it('submitting empty names PM, role, proof and reason and sends nothing', async () => {
    await drawer();
    await screen.findByRole('combobox', { name: 'Accountable PM' });
    press();
    const summary = await screen.findByRole('alert');
    for (const text of ['Choose a PM to continue.', 'Choose a role to continue.', 'Add proof to continue.', 'Give a reason to continue.']) expect(within(summary).getByText(text)).toBeTruthy();
    expect(posts()).toHaveLength(0);
  });

  it('one JSON POST with integer ids from the read; "PM assigned" only after the assignment and the list are read again', async () => {
    await drawer();
    await fill();
    let release!: () => void;
    gate = new Promise((resolve) => (release = resolve));
    press();
    await waitFor(() => expect(order()).toContain(`POST /${CASE}/assignment`));
    await waitFor(() => expect(order().filter((o) => o === 'GET /assignments')).toHaveLength(2));
    expect(screen.queryByText(/PM assigned/)).toBeNull();
    release();
    expect(await screen.findByText('PM assigned: Amara Okoye.')).toBeTruthy();
    const [post] = posts();
    expect(await bodyOf(post)).toEqual({ intake: 77, revision: 3, candidate: 301, role: 'Head of PMO', reason: 'Led the last Northwind bid.', evidence: 901 });
    expect(post.headers.get('x-csrftoken')).toBe(TOKEN);
    expect(order().slice(-3)).toEqual([`POST /${CASE}/assignment`, `GET /${CASE}/assignment`, 'GET /assignments']);
    // the row leaves the list only because the re-read list no longer holds it
    await waitFor(() => expect(document.querySelector(`[data-case="${CASE}"]`)).toBeNull());
    expect(screen.getByText('The PM prepares the RFP response')).toBeTruthy();
    await waitFor(() => expect(document.activeElement?.getAttribute('role')).toBe('status'));
  });

  it('a 5xx that stored the assignment re-reads first and shows Already assigned, never a second POST', async () => {
    scenario = 'assign_lost_reply';
    await drawer();
    await fill();
    press();
    expect(await screen.findByText('Already assigned: Amara Okoye')).toBeTruthy();
    expect(screen.getByText('Not confirmed at first; confirmed after reading it again.')).toBeTruthy();
    expect(posts()).toHaveLength(1);
    expect(screen.queryByText(/PM assigned/)).toBeNull();
  });

  it('a 5xx that stored nothing offers the form again with the unconfirmed words and resends nothing by itself', async () => {
    scenario = 'assign_uncertain';
    await drawer();
    await fill();
    press();
    expect(await screen.findByText('We couldn’t confirm the PM was assigned. Check before trying again.')).toBeTruthy();
    expect(posts()).toHaveLength(1);
    expect((screen.getByLabelText('Reason for choosing this PM') as HTMLTextAreaElement).value).toBe('Led the last Northwind bid.');
    expect(screen.queryByText(/PM assigned/)).toBeNull();
  });

  it('a network failure re-reads, and if that fails too only "Check again" (a read) is offered', async () => {
    await drawer();
    await fill();
    const real = fetchStub.getMockImplementation()!;
    let down = true;
    fetchStub.mockImplementation(async (r) => {
      if (down && /\/assignment$/.test(r.url)) throw new TypeError('Failed to fetch');
      return real(r);
    });
    press();
    expect(await screen.findByText('We couldn’t confirm the PM was assigned. Check before trying again.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Check again' })).toBeTruthy();
    down = false;
    press();
    // the read found no assignment, so the form is offered again (as "Assign PM"), and nothing was resent
    expect(await screen.findByRole('button', { name: 'Assign PM' })).toBeTruthy();
    expect(posts()).toHaveLength(1);
  });

  it('a 409 says it changed, reads again and shows the new state', async () => {
    scenario = 'assign_stale';
    await drawer();
    await fill();
    press();
    expect(await screen.findByText('This changed while you were working.')).toBeTruthy();
    expect(order().slice(-2)).toEqual([`POST /${CASE}/assignment`, `GET /${CASE}/assignment`]);
    // the re-read revision is the new one, so the same choice now goes through
    press();
    expect(await screen.findByText('PM assigned: Amara Okoye.')).toBeTruthy();
    expect((await bodyOf(posts()[1])).revision).toBe(4);
  });

  it.each([
    ['assign_denied', 'You can’t assign a PM for this RFP.'],
    ['assign_missing', 'This RFP isn’t available.'],
  ])('%s shows %s and keeps the form', async (answer, words) => {
    scenario = answer;
    await drawer();
    await fill();
    press();
    expect(await screen.findByText(words)).toBeTruthy();
    expect(screen.queryByText(/PM assigned/)).toBeNull();
    expect((screen.getByLabelText('Reason for choosing this PM') as HTMLTextAreaElement).value).not.toBe('');
  });

  it('a 422 maps reason and evidence to their fields with the API words', async () => {
    scenario = 'assign_invalid';
    await drawer();
    await fill();
    press();
    expect((await screen.findAllByText('Say why this person was chosen.')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('This proof is not available.').length).toBeGreaterThan(0);
    expect(screen.queryByText(/PM assigned/)).toBeNull();
  });

  it('a proof upload sends upload_id and checked:true with no evidence; the tick-box is required; switching routes clears', async () => {
    await drawer();
    await choose('Accountable PM', 'Tunde Bello');
    await choose('You are assigning as', 'PMO Lead');
    fireEvent.click(await screen.findByRole('radio', { name: 'Upload a file' }));
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [makeFile('proof.pdf', 'application/pdf', 12)] } });
    const tick = await screen.findByLabelText('I checked this file is the right proof.');
    const upload = requests().find((r) => r.method === 'POST' && /\/cases\//.test(r.url))!;
    expect(new URL(upload.url).pathname).toBe(`/api/v1/cases/${CASE}/files`);
    fireEvent.change(screen.getByLabelText('Reason for choosing this PM'), { target: { value: 'Knows the client.' } });
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('Confirm you checked the file.');
    expect(posts()).toHaveLength(0);
    // switching routes clears the other: the file and its tick go
    fireEvent.click(screen.getByRole('radio', { name: 'Use a recorded proof' }));
    expect(screen.queryByLabelText('I checked this file is the right proof.')).toBeNull();
    fireEvent.click(screen.getByRole('radio', { name: 'Upload a file' }));
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [makeFile('proof.pdf', 'application/pdf', 12)] } });
    fireEvent.click(await screen.findByLabelText('I checked this file is the right proof.'));
    void tick;
    press();
    expect(await screen.findByText('PM assigned: Tunde Bello.')).toBeTruthy();
    expect(await bodyOf(posts()[0])).toEqual({ intake: 77, revision: 3, candidate: 302, role: 'PMO Lead', reason: 'Knows the client.', upload_id: 7001, checked: true });
  });

  it('the pure rule: each of the four is required, a listed proof or a checked upload, and a reason over 4000 is refused', () => {
    const data = JSON.parse(JSON.stringify(receivedBids({ method: 'get', url: new URL(`http://x/api/v1/received-bids/${CASE}/assignment`), scenario: undefined, csrfOk: true, persona: 'pm' })[1]));
    const empty = { candidate: undefined, role: undefined, route: undefined, evidence: undefined, upload: null, checked: false, reason: '' };
    expect(Object.keys(assignProblems(data, empty))).toEqual(['candidate', 'role', 'proof', 'reason']);
    expect(Object.keys(assignProblems(data, { ...empty, candidate: '301', role: 'Head of PMO', route: 'listed', evidence: '901', reason: ' ' }))).toEqual(['reason']);
    expect(assignProblems(data, { ...empty, candidate: '301', role: 'Head of PMO', route: 'listed', evidence: '901', reason: 'x'.repeat(4001) }).reason).toContain('4000');
    expect(assignProblems(data, { ...empty, candidate: '301', role: 'Head of PMO', route: 'listed', evidence: '901', reason: 'ok' })).toEqual({});
  });
});

describe('source rules (AC17)', () => {
  const read = (path: string) => readFileSync(join(__dirname, '..', path), 'utf8');
  it('the two screens call none of the v7 paths', () => {
    for (const file of ['src/features/rfp/AssignPmDrawer.tsx', 'src/features/rfp/useReceivedBidAssign.ts', 'src/features/rfp/UnassignedBids.tsx', 'src/features/start-work/lines/receivedBid.tsx', 'src/features/rfp/receivedBids.ts']) {
      expect(read(file)).not.toMatch(/\/work\/\{|'\/api\/v1\/work'|cases\/[^'"`]*\/evidence|useWorkspaceAssign|fileToEvidence/);
    }
  });
  it('the chooser imports no per-line form', () => {
    expect(read('src/features/start-work/LineChooser.tsx')).not.toMatch(/from '\.\/lines\/|receivedBid|weeklyReport/);
  });
  it('the mock logs what was sent', () => {
    expect(receivedBidsLog()).toEqual({ requests: [], logged: [] });
  });
});
