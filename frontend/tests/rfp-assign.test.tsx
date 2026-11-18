// @vitest-environment jsdom
// F-36: SCR-24 "Assign accountable PM" over My work's Unassigned list, through the real contract mock over HTTP (so the
// 409, uncertain and 422 cases are the mock's own). Mock evidence only: it shows the page follows the contract it was given.
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { MyWork } from '@/features/my-work/MyWork';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

configure({ asyncUtilTimeout: 5000 });
process.env.TZ = 'Africa/Lagos';

const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
    listeners.forEach((l) => l());
  };
  const router = { replace: vi.fn((url: string) => set(new URL(url, 'http://localhost').search)), push: vi.fn(), prefetch: vi.fn() };
  return { listeners, get: () => params, set, router };
});
vi.mock('next/navigation', async () => {
  const { useSyncExternalStore } = await import('react');
  const subscribe = (cb: () => void) => {
    nav.listeners.add(cb);
    return () => nav.listeners.delete(cb);
  };
  return { usePathname: () => '/my-work', useRouter: () => nav.router, useSearchParams: () => useSyncExternalStore(subscribe, nav.get) };
});

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const assignRequest = ajv.compile(openapi.paths['/api/v1/work/{work_id}/assignment'].post.requestBody.content['application/json'].schema);

const realFetch = globalThis.fetch;
let server: Server;
let base: string;
let cookies: string;
type Sent = { method: string; path: string; body: Record<string, unknown> | undefined };
let sent: Sent[];
/** A held reply: the matching request waits until `release` is called. */
let hold: { match: (s: Sent) => boolean; release: () => void } | undefined;
let override: ((s: Sent) => Response | undefined) | undefined;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

beforeEach(async () => {
  await realFetch(`${base}/__mock/reset`, { method: 'POST' });
  cookies = 'psl_mock_persona=pmo_lead';
  sent = [];
  hold = undefined;
  override = undefined;
  nav.router.replace.mockClear();
  setCsrfToken('mock-csrf-pmo_lead');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === 'GET' ? '' : await request.text();
      const entry: Sent = { method: request.method, path: url.pathname + url.search, body: text ? JSON.parse(text) : undefined };
      sent.push(entry);
      if (url.pathname === '/api/v1/notifications' || url.pathname.startsWith('/api/v1/notifications')) return new Response(JSON.stringify({ items: [], unread: 0 }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      const answer = override?.(entry);
      if (answer) return answer;
      if (hold?.match(entry)) await new Promise<void>((resolve) => (hold!.release = resolve));
      return realFetch(`${base}${url.pathname}${url.search}`, {
        method: request.method,
        headers: { 'Content-Type': 'application/json', Cookie: cookies, 'X-CSRFToken': request.headers.get('X-CSRFToken') ?? '' },
        body: text || undefined,
      });
    }),
  );
});
afterEach(async () => {
  // let a request still running finish before the tree is removed
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const posts = (suffix: string) => sent.filter((r) => r.method === 'POST' && r.path.endsWith(suffix));
const assigns = () => posts('/assignment');
const itemFixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/work', `${name}.json`), 'utf8'));

async function open(id: string) {
  nav.set(`?queue=unassigned&assign=${id}`);
  render(<MyWork />);
  const dialog = await screen.findByRole('dialog', { name: 'Assign accountable PM' });
  await waitFor(() => expect(within(dialog).queryByText('Loading…')).toBeNull());
  return dialog;
}
const choosePm = async (dialog: HTMLElement, name: RegExp | string) => {
  fireEvent.click(within(dialog).getByRole('combobox', { name: /Accountable PM/ }));
  fireEvent.click(await screen.findByRole('option', { name }));
};
const press = (dialog: HTMLElement, label = 'Assign PM') => fireEvent.click(within(dialog).getByRole('button', { name: label }));
const pressWhenReady = async (dialog: HTMLElement, label: string) => fireEvent.click(await within(dialog).findByRole('button', { name: label }));
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });

describe('the panel (criteria 1 to 5)', () => {
  it('opens over the list with the client and reference, and the list stays drawn behind it', async () => {
    const dialog = await open('W-3302');
    expect(within(dialog).getByText('Tamarind Loans · TL-RFP-2026-014')).toBeTruthy();
    expect(screen.getAllByText(/loan origination RFP/).length).toBeGreaterThan(1);
    expect(screen.getByRole('tab', { name: /Unassigned/ })).toBeTruthy();
    // opening the panel changes the URL only: the list was read once
    expect(sent.filter((r) => r.path.startsWith('/api/v1/work?')).length).toBe(1);
  });

  it('lists exactly the returned candidates, chooses nobody, and counts them', async () => {
    const dialog = await open('W-3301');
    expect(within(dialog).getByRole('combobox', { name: /Accountable PM/ }).textContent).toContain('Choose a PM');
    expect(within(dialog).getByText('3 people can prepare RFPs here')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('combobox', { name: /Accountable PM/ }));
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(['Tunde BelloPMO · 2 RFPs in progress', 'Sola MartinsPMO · 1 RFP in progress', 'Ife OkoroPMO']);
    expect(options[2].textContent).not.toMatch(/0/);
    expect(screen.queryByRole('textbox', { name: /Accountable PM/ })).toBeNull();
  });

  it('says one person for a single candidate and requires the note when the response does', async () => {
    const dialog = await open('W-3303');
    expect(within(dialog).getByText('1 person can prepare RFPs here')).toBeTruthy();
    await choosePm(dialog, /Sola Martins/);
    press(dialog);
    expect(await within(dialog).findAllByText('Add a note to continue.')).not.toHaveLength(0);
    expect(assigns()).toHaveLength(0);
  });

  it('shows the acting role as text for one role and sends no acting_role; asks the backend for none it was not given', async () => {
    const dialog = await open('W-3301');
    expect(within(dialog).getByText('You are assigning as')).toBeTruthy();
    expect(within(dialog).getByText('PMO Lead')).toBeTruthy();
    expect(within(dialog).getByText('One of the roles PSL allows to assign RFPs')).toBeTruthy();
    expect(within(dialog).queryByRole('combobox', { name: /You are assigning as/ })).toBeNull();
  });

  it('draws the role choices the response lists, whoever is signed in, and sends the chosen one', async () => {
    const dialog = await open('W-3302');
    const role = within(dialog).getByRole('combobox', { name: /You are assigning as/ });
    expect(role.textContent).toContain('PMO Lead');
    fireEvent.click(role);
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['PMO Lead', 'CEO']);
    fireEvent.click(screen.getByRole('option', { name: 'CEO' }));
    await choosePm(dialog, /Tunde Bello/);
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    expect(assigns()[0].body).toMatchObject({ acting_role: 'ceo', person_id: 'P-0007', expected_revision: 1 });
  });

  it.each(['pm', 'ceo'])('reads nothing from /me and draws the same role choices for persona %s', async (persona) => {
    cookies = `psl_mock_persona=${persona}`;
    const dialog = await open('W-3302');
    fireEvent.click(within(dialog).getByRole('combobox', { name: /You are assigning as/ }));
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['PMO Lead', 'CEO']);
    expect(sent.some((r) => r.path === '/api/v1/me')).toBe(false);
  });

  it('shows the backend’s own next-step sentences word for word, or fixed wording that names no channel', async () => {
    const dialog = await open('W-3302');
    expect(dialog.textContent).toContain('The PM you choose is alerted by WhatsApp and email and sees it in Needs me. They start the RFP response. Tola starts reading the RFP once the PM opens it.');
    cleanup();
    const plain = await open('W-3301');
    const text = plain.textContent ?? '';
    expect(text).toContain('The PM you choose is alerted and sees it in Needs me. They start the RFP response.');
    expect(text).not.toMatch(/WhatsApp|email|Tola/);
  });
});

describe('no assign, no control (criterion 3)', () => {
  it('goes on to the work item when the response has no assign', async () => {
    nav.set('?queue=unassigned&assign=W-3305');
    render(<MyWork />);
    await waitFor(() => expect(nav.router.replace).toHaveBeenCalledWith('/work/W-3305'));
    expect(screen.queryByRole('button', { name: 'Assign PM' })).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('shows an empty list as a sentence with no control', async () => {
    const dialog = await open('W-3304');
    expect(await within(dialog).findByText('No one can prepare RFPs here yet.')).toBeTruthy();
    expect(within(dialog).queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Assign PM' })).toBeNull();
  });

  it('draws no control on a copy of W-3301 with the assign block removed', async () => {
    const copy = itemFixture('W-3301');
    delete copy.assign;
    override = (s) => (s.method === 'GET' && s.path === '/api/v1/work/W-3301' ? json(200, copy) : undefined);
    nav.set('?queue=unassigned&assign=W-3301');
    render(<MyWork />);
    await waitFor(() => expect(nav.router.replace).toHaveBeenCalledWith('/work/W-3301'));
    expect(screen.queryByRole('button', { name: 'Assign PM' })).toBeNull();
  });

  it('shows the not-open view for 403 and 404 with no client or reference, and the signed-out state for 401', async () => {
    for (const [status, id] of [[403, 'W-3301'], [404, 'W-3399']] as const) {
      override = (s) => (s.method === 'GET' && s.path.startsWith('/api/v1/work/W-3') ? json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: 'No.' }) : undefined);
      const dialog = await open(id);
      expect(await within(dialog).findByText('You can’t open this item.')).toBeTruthy();
      expect(dialog.textContent).not.toMatch(/Tamarind|TL-RFP|Tunde/);
      expect(within(dialog).queryByRole('combobox')).toBeNull();
      cleanup();
    }
    override = (s) => (s.method === 'GET' && s.path.startsWith('/api/v1/work/W-3') ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    const dialog = await open('W-3301');
    const link = await within(dialog).findByRole('link', { name: 'Sign in' });
    expect(decodeURIComponent(link.getAttribute('href') ?? '')).toContain('next=/my-work?queue=unassigned&assign=W-3301');
  });
});

describe('writes (criteria 6 to 11)', () => {
  it('sends one typed assignment with the item revision and a trimmed note, and a double press sends once', async () => {
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Note/ }), { target: { value: '  led the Lagoon bid  ' } });
    const button = within(dialog).getByRole('button', { name: 'Assign PM' });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    await settle();
    expect(assigns()).toHaveLength(1);
    expect(assigns()[0].body).toEqual({ expected_revision: 1, person_id: 'P-0007', note: 'led the Lagoon bid' });
    expect(assignRequest(assigns()[0].body)).toBe(true);
    const log = (await (await realFetch(`${base}/__mock/workspace-log`)).json()) as { assignments: { work_id: string; person_id: string; status: number }[] };
    expect(log.assignments).toMatchObject([{ work_id: 'W-3301', person_id: 'P-0007', status: 200 }]);
  });

  it('says nothing is assigned until the item and list are read again, then closes, shows the notice and drops the row', async () => {
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    // hold the list's re-read
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const before = sent.length;
    override = undefined;
    const original = globalThis.fetch;
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      if (request.method === 'GET' && new URL(request.url).pathname === '/api/v1/work' && sent.length > before) await gate;
      return original(request);
    }));
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    await settle();
    expect(screen.queryByText(/is now with/)).toBeNull();
    expect(screen.getByRole('dialog')).toBeTruthy();
    release();
    expect(await screen.findByText('TL-RFP-2026-014 is now with Tunde Bello.')).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByRole('tab', { name: /Unassigned/ }).textContent).toContain('5');
  });

  it('says it was sent but not confirmed when the item cannot be read back, and never says assigned', async () => {
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    override = (s) => (s.method === 'GET' && s.path === '/api/v1/work/W-3301' ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    expect(await screen.findByText(/The assignment was sent, but we couldn’t refresh to confirm it\. Reload My work to check\./)).toBeTruthy();
    expect(screen.queryByText(/is now with/)).toBeNull();
  });

  it('uploads proof first, then sends acting_role, evidence_id and the case revision the upload returned', async () => {
    const dialog = await open('W-3302');
    await choosePm(dialog, /Sola Martins/);
    const input = dialog.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(['From: kemi'], 'assignment-email.eml', { type: 'message/rfc822' })] } });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(1));
    expect(posts('/evidence')[0].body).toMatchObject({ kind: 'assignment_proof', case_revision: 1 });
    expect(await within(dialog).findByText(/Uploaded/)).toBeTruthy();
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    expect(assigns()[0].body).toMatchObject({ acting_role: 'pmo_lead', person_id: 'P-0021', case_revision: 2, evidence_id: 'EV-C-3302-1' });
  });

  it('shows "Size unknown" for a file whose size is not known, never NaN or 0', async () => {
    const dialog = await open('W-3302');
    const file = new File(['x'], 'unsized.eml');
    Object.defineProperty(file, 'size', { value: undefined });
    fireEvent.change(dialog.querySelector<HTMLInputElement>('input[type="file"]')!, { target: { files: [file] } });
    expect(await within(dialog).findByText(/Size unknown/)).toBeTruthy();
    expect(dialog.textContent).not.toMatch(/NaN|\b0 KB/);
  });

  it('sends nothing while the upload runs, and a failed file blocks the send until it is removed', async () => {
    const dialog = await open('W-3302');
    await choosePm(dialog, /Sola Martins/);
    override = (s) => (s.method === 'POST' && s.path.endsWith('/evidence') ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    const input = dialog.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(['x'], 'proof.eml')] } });
    expect(await within(dialog).findByText('Couldn’t upload. Try again.')).toBeTruthy();
    expect(within(dialog).getByRole('button', { name: 'Try again' })).toBeTruthy();
    press(dialog);
    expect(await within(dialog).findByText('Remove the file that didn’t upload, or try it again.')).toBeTruthy();
    expect(assigns()).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove proof.eml' }));
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    expect(assigns()[0].body).not.toHaveProperty('evidence_id');
  });

  it('holds Assign while an upload is running', async () => {
    const dialog = await open('W-3302');
    await choosePm(dialog, /Sola Martins/);
    hold = { match: (s) => s.method === 'POST' && s.path.endsWith('/evidence'), release: () => {} };
    fireEvent.change(dialog.querySelector<HTMLInputElement>('input[type="file"]')!, { target: { files: [new File(['x'], 'proof.eml')] } });
    await waitFor(() => expect(posts('/evidence')).toHaveLength(1));
    press(dialog);
    await settle();
    expect(assigns()).toHaveLength(0);
    hold.release();
    await within(dialog).findByText(/Uploaded/);
  });

  it('refuses a missing PM and an over-long note before sending, and keeps the typed note', async () => {
    const dialog = await open('W-3301');
    press(dialog);
    expect(await within(dialog).findAllByText('Choose a PM to continue.')).not.toHaveLength(0);
    expect(assigns()).toHaveLength(0);
    await choosePm(dialog, /Tunde Bello/);
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Note/ }), { target: { value: 'x'.repeat(2001) } });
    press(dialog);
    expect(await within(dialog).findAllByText('Keep the note to 2000 characters.')).not.toHaveLength(0);
    expect(assigns()).toHaveLength(0);
  });

  it('puts a 422 under the field it names and keeps the entries', async () => {
    cookies = 'psl_mock_persona=pmo_lead; psl_mock_assign=invalid';
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Note/ }), { target: { value: 'kept' } });
    press(dialog);
    expect(await within(dialog).findAllByText('Check person_id.')).not.toHaveLength(0);
    expect((within(dialog).getByRole('textbox', { name: /Note/ }) as HTMLTextAreaElement).value).toBe('kept');
    expect(within(dialog).getByRole('combobox', { name: /Accountable PM/ }).textContent).toContain('Tunde Bello');
  });

  it('names acting_role and evidence_id under their fields on a 422', async () => {
    const dialog = await open('W-3302');
    await choosePm(dialog, /Tunde Bello/);
    override = (s) => (s.method === 'POST' && s.path.endsWith('/assignment') ? json(422, { code: 'invalid', message: 'Check these fields: acting_role, evidence_id.', fields: [{ name: 'acting_role', message: 'That role can’t assign here.' }, { name: 'evidence_id', message: 'That file wasn’t found.' }] }) : undefined);
    press(dialog);
    expect(await within(dialog).findByText('That role can’t assign here.')).toBeTruthy();
    expect(within(dialog).getByText('That file wasn’t found.')).toBeTruthy();
  });

  it('on a 409 re-reads, keeps the choices, and the next press sends the new revision once', async () => {
    cookies = 'psl_mock_persona=pmo_lead; psl_mock_assign=stale';
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    press(dialog);
    expect(await within(dialog).findByText('This changed while you were working. Showing version 2.')).toBeTruthy();
    expect(within(dialog).getByRole('combobox', { name: /Accountable PM/ }).textContent).toContain('Tunde Bello');
    expect(assigns()).toHaveLength(1);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(assigns()).toHaveLength(1);
    cookies = 'psl_mock_persona=pmo_lead';
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(2));
    expect(assigns()[1].body).toMatchObject({ expected_revision: 2, person_id: 'P-0007' });
  });

  it('clears a choice a re-read no longer lists, and says so', async () => {
    cookies = 'psl_mock_persona=pmo_lead; psl_mock_assign=stale';
    const dialog = await open('W-3301');
    await choosePm(dialog, /Ife Okoro/);
    const changed = itemFixture('W-3301');
    changed.revision = 2;
    changed.assign.candidates = changed.assign.candidates.slice(0, 2);
    override = (s) => (s.method === 'GET' && s.path === '/api/v1/work/W-3301' && sent.filter((r) => r.path === '/api/v1/work/W-3301').length > 1 ? json(200, changed) : undefined);
    press(dialog);
    expect(await within(dialog).findByText('That person can no longer be chosen.')).toBeTruthy();
    expect(within(dialog).getByRole('combobox', { name: /Accountable PM/ }).textContent).toContain('Choose a PM');
  });

  it('after a write that was recorded and then failed, says not confirmed, then the re-read result, and sends once', async () => {
    const dialog = await open('W-3306');
    await choosePm(dialog, /Tunde Bello/);
    press(dialog);
    expect(await within(dialog).findByText('Assigned to Tunde Bello')).toBeTruthy();
    expect(within(dialog).queryByRole('combobox')).toBeNull();
    expect(screen.queryByText(/is now with/)).toBeNull();
    await settle();
    expect(assigns()).toHaveLength(1);
    const log = (await (await realFetch(`${base}/__mock/workspace-log`)).json()) as { assignments: { written: boolean }[] };
    expect(log.assignments).toMatchObject([{ written: true }]);
  });

  it('after a failure that wrote nothing, shows the form again with the entries kept and sends exactly one more on Try again', async () => {
    cookies = 'psl_mock_persona=pmo_lead; psl_mock_assign=uncertain';
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Note/ }), { target: { value: 'kept' } });
    press(dialog);
    expect(await within(dialog).findByText(/We couldn’t confirm the PM was assigned/)).toBeTruthy();
    expect(screen.queryByText(/is now with/)).toBeNull();
    expect((within(dialog).getByRole('textbox', { name: /Note/ }) as HTMLTextAreaElement).value).toBe('kept');
    expect(assigns()).toHaveLength(1);
    cookies = 'psl_mock_persona=pmo_lead';
    await pressWhenReady(dialog, 'Try again');
    await waitFor(() => expect(assigns()).toHaveLength(2));
    expect(await screen.findByText('TL-RFP-2026-014 is now with Tunde Bello.')).toBeTruthy();
  });

  it('treats a network error as uncertain: re-reads first, shows the form again and does not resend', async () => {
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    override = (s) => {
      if (s.method === 'POST' && s.path.endsWith('/assignment')) throw new TypeError('network');
      return undefined;
    };
    press(dialog);
    expect(await within(dialog).findByText(/We couldn’t confirm the PM was assigned/)).toBeTruthy();
    await settle();
    expect(assigns()).toHaveLength(1);
    expect(sent.filter((r) => r.path === '/api/v1/work/W-3301').length).toBeGreaterThanOrEqual(2);
    expect(within(dialog).getByRole('combobox', { name: /Accountable PM/ })).toBeTruthy();
    expect(screen.queryByText(/is now with/)).toBeNull();
  });

  it('shows the not-open view when the write answers 403', async () => {
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    override = (s) => (s.method === 'POST' && s.path.endsWith('/assignment') ? json(403, { code: 'forbidden', message: 'No.' }) : undefined);
    press(dialog);
    expect(await within(dialog).findByText('You can’t open this item.')).toBeTruthy();
    expect(dialog.textContent).not.toMatch(/Tamarind|TL-RFP|Tunde/);
  });
});

describe('Unknown, never 0 (criterion 13)', () => {
  it('shows Unknown for a missing client, role and hint, and after a write with no rfp.pm', async () => {
    const copy = itemFixture('W-3301');
    delete copy.rfp.client;
    for (const c of copy.assign.candidates) {
      delete c.role;
      delete c.hint;
    }
    const after = itemFixture('W-3301.next');
    delete after.rfp.pm;
    let written = false;
    override = (s) => {
      if (s.method === 'GET' && s.path === '/api/v1/work/W-3301') return json(200, written ? after : copy);
      if (s.method === 'POST' && s.path.endsWith('/assignment')) {
        written = true;
        return json(200, { work_id: 'W-3301', state: 'waiting', revision: 2, assigned_to: 'Tunde Bello' });
      }
      return undefined;
    };
    const dialog = await open('W-3301');
    expect(within(dialog).getByText('Unknown · TL-RFP-2026-014')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('combobox', { name: /Accountable PM/ }));
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['Tunde Bello', 'Sola Martins', 'Ife Okoro']);
    fireEvent.click(screen.getByRole('option', { name: /Tunde/ }));
    press(dialog);
    await waitFor(() => expect(assigns()).toHaveLength(1));
    expect(await screen.findByText('TL-RFP-2026-014 is now with Tunde Bello.')).toBeTruthy();
  });

  it('shows "Assigned to Unknown" when a re-read finds the assignment but no PM name', async () => {
    cookies = 'psl_mock_persona=pmo_lead; psl_mock_assign=uncertain_written';
    const after = itemFixture('W-3301.next');
    delete after.rfp.pm;
    const dialog = await open('W-3301');
    await choosePm(dialog, /Tunde Bello/);
    override = (s) => (s.method === 'GET' && s.path === '/api/v1/work/W-3301' && assigns().length > 0 ? json(200, after) : undefined);
    press(dialog);
    expect((await within(dialog).findByText(/Assigned to/)).textContent).toContain('Assigned to Unknown');
  });
});
