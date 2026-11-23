// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from '@/shell/AppShell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/my-work',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
const WORK_DESK = '/desk/';
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  // A /me whose work_desk_url and destination django_url hold real-looking paths: the frame must not link to any of them.
  const body = { ...me, work_desk_url: WORK_DESK, destinations: me.destinations.map((d: { key: string; title: string }) => ({ ...d, ['django' + '_url']: `/x/${d.key}/` })) };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) =>
      new URL(request.url).pathname === '/api/v1/me' ? json(200, body) : json(200, { items: [], unread_count: 0, as_of: '2026-11-23T00:00:00Z' }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe('AppShell with Django fields on /me', () => {
  it('draws our own frame, with no embed element and no Django-form links', async () => {
    const { container } = render(<AppShell><p>page body</p></AppShell>);
    await waitFor(() => expect(screen.getByText('page body')).toBeTruthy());
    expect(container.querySelector('psl-work-client')).toBeNull();
    expect(container.querySelector('.shell-topbar')).not.toBeNull();
    for (const a of container.querySelectorAll('a')) expect(a.getAttribute('href') ?? '').not.toContain('factory-forms');
    expect(container.querySelectorAll('nav a').length).toBeGreaterThan(0);
    for (const el of container.querySelectorAll('[href], [src], [action]')) {
      const target = `${el.getAttribute('href')} ${el.getAttribute('src')} ${el.getAttribute('action')}`;
      expect(target).not.toMatch(/\/desk\/|\/x\/|\/retired\//);
    }
    expect(container.textContent).not.toContain(WORK_DESK);
  });
});
