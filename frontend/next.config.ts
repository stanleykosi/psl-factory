import type { NextConfig } from 'next';

// /api/v1 is same-origin for the browser. Locally it is proxied to the contract mock;
// FE-CONNECT-1 points API_ORIGIN at Django without a code change.
const apiOrigin = process.env.API_ORIGIN ?? 'http://127.0.0.1:4010';

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
