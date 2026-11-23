import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { expect, it } from 'vitest';

const root = join(__dirname, '..');
const LIVE_SOURCE = join(root, '../contracts/psl-factory.openapi.json');

it('src/api/live-schema.d.ts equals openapi-typescript output for the live contract', () => {
  const dir = mkdtempSync(join(tmpdir(), 'psl-live-schema-'));
  try {
    const out = join(dir, 'live-schema.d.ts');
    execFileSync(process.execPath, [join(root, 'node_modules/openapi-typescript/bin/cli.js'), LIVE_SOURCE, '-o', out]);
    expect(readFileSync(join(root, 'src/api/live-schema.d.ts'), 'utf8')).toBe(readFileSync(out, 'utf8'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

it('gen:api:live reads the same contract file the mock tests validate against', () => {
  const script = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).scripts['gen:api:live'] as string;
  const source = script.match(/openapi-typescript\s+(\S+)/)![1];
  expect(resolve(root, source)).toBe(resolve(LIVE_SOURCE));
  expect(readFileSync(join(__dirname, 'mock-live-me.test.ts'), 'utf8')).toContain("'../../contracts/psl-factory.openapi.json'");
});
