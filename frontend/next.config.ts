import type { NextConfig } from 'next';

// /api/v1 is same-origin for the browser. Locally it is proxied to the contract mock;
// FE-CONNECT-1 points API_ORIGIN at Django without a code change.
const apiOrigin = process.env.API_ORIGIN ?? 'http://127.0.0.1:4010';

const nextConfig: NextConfig = {
  // `next dev` blocks its dev resources for any host but localhost, so a page opened on
  // 127.0.0.1 never hydrates and stays on "Loading…". Loopback only; no effect on `next build`.
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    const api = { source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` };
    // D-155: the demo bar's Reset demo reaches the mock's reset endpoint; only when the dev script turns the demo on.
    const reset = { source: '/__mock/reset', destination: `${apiOrigin}/__mock/reset` };
    return process.env.NEXT_PUBLIC_MOCK_DEMO === '1' && process.env.NODE_ENV !== 'production' ? [api, reset] : [api];
  },
};

export default nextConfig;
