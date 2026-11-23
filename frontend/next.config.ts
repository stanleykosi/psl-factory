import type { NextConfig } from 'next';

// /api/v1 is same-origin for the browser. Locally it is proxied to the contract mock;
// FE-CONNECT-1 points API_ORIGIN at Django without a code change.
const apiOrigin = process.env.API_ORIGIN ?? 'http://127.0.0.1:4010';

const uuid = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';

// The authenticated file downloads. Django enforces session, permission and tenant on each; the proxy adds none,
// so only these exact paths are forwarded (with Django's trailing slash).
const downloads = [
  `/cases/:case(${uuid})/files/:upload(\\d+)`,
  `/projects/:case(${uuid})/templates/:template(\\d+)/file`,
  `/cases/:case(${uuid})/rfp/intake/:intake(\\d+)/attachment`,
  `/work/:work(\\d+)/invoice-proof/:proof(\\d+)`,
  `/cases/:case(${uuid})/finance/invoices/:issue(\\d+)/payments/:receipt(\\d+)/proof/:kind`,
  `/cases/:case(${uuid})/finance/reminders/:issue(\\d+)/drafts/:draft(\\d+)/:file_kind`,
];

const nextConfig: NextConfig = {
  // `next dev` blocks its dev resources for any host but localhost, so a page opened on
  // 127.0.0.1 never hydrates and stays on "Loading…". Loopback only; no effect on `next build`.
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    const beforeFiles = [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
    if (process.env.NEXT_PUBLIC_MOCK_DEMO === '1' && process.env.NODE_ENV !== 'production') {
      beforeFiles.push({ source: '/__mock/reset', destination: `${apiOrigin}/__mock/reset` });
    }
    // afterFiles: a real page always wins over a download rewrite.
    const afterFiles = downloads.map((source) => ({
      source,
      destination: `${apiOrigin}${source.replace(/\(.*?\)(?=\/|$)/g, '')}/`,
    }));
    return { beforeFiles, afterFiles, fallback: [] };
  },
};

export default nextConfig;
