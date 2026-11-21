import type { NextConfig } from 'next';

// /api/v1 is same-origin for the browser. Locally it is proxied to the contract mock;
// FE-CONNECT-1 points API_ORIGIN at Django without a code change.
const apiOrigin = process.env.API_ORIGIN ?? 'http://127.0.0.1:4010';

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_FACTORY_ORIGIN: process.env.NEXT_PUBLIC_FACTORY_ORIGIN ?? '' },
  // `next dev` blocks its dev resources for any host but localhost, so a page opened on
  // 127.0.0.1 never hydrates and stays on "Loading…". Loopback only; no effect on `next build`.
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    return { beforeFiles: [
      { source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` },
      { source: '/factory-assets/work-client.js', destination: `${apiOrigin}/static/factory-work-client.js` },
      { source: '/accounts/:path*', destination: `${apiOrigin}/accounts/:path*` },
      { source: '/factory-forms/:path*', destination: `${apiOrigin}/:path*` },
      { source: '/static/:path*', destination: `${apiOrigin}/static/:path*` },
    ], afterFiles: [], fallback: [{ source: '/:path*', destination: `${apiOrigin}/:path*` }] };
  },
};

export default nextConfig;
