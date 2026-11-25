import { join } from 'node:path';

// @ts-expect-error compiled module without type declarations
import { match } from 'next/dist/compiled/path-to-regexp';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { matchingSources } from './source-files';

const API = 'http://127.0.0.1:9999';
const CASE = '3f2b8c1e-1a4d-4c7e-9b0a-5d6e7f8a9b0c';

async function load(env: Record<string, string> = {}) {
  vi.resetModules();
  vi.stubEnv('API_ORIGIN', API);
  for (const [key, value] of Object.entries(env)) vi.stubEnv(key, value);
  const { default: config } = await import('../next.config');
  const rules = await config.rewrites!();
  if (Array.isArray(rules)) throw new Error('expected before/after/fallback rewrites');
  return { config, rules };
}

afterEach(() => vi.unstubAllEnvs());

describe('proxy rewrites', () => {
  it('forwards exactly the API and the six downloads, with no catch-all', async () => {
    const { config, rules } = await load();
    expect(rules.beforeFiles).toEqual([{ source: '/api/v1/:path*', destination: `${API}/api/v1/:path*` }]);
    expect(rules.afterFiles).toHaveLength(6);
    expect(rules.fallback ?? []).toEqual([]);
    expect('env' in config).toBe(false);
    for (const rule of [...(rules.beforeFiles as []), ...(rules.afterFiles as [])] as { source: string; destination: string }[]) {
      expect(rule.destination.startsWith(API)).toBe(true);
      expect(rule.source).not.toMatch(/^\/(:path\*|accounts|static|factory-forms|factory-assets)/);
    }
  });

  it('each of the six download rules has exactly this source and destination', async () => {
    const { rules } = await load();
    const U = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
    expect(rules.afterFiles).toEqual([
      { source: `/cases/:case(${U})/files/:upload(\\d+)`, destination: `${API}/cases/:case/files/:upload/` },
      { source: `/projects/:case(${U})/templates/:template(\\d+)/file`, destination: `${API}/projects/:case/templates/:template/file/` },
      { source: `/cases/:case(${U})/rfp/intake/:intake(\\d+)/attachment`, destination: `${API}/cases/:case/rfp/intake/:intake/attachment/` },
      { source: '/work/:work(\\d+)/invoice-proof/:proof(\\d+)', destination: `${API}/work/:work/invoice-proof/:proof/` },
      { source: `/cases/:case(${U})/finance/invoices/:issue(\\d+)/payments/:receipt(\\d+)/proof/:kind`, destination: `${API}/cases/:case/finance/invoices/:issue/payments/:receipt/proof/:kind/` },
      { source: `/cases/:case(${U})/finance/reminders/:issue(\\d+)/drafts/:draft(\\d+)/:file_kind`, destination: `${API}/cases/:case/finance/reminders/:issue/drafts/:draft/:file_kind/` },
    ]);
  });

  it('adds /__mock/reset only with the demo flag and outside production', async () => {
    const reset = (rules: { beforeFiles?: unknown }) => (rules.beforeFiles as { source: string }[]).filter((r) => r.source === '/__mock/reset');
    expect(reset((await load({ NEXT_PUBLIC_MOCK_DEMO: '' })).rules)).toHaveLength(0);
    expect(reset((await load({ NEXT_PUBLIC_MOCK_DEMO: '1', NODE_ENV: 'development' })).rules)).toHaveLength(1);
    expect(reset((await load({ NEXT_PUBLIC_MOCK_DEMO: '1', NODE_ENV: 'production' })).rules)).toHaveLength(0);
  });

  it('each download pattern takes its route and refuses near misses', async () => {
    const { rules } = await load();
    const sources = (rules.afterFiles as { source: string; destination: string }[]).map((r) => r.source);
    const matchers = sources.map((source) => match(source, { decode: decodeURIComponent }));
    const good = [
      `/cases/${CASE}/files/12`,
      `/projects/${CASE}/templates/12/file`,
      `/cases/${CASE}/rfp/intake/12/attachment`,
      `/work/12/invoice-proof/12`,
      `/cases/${CASE}/finance/invoices/12/payments/12/proof/bank`,
      `/cases/${CASE}/finance/reminders/12/drafts/12/pdf`,
    ];
    good.forEach((path, i) => expect(matchers[i](path), path).not.toBe(false));
    const bad = [
      '/cases/not-a-uuid/files/1',
      `/cases/${CASE}/files/abc`,
      `/cases/${CASE}/files/1/extra`,
      `/work/x/invoice-proof/1`,
      `/finance/followup-inbox/${CASE}/key`,
      '/health',
      '/accounts/login',
      '/static/x.js',
    ];
    for (const path of bad) matchers.forEach((m) => expect(m(path), path).toBe(false));
    // Each is reached only by its own route.
    good.forEach((path, i) => matchers.forEach((m, j) => j !== i && expect(m(path)).toBe(false)));
  });

  it('keeps the trailing slash Django requires on every download destination', async () => {
    const { rules } = await load();
    for (const rule of rules.afterFiles as { destination: string }[]) {
      expect(rule.destination).toMatch(/\/$/);
      expect(rule.destination).not.toMatch(/[()\\]/);
    }
  });

  it('shadows no app route', async () => {
    const { rules } = await load();
    const matchers = (rules.afterFiles as { source: string }[]).map((r) => match(r.source, { decode: decodeURIComponent }));
    const pages = ['/work/12', '/work/12/history', '/work/12/decide', '/work/12/outcome', '/work/12/respond', '/projects', `/projects/${CASE}`, `/projects/${CASE}/documents/5`, `/projects/${CASE}/anything`];
    for (const page of pages) matchers.forEach((m) => expect(m(page), page).toBe(false));
  });
});

describe('the Django embed is gone', () => {
  it('no source mentions the removed pieces', () => {
    const root = join(__dirname, '..');
    const removed = new RegExp(['FactoryDesk', 'work_desk_url', 'django_url', 'factory-forms', 'factory-assets', 'NEXT_PUBLIC_FACTORY_ORIGIN'].join('|'));
    const hits = matchingSources(['src', 'tests', 'e2e', 'mock'].map((d) => join(root, d)), removed);
    // The live contract itself and its generated types name these fields (the frame reads `/me` and ignores them); the mock's `/me` fixtures hold the fixed /retired/ value and tests/mock-live-me.test.ts proves their shape; the project list and journey fixtures carry the contract's required django_url, never read (tests/mock-live-projects.test.ts proves their shape). mock/work-live.mjs and mock/issues.mjs serve the live work item, whose required `django_url` field they must carry (F-85, F-111). The document review fixtures carry the contract's required django_url too (F-72, tests/mock-live-document-review.test.ts). The alerts adapter (F-61) reads `django_url` only as the fallback link of an alert with no typed `api_url` (the contract names it on every alert item), and its mock and tests carry the field. The decision desk's typed work fixtures and its mock (decide.test.tsx, live-decide.mjs) carry the same required django_url. The project money and milestones fixtures carry the same field (F-71). The clients mock carries the required django_url of a workspace (F-73).
    const allowed = [
      'next-config.test.ts',
      'shell-no-embed.test.tsx',
      'live-schema.d.ts',
      'shell-live.test.tsx',
      'client.test.ts',
      'destinations.ts',
      'mock-live-me.test.ts',
      'projects-journey.test.tsx',
      'demo-projects.mjs',
      'work-live.mjs',
      'received-bids.mjs',
      'LineChooser.tsx',
      'start-live.mjs',
      'start-work-live.test.tsx',
      'start-work-engine-ui.test.tsx',
      'document-review.test.tsx',
      'document-review-model.test.ts',
      'documents/review-2901.json',
      'money-model.test.ts',
      'milestones-model.test.ts',
      'decide.test.tsx',
      'live-decide.mjs',
      'features/alerts/model.ts',
      'mock/alerts.mjs',
      'alerts-helpers.ts',
      'alerts-model.test.ts',
      'alerts.test.tsx',
      'alerts-bell.test.tsx',
      'demo-mock.test.ts',
      'project-sections-model.test.ts',
      'issues.mjs',
      'forecast-live.mjs',
      'engagement-live.mjs',
      'clients.mjs',
      'clients-mock.test.ts',
      'bid-pack-live.mjs',
      'commercial-live.mjs',
    ];
    expect(hits.filter((file) => !allowed.some((name) => file.endsWith(name)) && !/mock\/fixtures\/me\.[a-z_]+\.json$/.test(file) && !/mock\/fixtures\/(projects\/(money\/|tabs\/)?[^/]+|E-PROJECT)\.json$/.test(file))).toEqual([]);
  });
});
