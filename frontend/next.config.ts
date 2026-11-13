import type { NextConfig } from 'next';

// /api/v1 is same-origin for the browser. Locally it is proxied to the contract mock;
// FE-CONNECT-1 points API_ORIGIN at Django without a code change.
const apiOrigin = process.env.API_ORIGIN ?? 'http://127.0.0.1:4010';

const nextConfig: NextConfig = {
  // `next dev` blocks its dev resources for any host but localhost, so a page opened on
  // 127.0.0.1 never hydrates and stays on "Loading…". Loopback only; no effect on `next build`.
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
