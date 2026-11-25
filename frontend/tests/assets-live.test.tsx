// @vitest-environment jsdom
// F-102: the fixed asset schedule (SCR-55) read mapping, the proof-link rule and the page on the live-shaped mock (mock/assets-live.mjs).
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { errorFromResponse } from '@/api/errors';
import type { LiveAssets } from '@/api/types';
import { ToastProvider } from '@/components';
import { assetsAdapter } from '@/features/fixed-assets/assetsAdapter';
import { assetsSections, errorWords, isUnclear, proofLinks } from '@/features/fixed-assets/labels';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { adapterFor } from '@/features/workspace/adapter';
import '@/features/workspace/lines';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';

// @ts-expect-error plain ESM module without type declarations
import { ASSETS_PATH, assetsLive } from '../mock/assets-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/3901', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const reply = (path: string, scenario?: string, method = 'get') => assetsLive({ method, url: new URL(path, 'http://m.local'), scenario, persona: 'finance_lead' }) as [number, unknown, Record<string, string>?];
const read = (id: number) => reply(`/api/v1/work/${id}/assets`)[1] as LiveAssets;
const draw = (sections: Section[]) => render(<>{sections.map((s) => <SectionView key={s.key} section={s} level={2} />)}</>);

describe('the mock and the contract agree', () => {
  const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, { responses: Record<string, { content?: { 'application/json': { schema: object } } }> }>> };
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  const validator = (path: string) => ajv.compile(spec.paths[path].get.responses['200'].content!['application/json'].schema);
  it.each([3901, 3902, 3903, 3904, 3905, 3906, 3907, 3908])('assets %i and its work item are valid answers', (id) => {
    const assets = validator('/api/v1/work/{work_id}/assets');
    const work = validator('/api/v1/work/{work_id}');
    expect(assets(read(id)), JSON.stringify(assets.errors)).toBe(true);
    expect(work(reply(`/api/v1/work/${id}`)[1]), JSON.stringify(work.errors)).toBe(true);
  });
  it('3909 is unavailable everywhere, 3910 refuses only the assets read, and the mock is read only', () => {
    expect(reply('/api/v1/work/3909')[0]).toBe(404);
    expect(reply('/api/v1/work/3909/assets')[0]).toBe(404);
    expect(reply('/api/v1/work/3910')[0]).toBe(200);
    expect(reply('/api/v1/work/3910/assets')[0]).toBe(403);
    expect(reply('/api/v1/work/3901/assets', undefined, 'post')[0]).toBe(405);
    expect(ASSETS_PATH.test('/api/v1/work/3911/assets')).toBe(false);
  });
  it('a date proof is served only for a fact the read lists', () => {
    expect(reply('/api/v1/work/3905/assets/date-proofs/701')[0]).toBe(200);
    expect(reply('/api/v1/work/3905/assets/date-proofs/701')[2]?.['Content-Type']).toBe('application/pdf');
    expect(reply('/api/v1/work/3905/assets/date-proofs/999')[0]).toBe(404);
    expect(reply('/api/v1/work/3901/assets/date-proofs/701')[0]).toBe(404);
  });
});

describe('the mapper', () => {
  it('3901: stage, finding, 64 assets, 5 changes and the three unclear dates (AC1, AC2)', () => {
    const a = read(3901);
    expect(a.register!.assets).toHaveLength(64);
    const sections = assetsSections(a);
    expect(sections.find((s) => s.key === 'assets')!.items).toHaveLength(64);
    expect(sections.find((s) => s.key === 'events')!.items).toHaveLength(5);
    expect(sections.find((s) => s.key === 'unclear')!.items.map((i) => i.text)).toEqual(['FA-007 · Date unclear', 'FA-008 · Date unclear', 'FA-009 · Date unclear']);
    expect(sections.some((s) => s.key === 'schedule' || s.key === 'schedule-held')).toBe(false);
    draw(sections.filter((s) => s.key === 'stage'));
    expect(screen.getByText('Stage: Investigating')).toBeTruthy();
    expect(screen.getByText('Chidi is reading the register and checking the dates.')).toBeTruthy();
  });

  it('an asset is unclear when dates are absent or both are empty, and not when one date is given', () => {
    const base = read(3905).register!.assets[0];
    expect(isUnclear({ ...base, dates: undefined })).toBe(true);
    expect(isUnclear({ ...base, dates: { ...base.dates!, delivery_date: null, in_service_date: null } })).toBe(true);
    expect(isUnclear({ ...base, dates: { ...base.dates!, delivery_date: null } })).toBe(false);
  });

  it('dated assets read the basis in words (AC2)', () => {
    draw(assetsSections(read(3905)).filter((s) => s.key === 'dates'));
    expect(screen.getAllByText('Supplied fraction').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Reviewed in-service date')).toHaveLength(1);
  });

  it('null money reads Unknown, never 0 (AC4, AC5)', () => {
    const sections = assetsSections(read(3902));
    const assets = sections.find((s) => s.key === 'assets')!;
    expect(assets.items[0].cells!.find((c) => c.column === 'opening_cost')!.money).toEqual({ currency: 'NGN', unknown: true });
    const closing = sections.find((s) => s.key === 'closing')!;
    expect(closing.items.find((i) => i.id === 'book')!.money).toEqual({ currency: 'NGN', unknown: true });
    expect(closing.items.find((i) => i.id === 'accumulated')!.money!.unknown).toBe(true);
    expect(closing.items.find((i) => i.id === 'cost')!.money).toEqual({ amount: '1000000000.00', currency: 'NGN', unknown: false });
    expect(sections.find((s) => s.key === 'register')!.items.find((i) => i.id === 'completeness')!.value).toBe('Partial');
    draw(sections.filter((s) => s.key === 'assets' || s.key === 'closing'));
    expect(screen.getAllByText('Unknown').length).toBeGreaterThanOrEqual(5);
    expect(screen.queryAllByText(/^₦?0$/)).toEqual([]);
  });

  it('an amount is shown as sent: the residual "0.00" is a real zero, a null is not (AC4)', () => {
    draw(assetsSections(read(3902)).filter((s) => s.key === 'assets'));
    expect(screen.getAllByText('₦0.00').length).toBeGreaterThan(0);
  });

  it('held (3903): the reason is shown and no row or total is drawn as a figure (AC6)', () => {
    const sections = assetsSections(read(3903));
    expect(sections.some((s) => s.key === 'schedule' || s.key === 'totals')).toBe(false);
    expect(sections.find((s) => s.key === 'schedule-findings')!.items[0].text).toBe('The in-service date of one asset is unclear, so the charge is held.');
    draw(sections.filter((s) => s.key.startsWith('schedule')));
    expect(screen.getByText(/Held\./)).toBeTruthy();
  });

  it('ready (3905): rows, totals, scope and Posted to the ledger: No (AC5, AC6)', () => {
    const sections = assetsSections(read(3905));
    expect(sections.find((s) => s.key === 'schedule')!.items).toHaveLength(3);
    expect(sections.find((s) => s.key === 'totals')!.items.map((i) => i.money!.amount)).toEqual(['42003000.00', '8400000.00', '20400600.00', '21602700.00']);
    const scope = sections.find((s) => s.key === 'scope')!;
    expect(scope.items.find((i) => i.id === 'posted')!.value).toBe('No');
    expect(sections.find((s) => s.key === 'register')!.items.find((i) => i.id === 'native')!.value).toBe('No');
    expect(sections.find((s) => s.key === 'row-findings')!.items[0].text).toBe('FA-003: The disposal in June is part-year.');
  });

  it('calculating (3904): no schedule and "No review is open for you." (AC7)', () => {
    const sections = assetsSections(read(3904));
    expect(sections.some((s) => s.key.startsWith('schedule') || s.key === 'totals')).toBe(false);
    expect(sections.find((s) => s.key === 'reviews')!.items.map((i) => i.text)).toEqual(['No review is open for you.']);
  });

  it('review options are text only (AC8)', () => {
    draw(assetsSections(read(3905)).filter((s) => s.key === 'reviews'));
    expect(screen.getByText('Schedule review: Approve, Return')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('no register: the sentence and the finding (AC10)', () => {
    const sections = assetsSections(read(3908));
    expect(sections.find((s) => s.key === 'no-register')!.items[0].text).toBe('No register has been captured yet.');
    expect(sections.find((s) => s.key === 'stage')!.items.map((i) => i.text)).toContain('Waiting for the first register.');
    expect(sections.some((s) => s.key === 'assets' || s.key === 'closing')).toBe(false);
  });

  it('empty assets and events read their sentences', () => {
    const a = { ...read(3905), register: { ...read(3905).register!, assets: [], events: [] } };
    const sections = assetsSections(a);
    expect(sections.find((s) => s.key === 'assets')!.items[0].text).toBe('No assets in this register.');
    expect(sections.find((s) => s.key === 'events')!.items[0].text).toBe('No changes in this period.');
  });

  it('opening proof words and the returned case (AC7)', () => {
    expect(assetsSections(read(3905)).find((s) => s.key === 'proof')!.items.map((i) => i.text)).toEqual(['Opening proof attached']);
    expect(assetsSections(read(3907)).find((s) => s.key === 'proof')!.items.map((i) => i.text)).toEqual(['No opening proof attached', 'Returned for opening proof']);
  });
});

describe('the proof-link rule (AC3)', () => {
  it('lists only the fact ids the read carries, each with its asset; an id no asset cites is other', () => {
    expect(proofLinks(read(3905))).toEqual([
      { factId: 701, assetId: 'FA-001' },
      { factId: 702, assetId: 'FA-002' },
      { factId: 703, assetId: 'FA-003' },
    ]);
    expect(proofLinks({ ...read(3905), date_attachment_ids: [9999] })).toEqual([{ factId: 9999, assetId: null }]);
    expect(proofLinks(read(3901))).toEqual([]);
  });
});

describe('the error words (AC11, AC12)', () => {
  const err = (status: number, code: string) => errorFromResponse(status, { code, message: 'm' });
  it('404 and 403 read the same; csrf asks to refresh and press again; 503 is left to the frame', () => {
    expect(errorWords(err(404, 'not_found'))).toBe('This record is unavailable.');
    expect(errorWords(err(403, 'forbidden'))).toBe('This record is unavailable.');
    expect(errorWords(err(403, 'csrf_failed'))).toBe('Refresh your session and try again.');
    expect(errorWords(err(503, 'unavailable'))).toBeNull();
  });
});

describe('the adapter', () => {
  it('is registered for assets, has no commands and draws no write control (AC8, AC14)', () => {
    expect(adapterFor('assets')).toBe(assetsAdapter);
    expect(assetsAdapter.commands).toBeUndefined();
    expect(adapterFor('some-other-panel')).toBeUndefined();
    const src = readFileSync(join(__dirname, '../src/features/fixed-assets/labels.ts'), 'utf8') + readFileSync(join(__dirname, '../src/features/fixed-assets/AssetsActions.tsx'), 'utf8') + readFileSync(join(__dirname, '../src/features/fixed-assets/assetsAdapter.ts'), 'utf8');
    expect(src).not.toMatch(/liveApi\.POST|never reads asset values|MANAGEMENT ACCOUNTS/);
  });
});

describe('the page', () => {
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
  let scenario: string | undefined;
  let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
  const calls = (suffix: string) => fetchStub.mock.calls.filter(([r]) => new URL(r.url).pathname.endsWith(suffix)).length;

  beforeEach(() => {
    scenario = undefined;
    setCsrfToken('t');
    fetchStub = vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
      if (!ASSETS_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
      const [status, body] = assetsLive({ method: 'get', url, scenario, persona: 'finance_lead' }) as [number, unknown];
      return json(status, body);
    });
    vi.stubGlobal('fetch', fetchStub);
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });
  const open = (id: number) =>
    render(
      <ToastProvider>
        <LiveWorkItemView id={String(id)} tab="overview" />
      </ToastProvider>,
    );

  it('3905: proof links to the exact PDF routes and the accounting note as returned (AC3, AC9)', async () => {
    open(3905);
    const proofs = await screen.findAllByRole('link', { name: 'Open proof' });
    expect(proofs.map((a) => a.getAttribute('href'))).toEqual(['/api/v1/work/3905/assets/date-proofs/701', '/api/v1/work/3905/assets/date-proofs/702', '/api/v1/work/3905/assets/date-proofs/703']);
    expect(screen.getByRole('link', { name: 'Open accounting note' }).getAttribute('href')).toBe('https://notes.example.test/accounting-note/8');
    expect(screen.queryByRole('button', { name: /approve|return|reject|upload|correct/i })).toBeNull();
  });

  it('3906: one proof and no accounting note link and no placeholder (AC9)', async () => {
    open(3906);
    await screen.findAllByRole('link', { name: 'Open proof' });
    expect(screen.queryByText(/accounting note/i)).toBeNull();
  });

  it('3901: no proof links and no schedule', async () => {
    open(3901);
    await screen.findByText('Unclear dates');
    expect(screen.queryByRole('link', { name: 'Open proof' })).toBeNull();
    expect(screen.queryByText('Depreciation schedule')).toBeNull();
  });

  it('3910: the header stays and the panel reads "This record is unavailable." (AC11)', async () => {
    open(3910);
    expect(await screen.findByText('This record is unavailable.')).toBeTruthy();
    expect(screen.getByText('Fixed asset schedule for PSL Technologies')).toBeTruthy();
  });

  it('csrf_failed: not the no-access state; the session is refreshed once and the read is not repeated (AC12)', async () => {
    scenario = 'csrf_failed';
    open(3905);
    expect(await screen.findByText('Refresh your session and try again.')).toBeTruthy();
    expect(screen.queryByText('This record is unavailable.')).toBeNull();
    expect(calls('/assets')).toBe(1);
    expect(calls('/session')).toBe(1);
  });

  it('503 on the panel: the header stays and the read is not retried until pressed (AC13)', async () => {
    scenario = 'assets:503';
    open(3905);
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(screen.getByText('Fixed asset schedule for PSL Technologies')).toBeTruthy();
    await new Promise((r) => setTimeout(r, 100));
    expect(calls('/assets')).toBe(1);
    scenario = undefined;
    screen.getByRole('button', { name: 'Try again' }).click();
    await waitFor(() => expect(calls('/assets')).toBe(2));
    expect(await screen.findAllByRole('link', { name: 'Open proof' })).toHaveLength(3);
  });
});
