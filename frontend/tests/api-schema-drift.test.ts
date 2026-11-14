import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';

const root = join(__dirname, '..');
const DRIFT_SOURCE = join(root, '../architecture/packages/v7/openapi.json');

it('src/api/schema.d.ts equals openapi-typescript output for the v7 openapi.json', () => {
  const dir = mkdtempSync(join(tmpdir(), 'psl-schema-'));
  try {
    const out = join(dir, 'schema.d.ts');
    execFileSync(process.execPath, [
      join(root, 'node_modules/openapi-typescript/bin/cli.js'),
      DRIFT_SOURCE,
      '-o',
      out,
    ]);
    expect(readFileSync(join(root, 'src/api/schema.d.ts'), 'utf8')).toBe(readFileSync(out, 'utf8'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

it('gen:api, the drift test and the mock all read the same openapi.json', () => {
  const genApi = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).scripts['gen:api'] as string;
  const genSource = genApi.match(/openapi-typescript\s+(\S+)/)![1];
  expect(resolve(root, genSource)).toBe(resolve(DRIFT_SOURCE));
  expect(resolve(OPENAPI_PATH)).toBe(resolve(DRIFT_SOURCE));
});
