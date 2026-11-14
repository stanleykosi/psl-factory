// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OverviewPage } from '@/features/overview/OverviewPage';
import { AppShell } from '@/shell/AppShell';

// The 3D floor is replaced by a stub: the factory runs only when the overview imports the module.
const floor = vi.hoisted(() => ({ loaded: false, fail: undefined as (() => void) | undefined }));
vi.mock('@/features/floor/Floor3D', async () => {
  floor.loaded = true;
  const { floorLabel } = await import('@/features/floor/support');
  return {
    default: function Floor3DStub({ lines, onFailure }: { lines: unknown[]; onFailure: () => void }) {
      floor.fail = onFailure;
      return <canvas role="img" aria-label={floorLabel(lines.length)} />;
    },
  };
});
vi.mock('@/features/floor/support', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/floor/support')>()),
  webglAvailable: () => true,
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/overview', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const read = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const REDUCED = '(prefers-reduced-motion: reduce)';
let media: Record<string, boolean>;
const listeners = new Set<() => void>();
const setMedia = (query: string, value: boolean) => {
  media[query] = value;
  listeners.forEach((l) => l());
};

beforeEach(() => {
  media = {};
  listeners.clear();
  vi.stubGlobal('matchMedia', (q: string) => ({
    get matches() {
      return media[q] ?? false;
    },
    media: q,
    addEventListener: (_: string, l: () => void) => listeners.add(l),
    removeEventListener: (_: string, l: () => void) => listeners.delete(l),
  }));
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

const radio = (name: string) => screen.getByRole('radio', { name });
const flatRows = () => document.querySelectorAll('section[aria-label="Lines"] .overview__row');

async function open() {
  render(
    <AppShell>
      <OverviewPage />
    </AppShell>,
  );
  await until(() => expect(screen.getByRole('radiogroup', { name: 'View' })).toBeTruthy());
}

describe('the 3D floor loads only when chosen', () => {
  it('Flat does not import Floor3D; choosing 3D floor does, and the flat list stays for screen readers', async () => {
    await open();
    expect(floor.loaded).toBe(false);
    fireEvent.click(radio('3D floor'));
    expect(radio('3D floor').getAttribute('aria-checked')).toBe('true');
    await until(() => expect(screen.getByRole('img', { name: /^3D factory floor: 8 lines/ })).toBeTruthy());
    expect(floor.loaded).toBe(true);
    expect(screen.getByRole('img').getAttribute('aria-label')).toBe('3D factory floor: 8 lines. The same figures are listed in the flat view below.');
    expect(flatRows()).toHaveLength(8);
    expect(flatRows()[0].closest('.overview__sr')).not.toBeNull();
    expect(document.querySelectorAll('dl.overview__totals > div')).toHaveLength(4);
    expect(screen.getByRole('link', { name: 'See all exceptions' })).toBeTruthy();

    fireEvent.click(radio('Flat'));
    expect(screen.queryByRole('img')).toBeNull();
    expect(flatRows()[0].closest('.overview__sr')).toBeNull();
  });

  it('arrow keys move the selection and the focus', async () => {
    await open();
    radio('Flat').focus();
    fireEvent.keyDown(radio('Flat'), { key: 'ArrowRight' });
    expect(radio('3D floor').getAttribute('aria-checked')).toBe('true');
    expect(document.activeElement).toBe(radio('3D floor'));
    expect(radio('Flat').tabIndex).toBe(-1);
    fireEvent.keyDown(radio('3D floor'), { key: 'ArrowLeft' });
    expect(radio('Flat').getAttribute('aria-checked')).toBe('true');
    expect(document.activeElement).toBe(radio('Flat'));
  });

  it('reduced motion turning on while 3D is shown switches to Flat; the switch returns when it turns off', async () => {
    await open();
    fireEvent.click(radio('3D floor'));
    await until(() => expect(screen.getByRole('img')).toBeTruthy());
    act(() => setMedia(REDUCED, true));
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeTruthy();
    act(() => setMedia(REDUCED, false));
    expect(radio('Flat').getAttribute('aria-checked')).toBe('true');
  });

  it('a runtime failure in 3D falls back to Flat with a warning and hides the 3D option', async () => {
    await open();
    fireEvent.click(radio('3D floor'));
    await until(() => expect(screen.getByRole('img')).toBeTruthy());
    act(() => floor.fail!());
    expect(screen.getByText('We couldn’t show the 3D floor, so it’s shown flat.').closest('.psl-callout--warning')).not.toBeNull();
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(flatRows()).toHaveLength(8);
    expect(flatRows()[0].closest('.overview__sr')).toBeNull();
  });
});
