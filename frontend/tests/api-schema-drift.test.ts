import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { expect, it } from 'vitest';

const root = join(__dirname, '..');

it('src/api/schema.d.ts equals openapi-typescript output for the v6 openapi.json', () => {
  const dir = mkdtempSync(join(tmpdir(), 'psl-schema-'));
  try {
    const out = join(dir, 'schema.d.ts');
    execFileSync(process.execPath, [
      join(root, 'node_modules/openapi-typescript/bin/cli.js'),
      join(root, '../architecture/packages/v6/openapi.json'),
      '-o',
      out,
    ]);
    expect(readFileSync(join(root, 'src/api/schema.d.ts'), 'utf8')).toBe(readFileSync(out, 'utf8'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
