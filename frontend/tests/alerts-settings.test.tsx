// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AlertSettingsPage } from '@/features/alerts/AlertSettingsPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { createAlertsMock } from '../mock/alerts.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';

vi.mock('next/navigation', () => ({
  usePathname: () => '/settings/alerts',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockDir = join(__dirname, '../mock');
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const me = JSON.parse(readFileSync(join(mockDir, 'fixtures/me.finance_lead.json'), 'utf8'));
const board = JSON.parse(readFileSync(join(mockDir, 'fixtures/E-ALERT-PREFS-READ.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Call = { method: string; csrf: string | null; raw: string };
let mock: { handle: (args: object) => { status: number; body: unknown } };
let scenario: string;
let calls: Call[];
let hook: (call: Call) => Response | Promise<Response | undefined> | undefined;

function fromMock(call: Call) {
  const operationId = call.method === 'PUT' ? 'E-ALERT-PREFS' : 'E-ALERT-PREFS-READ';
  const r = mock.handle({ operationId, url: new URL('http://x/api/v1/me/alert-preferences'), raw: call.raw, persona: 'finance_lead', cookies: { psl_mock_alerts: scenario } });
  return json(r.status, r.body);
}

beforeEach(() => {
  mock = createAlertsMock({ openapi });
  scenario = 'board';
  calls = [];
  hook = () => undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const call = { method: request.method, csrf: request.headers.get('X-CSRFToken'), raw: request.method === 'PUT' ? await request.text() : '' };
      calls.push(call);
      return (await hook(call)) ?? fromMock(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

const puts = () => calls.filter((c) => c.method === 'PUT');
const sent = () => puts().map((c) => JSON.parse(c.raw));
const sw = (name: string) => screen.getByRole('switch', { name });
const checked = (name: string) => sw(name).getAttribute('aria-checked');
const save = () => fireEvent.click(screen.getByRole('button', { name: /Save settings|Saving…/ }));

async function open() {
  const result = render(
    <AppShell>
      <AlertSettingsPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  return result;
}

function phone() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
}

describe('settings (SCR-15-desktop-settings)', () => {
  it('board: eyebrow, title, the WHEN / WHATSAPP / EMAIL / TIMING matrix, both cards and Save', async () => {
    await open();
    expect(document.querySelector('.alerts-eyebrow')!.textContent).toBe('SETTINGS / ALERTS');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('How you’re alerted');
    const table = screen.getByRole('table', { name: 'Alerts for each kind of work' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['WHEN', 'WHATSAPP', 'EMAIL', 'TIMING']);
    const bodyRows = within(table).getAllByRole('row').slice(1);
    expect(bodyRows.map((tr) => {
      const cells = tr.querySelectorAll('td');
      return [cells[0].textContent, ...[...tr.querySelectorAll('[role=switch]')].map((s) => s.getAttribute('aria-checked')), cells[3].textContent];
    })).toEqual([
      ['A decision is waiting for me', 'true', 'true', 'Straight away'],
      ['Information is requested from me', 'true', 'true', 'Straight away'],
      ['Work I started is stuck', 'true', 'true', 'Straight away'],
      ['Work I started is verified', 'false', 'true', 'In the daily digest'],
      ['Everything else', 'false', 'true', 'In the daily digest'],
    ]);
    const digest = screen.getByLabelText('Daily digest at') as HTMLSelectElement;
    expect([digest.value, [...digest.options].map((o) => o.textContent)]).toEqual(['08:00', ['07:00', '08:00', '09:00']]);
    const quiet = screen.getByLabelText('Quiet hours') as HTMLSelectElement;
    expect(quiet.selectedOptions[0].textContent).toBe('20:00 to 07:00, and weekends');
    expect(screen.getByText('WhatsApp number')).toBeTruthy();
    expect(screen.getByText('+234 803 *** 4412 · verified')).toBeTruthy();
    expect(screen.getByText('Alerts never include amounts or client details beyond the name.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Save settings' })).toBeTruthy();
  });

  it('switches are named, toggle on click and Space (a native button), and say their state', async () => {
    await open();
    expect(screen.getAllByRole('switch')).toHaveLength(10);
    const name = 'WhatsApp, A decision is waiting for me';
    expect(sw(name).tagName).toBe('BUTTON');
    expect(sw(name).getAttribute('type')).toBe('button');
    fireEvent.click(sw(name));
    expect(checked(name)).toBe('false');
    // Space and Enter on a focused native button fire click; jsdom does not synthesise it, so this checks the element type above.
    fireEvent.click(sw(name));
    expect(checked(name)).toBe('true');
  });

  it('save sends exactly the contract body with X-CSRFToken, shows saved, and the next save sends revision 4', async () => {
    await open();
    fireEvent.click(sw('Email, Work I started is stuck'));
    fireEvent.change(screen.getByLabelText('Daily digest at'), { target: { value: '09:00' } });
    save();
    await until(() => expect(screen.getByRole('status').textContent).toBe('Your alert settings are saved.'));
    expect(puts().map((c) => c.csrf)).toEqual(['mock-csrf-finance_lead']);
    expect(sent()[0]).toEqual({
      channel: 'both',
      frequency: 'immediate',
      expected_revision: 3,
      events: [
        { key: 'decision_waiting', whatsapp: true, email: true },
        { key: 'info_requested', whatsapp: true, email: true },
        { key: 'work_stuck', whatsapp: true, email: false },
        { key: 'work_verified', whatsapp: false, email: true },
        { key: 'everything_else', whatsapp: false, email: true },
      ],
      digest_at: '09:00',
      quiet_hours: '20-07-weekends',
    });
    expect(checked('Email, Work I started is stuck')).toBe('false');
    fireEvent.click(sw('Email, Everything else'));
    expect(screen.queryByText('Your alert settings are saved.')).toBeNull();
    save();
    await until(() => expect(puts()).toHaveLength(2));
    expect(sent()[1].expected_revision).toBe(4);
    for (const raw of puts().map((c) => c.raw)) {
      expect(raw).not.toMatch(/4412|masked|label|timing|note/);
    }
  });

  it('one save in flight: Saving… with aria-disabled, a second press sends nothing', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    hook = async (call) => {
      if (call.method !== 'PUT') return undefined;
      await gate;
      return fromMock(call);
    };
    await open();
    save();
    await until(() => expect(screen.getByRole('button', { name: 'Saving…' }).getAttribute('aria-disabled')).toBe('true'));
    save();
    save();
    release();
    await until(() => expect(screen.getByText('Your alert settings are saved.')).toBeTruthy());
    expect(puts()).toHaveLength(1);
  });

  it('409: re-reads, drops the edits, shows the newer version and focuses the callout; the next save sends revision 4', async () => {
    scenario = 'stale';
    await open();
    fireEvent.click(sw('WhatsApp, A decision is waiting for me'));
    expect(checked('WhatsApp, A decision is waiting for me')).toBe('false');
    save();
    const text = 'Someone changed these settings since you opened them. This is the latest version; make your changes again.';
    await until(() => expect(screen.getByRole('alert').textContent).toBe(text));
    expect(document.activeElement).toBe(screen.getByRole('alert'));
    expect(checked('WhatsApp, A decision is waiting for me')).toBe('true');
    expect(checked('Email, Work I started is stuck')).toBe('false');
    expect(calls.map((c) => c.method)).toEqual(['GET', 'PUT', 'GET']);
    save();
    await until(() => expect(screen.getByText('Your alert settings are saved.')).toBeTruthy());
    expect(sent()[1].expected_revision).toBe(4);
  });

  it('422: channel "sms" goes back unchanged; the message shows verbatim, focused; the edits stay', async () => {
    scenario = 'invalid';
    await open();
    fireEvent.click(sw('Email, Everything else'));
    save();
    await until(() => expect(screen.getByRole('alert').textContent).toBe('We couldn’t save your settings. Check these fields: channel.'));
    expect(document.activeElement).toBe(screen.getByRole('alert'));
    expect(sent()[0].channel).toBe('sms');
    expect(checked('Email, Everything else')).toBe('false');
  });

  for (const [label, failure] of [
    ['500', () => json(500, { code: 'server_error', message: 'The server had a problem.' })],
    ['a network error', () => Promise.reject(new TypeError('offline'))],
  ] as const) {
    it(`${label} on save keeps the edits, says nothing changed with the reference, and does not retry`, async () => {
      hook = (call) => (call.method === 'PUT' ? (failure() as Response | Promise<Response>) : undefined);
      await open();
      fireEvent.click(sw('Email, Everything else'));
      save();
      await until(() => expect(screen.getByRole('alert').textContent).toMatch(/^We couldn’t save your settings\. Nothing was changed\. .+ Reference (server_error|network_error) for support\.$/));
      expect(checked('Email, Everything else')).toBe('false');
      await act(async () => {
        await new Promise((r) => setTimeout(r, 50));
      });
      expect(puts()).toHaveLength(1);
      expect(screen.getByRole('button', { name: 'Save settings' }).getAttribute('aria-disabled')).toBeNull();
    });
  }

  it('locked: the reason shows, the switches are aria-disabled and never change, and the PUT sends them as read', async () => {
    scenario = 'locked';
    await open();
    expect(screen.getByText('Only HR can receive payroll alerts outside the app')).toBeTruthy();
    for (const name of ['WhatsApp, Payroll problems', 'Email, Payroll problems']) {
      expect(sw(name).getAttribute('aria-disabled')).toBe('true');
      fireEvent.click(sw(name));
      fireEvent.keyDown(sw(name), { key: ' ' });
      expect(checked(name)).toBe('false');
    }
    save();
    await until(() => expect(puts()).toHaveLength(1));
    expect(sent()[0].events.at(-1)).toEqual({ key: 'payroll_problems', whatsapp: false, email: false });
  });

  it('load error and a 200 without events: the error card, no table and no Save', async () => {
    hook = () => json(500, { code: 'server_error', message: 'Broke.' });
    const { unmount } = await open();
    expect(screen.getByRole('alert').textContent).toContain('We couldn’t load your alert settings. Your work is safe; nothing was changed.');
    expect(screen.getByRole('alert').textContent).toContain('Reference server_error for support.');
    unmount();
    const { events: _events, ...noEvents } = board;
    void _events;
    hook = () => json(200, noEvents);
    await open();
    expect(screen.getByRole('alert').textContent).toContain('Reference missing_events for support.');
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Save settings' })).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    hook = () => undefined;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(screen.getByRole('table')).toBeTruthy());
  });

  it('401 on the read, and on the save, shows signed out with next=/settings/alerts', async () => {
    hook = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    const { unmount } = await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsettings%2Falerts');
    unmount();
    hook = (call) => (call.method === 'PUT' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : undefined);
    await open();
    save();
    await until(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fsettings%2Falerts'));
  });
});

describe('phone (SCR-15-mobile-settings)', () => {
  it('phone scenario: back link, four event cards with named switches, quiet hours line, footer Save; no selects or number', async () => {
    phone();
    scenario = 'phone';
    await open();
    expect(screen.getByRole('link', { name: '← Notifications' }).getAttribute('href')).toBe('/notifications');
    const cards = [...document.querySelectorAll('.alerts-eventcard')];
    expect(cards.map((c) => [c.querySelector('.alerts-eventlabel')!.textContent, c.querySelector('.alerts-timing')!.textContent])).toEqual([
      ['A decision is waiting for me', 'Straight away'],
      ['Information is requested from me', 'Straight away'],
      ['Work I started is stuck', 'Straight away'],
      ['Work I started is verified', 'Daily digest'],
    ]);
    expect(within(cards[3] as HTMLElement).getAllByRole('switch').map((s) => s.getAttribute('aria-label'))).toEqual(['WhatsApp, Work I started is verified', 'Email, Work I started is verified']);
    expect([...cards[0].querySelectorAll('[aria-hidden="true"]')].map((s) => s.textContent)).toEqual(['', 'WhatsApp', '', 'Email']);
    expect(screen.getByText('Quiet hours 20:00 to 07:00 and weekends')).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByText('WhatsApp number')).toBeNull();
    expect(document.querySelector('.alerts-footer button')!.textContent).toBe('Save settings');
  });

  it('board on the phone renders the fifth event and the save body has no digest_at or quiet_hours', async () => {
    phone();
    await open();
    expect(document.querySelectorAll('.alerts-eventcard')).toHaveLength(5);
    expect(screen.getByText('Everything else')).toBeTruthy();
    save();
    await until(() => expect(puts()).toHaveLength(1));
    expect(sent()[0]).not.toHaveProperty('digest_at');
    expect(sent()[0]).not.toHaveProperty('quiet_hours');
    expect(sent()[0].events).toHaveLength(5);
  });
});
