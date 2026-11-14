// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import { OverviewPage } from '@/features/overview/OverviewPage';
import { AppShell } from '@/shell/AppShell';

// The floor module fails to load (a chunk error): the import rejects.
vi.mock('@/features/floor/Floor3D', () => {
  throw new Error('Loading chunk failed');
});
vi.mock('@/features/floor/support', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/floor/support')>()),
  webglAvailable: () => true,
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/overview', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const read = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) =>
      new URL(request.url).pathname === '/api/v1/me' ? json(200, read('me.finance_lead.json')) : json(200, read('E-OVERVIEW.json')),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

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

it('a rejected floor import falls back to Flat with a warning and hides the 3D option', async () => {
  render(
    <AppShell>
      <OverviewPage />
    </AppShell>,
  );
  await until(() => expect(screen.getByRole('radiogroup', { name: 'View' })).toBeTruthy());
  fireEvent.click(screen.getByRole('radio', { name: '3D floor' }));
  expect(screen.getByRole('status').textContent).toContain('Loading the 3D floor…');
  await until(() => expect(screen.getByText('We couldn’t show the 3D floor, so it’s shown flat.')).toBeTruthy());
  expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
  expect(screen.queryByRole('status')).toBeNull();
  const rows = document.querySelectorAll('section[aria-label="Lines"] > ul > li');
  expect(rows).toHaveLength(8);
});
