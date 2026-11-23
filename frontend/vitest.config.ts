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
    // Keep test files isolated without launching a new Node subprocess for each file.
    pool: 'threads',
    maxWorkers: 2,
  },
});
