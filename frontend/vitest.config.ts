import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    include: ['tests/**/*.test.{ts,tsx}'],
    environment: 'node',
    setupFiles: ['tests/setup.ts'],
    testTimeout: 30000,
    // Under machine load, setup hooks (starting the mock server, first render) can exceed the 10 s default.
    hookTimeout: 60000,
    // 8 GB / 8-core machine: the default (cores - 1) jsdom workers starve memory when two runs overlap
    // ("Failed to start forks worker"). Four keeps a full run reliable at the cost of a little time.
    maxWorkers: 4,
  },
});
