// @vitest-environment jsdom
// F-112: "Log a change" on the Changes register against the live-shaped mock: one request per press, no automatic retry, a lost answer
// locks and "Check the list" only reads, "Logged" only from the re-read, the proof chosen from the served list.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { LogChangeDrawer } from '@/features/change-request/LogChangeDrawer';

// @ts-expect-error plain ESM module without type declarations
import { CHANGE_PATH, changeLive, resetChangeLive } from '../mock/change-live.mjs';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects/P-0101/registers', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const reloadList = vi.fn(async () => undefined);
const writes = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(writes().map(async ([r]) => JSON.parse(await r.clone().text()) as Record<string, unknown>));
const reads = () => fetchStub.mock.calls.filter(([r]) => r.method === 'GET').length;
const quiet = () => new Promise((r) => setTimeout(r, 30));

beforeEach(() => {
  resetChangeLive();
  scenario = undefined;
  reloadList.mockClear();
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    if (!CHANGE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const reply = changeLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async () => {
  render(<LogChangeDrawer caseId="P-0101" reloadList={reloadList} onClose={() => undefined} pathname="/projects/P-0101/registers" />);
  await screen.findByRole('button', { name: 'Log the change' });
};
const choose = (label: string | RegExp, option: RegExp) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: option }));
};
const fill = (reference = 'CR-0099') => {
  fireEvent.change(screen.getByLabelText('Reference'), { target: { value: reference } });
  choose('Category', /^Standard$/);
  fireEvent.change(screen.getByLabelText('Module'), { target: { value: 'Billing' } });
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Change the invoice footer' } });
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'The client asked' } });
  choose('Proof', /security assessment/);
};
const BODY = { action: 'capture', case_revision: 12, reference: 'CR-0099', category: 'Standard', module: 'Billing', description: 'Change the invoice footer', reason: 'The client asked', evidence_id: 7901 };

describe('log a change', () => {
  it('every field is required: an empty form shows what is missing and sends nothing', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    expect((await screen.findAllByText(/to continue\./)).length).toBeGreaterThanOrEqual(6);
    expect(writes()).toHaveLength(0);
  });
  it('the proof can only be chosen from the read’s list and the category from the two words; no key or proof id is typed', async () => {
    await open();
    fireEvent.click(screen.getByRole('combobox', { name: 'Proof' }));
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['security assessment · version 1 · no. 7901', 'meeting minutes · version 2 · no. 7902']);
    fireEvent.click(screen.getByRole('option', { name: /meeting minutes/ }));
    fireEvent.click(screen.getByRole('combobox', { name: 'Category' }));
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Normal', 'Standard']);
  });
  it('sends one capture with the read’s case revision; "Logged" appears only because the list read again holds it', async () => {
    await open();
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await screen.findByText(/Logged: CR-0099/);
    expect(await sent()).toEqual([BODY]);
    expect(reloadList).toHaveBeenCalledTimes(1);
  });
  it('a double click sends one request', async () => {
    await open();
    fill();
    const b = screen.getByRole('button', { name: 'Log the change' });
    fireEvent.click(b);
    fireEvent.click(b);
    await screen.findByText(/Logged: CR-0099/);
    expect(writes()).toHaveLength(1);
  });
  it('a 409 keeps the typed text and sends nothing by itself', async () => {
    await open();
    fill();
    scenario = 'w409';
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await screen.findByText(/This changed while you were working/);
    expect((screen.getByLabelText('Description') as HTMLTextAreaElement).value).toBe('Change the invoice footer');
    expect((screen.getByLabelText('Reference') as HTMLInputElement).value).toBe('CR-0099');
    await quiet();
    expect(writes()).toHaveLength(1);
  });
  it('a 422 shows its message beside the named field', async () => {
    await open();
    fill('CR-0031');
    // the seeded list of P-0101 is empty: log twice so the second reference clashes
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await screen.findByText(/Logged: CR-0031/);
    cleanup();
    await open();
    fill('CR-0031');
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    expect((await screen.findAllByText('This reference is already used.')).length).toBeGreaterThan(0);
    expect(writes()).toHaveLength(2);
  });
  it('a lost answer before the write ran locks the form; "Check the list" only reads and never sends again', async () => {
    await open();
    fill();
    scenario = 'wdrop0';
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect((screen.getByLabelText('Reference') as HTMLInputElement).readOnly).toBe(true);
    const before = reads();
    fireEvent.click(screen.getByRole('button', { name: 'Check the list' }));
    await screen.findByText('The change isn’t in the list yet. Nothing here shows it was logged.');
    expect(reads()).toBeGreaterThan(before);
    expect(writes()).toHaveLength(1);
  });
  it('a lost answer after the write ran: "Check the list" finds it and says so only from the read', async () => {
    await open();
    fill();
    scenario = 'wdrop';
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(screen.queryByText(/Logged:/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Check the list' }));
    await waitFor(() => expect(screen.getByText(/Logged: CR-0099/)).toBeTruthy());
    expect(writes()).toHaveLength(1);
  });
  it('csrf_failed asks for another press and sends nothing again', async () => {
    await open();
    fill();
    scenario = 'w403csrf';
    fireEvent.click(screen.getByRole('button', { name: 'Log the change' }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    await quiet();
    expect(writes()).toHaveLength(1);
    expect(screen.queryByText(/Logged:/)).toBeNull();
  });
});
