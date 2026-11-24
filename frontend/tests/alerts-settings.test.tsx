// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { AlertSettingsPage } from '@/features/alerts/AlertSettingsPage';

import { json, settle, until } from './alerts-helpers';

// /settings/alerts (SCR-15 settings) on the live 1.24.0 shapes: two switches, readiness, receipts and the save.
vi.mock('next/navigation', () => ({
  usePathname: () => '/settings/alerts',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const held = () => ({
  revision: 3,
  email_requested: true,
  whatsapp_requested: false,
  email_ready: true,
  whatsapp_ready: false,
  recent_deliveries: [
    { channel: 'email', state: 'delivered', created_at: '2026-11-12T08:00:00Z', delivered_at: '2026-11-12T08:00:04Z', receipt: 'r-77' },
    { channel: 'whatsapp', state: 'uncertain', created_at: '2026-11-11T17:00:00Z', delivered_at: null, receipt: null },
    { channel: 'email', state: 'queued', created_at: '2026-11-10T17:00:00Z', delivered_at: null, receipt: null },
    { channel: 'whatsapp', state: 'held', created_at: '2026-11-09T17:00:00Z', delivered_at: null, receipt: null },
  ],
});

type Call = { method: string; csrf: string | null; raw: string };
let calls: Call[];
let answer: (call: Call) => Response | Promise<Response>;
let prefs: ReturnType<typeof held>;

beforeEach(() => {
  setCsrfToken('csrf-1');
  calls = [];
  prefs = held();
  answer = (call) => {
    if (call.method === 'GET') return json(200, prefs);
    const sent = JSON.parse(call.raw);
    const { recent_deliveries: receipts, ...rest } = prefs;
    void receipts;
    prefs = { ...prefs, revision: sent.revision + 1, email_requested: sent.email_requested, whatsapp_requested: sent.whatsapp_requested };
    return json(200, { ...rest, revision: prefs.revision, email_requested: sent.email_requested, whatsapp_requested: sent.whatsapp_requested });
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const call = { method: request.method, csrf: request.headers.get('X-CSRFToken'), raw: request.method === 'POST' ? await request.text() : '' };
      calls.push(call);
      return answer(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const posts = () => calls.filter((c) => c.method === 'POST');
const sent = () => posts().map((c) => JSON.parse(c.raw));
const sw = (name: string) => screen.getByRole('switch', { name });
const saveButton = () => screen.getByRole('button', { name: /Save settings|Saving…/ });

async function open() {
  const view = render(<AlertSettingsPage />);
  await until(() => expect(screen.queryByRole('switch', { name: 'Email' })).toBeTruthy());
  return view;
}

function phone() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
}

describe('what the page shows', () => {
  it('exactly an Email and a WhatsApp switch with Ready or Not ready yet, and the receipts', async () => {
    await open();
    expect(document.querySelector('.alerts-eyebrow')!.textContent).toBe('SETTINGS / ALERTS');
    expect(screen.getAllByRole('switch').map((s) => [s.getAttribute('aria-label'), s.getAttribute('aria-checked')])).toEqual([
      ['Email', 'true'],
      ['WhatsApp', 'false'],
    ]);
    expect([...document.querySelectorAll('.alerts-channelstate')].map((s) => s.textContent)).toEqual(['Ready', 'Not ready yet']);
    expect(sw('Email').tagName).toBe('BUTTON');
    expect(sw('Email').getAttribute('aria-describedby')).toBe('alerts-state-email');
    expect(screen.getByRole('heading', { level: 2, name: 'Recent deliveries' })).toBeTruthy();
  });

  it('draws no per-event rows, digest or quiet-hours select, locked rows or phone-number block', async () => {
    await open();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(document.body.textContent).not.toMatch(/digest|quiet hours|verified|WhatsApp number|decision is waiting/i);
  });

  it('a switch on while its channel is not ready says nothing will arrive until it is set up', async () => {
    await open();
    fireEvent.click(sw('WhatsApp'));
    expect(document.querySelector('#alerts-state-whatsapp')!.textContent).toBe('Not ready yet: you will not receive anything on this channel until it is set up');
    expect(sw('WhatsApp').getAttribute('aria-checked')).toBe('true');
  });

  it('receipts: Queued, Not confirmed, Delivered and Held, as returned; uncertain is never worded or styled as delivered', async () => {
    await open();
    const items = [...document.querySelectorAll('.alerts-receipt')];
    expect(items.map((li) => [li.children[0].textContent, li.children[1].textContent])).toEqual([
      ['Email', 'Delivered'],
      ['WhatsApp', 'Not confirmed'],
      ['Email', 'Queued'],
      ['WhatsApp', 'Held'],
    ]);
    // delivered shows delivered_at (08:00:04Z is 09:00 WAT), the rest created_at; receipt only when present
    expect(items[0].textContent).toContain('12 Nov 2026 · 09:00 WAT');
    expect(items[0].textContent).toContain('Receipt r-77');
    expect(items[1].textContent).toContain('11 Nov 2026 · 18:00 WAT');
    expect(items[1].textContent).not.toContain('Receipt');
    expect(items[1].textContent).not.toMatch(/delivered/i);
    expect(items[1].querySelector('.alerts-receiptstate')!.className).toContain('alerts-receiptstate--uncertain');
    expect(items[1].querySelector('.alerts-receiptstate')!.className).not.toContain('delivered');
  });

  it('no receipts: "Nothing has been sent to you yet."', async () => {
    prefs.recent_deliveries = [];
    await open();
    expect(screen.getByText('Nothing has been sent to you yet.')).toBeTruthy();
    expect(document.querySelector('.alerts-receipts')).toBeNull();
  });
});

describe('saving', () => {
  it('Save is off, with its reason, until a switch differs from what was read', async () => {
    await open();
    expect(saveButton().hasAttribute('disabled') || saveButton().getAttribute('aria-disabled') === 'true').toBe(true);
    expect(screen.getByText('Nothing to save: change a switch first.')).toBeTruthy();
    expect(saveButton().getAttribute('aria-describedby')).toBe('alerts-nochange');
    fireEvent.click(sw('Email'));
    expect(screen.queryByText('Nothing to save: change a switch first.')).toBeNull();
    fireEvent.click(sw('Email'));
    expect(screen.queryByText('Nothing to save: change a switch first.')).toBeTruthy();
    fireEvent.click(saveButton());
    await settle();
    expect(posts()).toHaveLength(0);
  });

  it('sends exactly {revision, email_requested, whatsapp_requested} with the CSRF token, shows Saved, and the next save uses the returned revision', async () => {
    await open();
    fireEvent.click(sw('WhatsApp'));
    fireEvent.click(saveButton());
    await until(() => expect(screen.queryByText('Saved')).toBeTruthy());
    expect(sent()).toEqual([{ revision: 3, email_requested: true, whatsapp_requested: true }]);
    expect(Object.keys(sent()[0])).toEqual(['revision', 'email_requested', 'whatsapp_requested']);
    expect(posts()[0].csrf).toBe('csrf-1');
    // the 200 had no receipts: the held list stays
    expect(document.querySelectorAll('.alerts-receipt')).toHaveLength(4);
    fireEvent.click(sw('Email'));
    expect(screen.queryByText('Saved')).toBeNull();
    fireEvent.click(saveButton());
    await until(() => expect(sent()).toHaveLength(2));
    expect(sent()[1]).toEqual({ revision: 4, email_requested: false, whatsapp_requested: true });
  });

  it('a 409 shows the stale notice, drops the draft on Reload and never retries by itself', async () => {
    let first = true;
    answer = (call) => {
      if (call.method === 'GET') return json(200, prefs);
      if (first) {
        first = false;
        prefs = { ...prefs, revision: 4, email_requested: false };
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return json(200, prefs);
    };
    await open();
    fireEvent.click(sw('WhatsApp'));
    fireEvent.click(saveButton());
    await until(() => expect(screen.queryByText(/These settings changed elsewhere\. Reload to see the latest\./)).toBeTruthy());
    await settle();
    expect(posts()).toHaveLength(1);
    // the draft is still the person's until they reload
    expect(sw('WhatsApp').getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    await until(() => expect(sw('Email').getAttribute('aria-checked')).toBe('false'));
    expect(sw('WhatsApp').getAttribute('aria-checked')).toBe('false');
    expect(screen.queryByText(/changed elsewhere/)).toBeNull();
    expect(posts()).toHaveLength(1);
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(2);
  });

  it('a 422 shows the server message and keeps the draft', async () => {
    answer = (call) => (call.method === 'GET' ? json(200, prefs) : json(422, { code: 'invalid', message: 'Choose at least one channel.' }));
    await open();
    fireEvent.click(sw('Email'));
    fireEvent.click(saveButton());
    await until(() => expect(screen.queryByText(/Choose at least one channel\./)).toBeTruthy());
    expect(sw('Email').getAttribute('aria-checked')).toBe('false');
  });

  for (const [label, reply] of [
    ['a 403', () => json(403, { code: 'forbidden', message: 'No.' })],
    ['a 500', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['a network failure', () => Promise.reject(new TypeError('network'))],
  ] as const) {
    it(`${label} keeps the draft and Save can be pressed again`, async () => {
      let fail = true;
      answer = (call) => (call.method === 'GET' ? json(200, prefs) : fail ? reply() : json(200, { ...prefs, revision: 4 }));
      await open();
      fireEvent.click(sw('Email'));
      fireEvent.click(saveButton());
      await until(() => expect(screen.queryByText(/We couldn’t save your settings\. Nothing was changed\. Try again\./)).toBeTruthy());
      expect(sw('Email').getAttribute('aria-checked')).toBe('false');
      fail = false;
      fireEvent.click(saveButton());
      await until(() => expect(screen.queryByText('Saved')).toBeTruthy());
      expect(posts()).toHaveLength(2);
    });
  }

  it('a 401 on save shows the signed-out state', async () => {
    answer = (call) => (call.method === 'GET' ? json(200, prefs) : json(401, { code: 'unauthenticated', message: 'Sign in.' }));
    await open();
    fireEvent.click(sw('Email'));
    fireEvent.click(saveButton());
    await until(() => expect(screen.queryByText(/signed out/i)).toBeTruthy());
  });

  it('one save at a time: a second press while saving sends nothing', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    answer = async (call) => {
      if (call.method === 'GET') return json(200, prefs);
      await gate;
      return json(200, { ...prefs, revision: 4, email_requested: false });
    };
    await open();
    fireEvent.click(sw('Email'));
    fireEvent.click(saveButton());
    fireEvent.click(saveButton());
    await settle();
    expect(posts()).toHaveLength(1);
    release();
    await until(() => expect(screen.queryByText('Saved')).toBeTruthy());
  });
});

describe('load states', () => {
  it('a 500 shows the error card with Try again', async () => {
    answer = () => json(500, { code: 'server_error', message: 'Down.' });
    render(<AlertSettingsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alert settings/)).toBeTruthy());
    answer = () => json(200, prefs);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(screen.queryByRole('switch', { name: 'Email' })).toBeTruthy());
  });

  it('a 401 shows the signed-out state and nothing more is read', async () => {
    answer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    render(<AlertSettingsPage />);
    await until(() => expect(screen.queryByText(/signed out/i)).toBeTruthy());
    expect(calls).toHaveLength(1);
  });

  it('a body without a revision, the switches or a receipts list is a load error, not a page', async () => {
    for (const bad of [{ ...held(), revision: undefined }, { ...held(), recent_deliveries: undefined }, { ...held(), email_requested: 'yes' }, {}]) {
      answer = () => json(200, bad);
      const view = render(<AlertSettingsPage />);
      await until(() => expect(screen.queryByText(/We couldn’t load your alert settings/)).toBeTruthy());
      expect(screen.queryByRole('switch')).toBeNull();
      view.unmount();
    }
  });
});

describe('phone (SCR-15-mobile-settings)', () => {
  it('back link, both switches, receipts and the Save in the pinned footer', async () => {
    phone();
    await open();
    expect(screen.getByRole('link', { name: '← Notifications' }).getAttribute('href')).toBe('/notifications');
    expect(screen.getAllByRole('switch')).toHaveLength(2);
    const footer = document.querySelector('.alerts-footer') as HTMLElement;
    expect(within(footer).getByRole('button', { name: 'Save settings' })).toBeTruthy();
    expect(document.querySelectorAll('.alerts-receipt')).toHaveLength(4);
    fireEvent.click(sw('Email'));
    fireEvent.click(within(footer).getByRole('button', { name: 'Save settings' }));
    await until(() => expect(sent()).toEqual([{ revision: 3, email_requested: false, whatsapp_requested: false }]));
  });
});
