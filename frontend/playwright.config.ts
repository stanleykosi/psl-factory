import { defineConfig, devices } from '@playwright/test';

// Browser accessibility run: builds the app, starts the contract mock and `next start`.
const appPort = Number(process.env.E2E_PORT ?? 3101);
const mockPort = Number(process.env.MOCK_PORT ?? 3102);

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: `http://localhost:${appPort}`, ...devices['Desktop Chrome'] },
  webServer: [
    {
      command: 'node mock/server.mjs',
      env: { MOCK_PORT: String(mockPort) },
      url: `http://127.0.0.1:${mockPort}/api/v1/me`,
      reuseExistingServer: false,
    },
    {
      command: `npm run build && npx next start -p ${appPort}`,
      env: { API_ORIGIN: `http://127.0.0.1:${mockPort}`, NEXT_TELEMETRY_DISABLED: '1', FRAME_FIXTURES: '1' },
      url: `http://localhost:${appPort}/my-work`,
      timeout: 300_000,
      reuseExistingServer: false,
    },
  ],
});
