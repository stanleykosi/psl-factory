// Local development: the contract mock on 127.0.0.1:MOCK_PORT (default 4010) plus `next dev`.
// Extra arguments go to next dev (for example `npm run dev -- -p 3101`). Ctrl-C stops both.
import { spawn } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const mockPort = process.env.MOCK_PORT ?? '4010';
const apiOrigin = process.env.API_ORIGIN ?? `http://127.0.0.1:${mockPort}`;
// D-155: the live demo of the mock (answer delay, runs, the demo bar). Only here, and only against the mock: never in a build or against a real backend.
const demo = apiOrigin === `http://127.0.0.1:${mockPort}` ? { MOCK_DEMO: '1', NEXT_PUBLIC_MOCK_DEMO: '1' } : {};
const env = { ...process.env, ...demo, MOCK_PORT: mockPort, API_ORIGIN: apiOrigin };

const children = [
  spawn(process.execPath, [join(root, 'mock', 'server.mjs')], { cwd: root, env, stdio: 'inherit' }),
  spawn(process.execPath, [join(root, 'node_modules', 'next', 'dist', 'bin', 'next'), 'dev', ...process.argv.slice(2)], {
    cwd: root,
    env,
    stdio: 'inherit',
  }),
];

let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
  process.exitCode = code;
}

for (const child of children) child.on('exit', (code) => stop(code ?? 0));
process.on('SIGINT', () => stop(0));
process.on('SIGTERM', () => stop(0));
