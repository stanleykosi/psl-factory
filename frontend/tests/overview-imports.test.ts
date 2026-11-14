import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// three.js stays out of the Overview's first load: only features/floor/** may import it.
const src = join(__dirname, '../src');
const filesUnder = (dir: string): string[] =>
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? filesUnder(join(dir, e.name)) : [join(dir, e.name)]));

describe('overview imports', () => {
  const files = [...filesUnder(join(src, 'app/overview')), ...filesUnder(join(src, 'features/overview'))];

  it('scans the overview route and feature', () => {
    expect(files.length).toBeGreaterThanOrEqual(5);
  });

  for (const file of files) {
    it(`${file.slice(src.length + 1)} has no static three or Floor3D import`, () => {
      const text = readFileSync(file, 'utf8');
      expect(text).not.toMatch(/from\s+['"]three(\/[^'"]*)?['"]/);
      expect(text).not.toMatch(/from\s+['"]@\/features\/floor\/Floor3D['"]/);
      expect(text).not.toMatch(/features\/exceptions/);
    });
  }

  it('outside features/floor nothing imports three or Floor3D statically', () => {
    for (const file of filesUnder(src).filter((f) => !f.startsWith(join(src, 'features/floor')))) {
      const text = readFileSync(file, 'utf8');
      expect(text, file).not.toMatch(/from\s+['"]three(\/[^'"]*)?['"]/);
      expect(text, file).not.toMatch(/from\s+['"]@\/features\/floor\/(Floor3D|scene)['"]/);
    }
  });

  it('only Floor3D imports scene.ts, and support.ts has no three import', () => {
    const floor = join(src, 'features/floor');
    expect(readFileSync(join(floor, 'support.ts'), 'utf8')).not.toMatch(/['"]three['"]/);
    const importers = filesUnder(src).filter((f) => /from\s+['"](\.\/scene|@\/features\/floor\/scene)['"]/.test(readFileSync(f, 'utf8')));
    expect(importers).toEqual([join(floor, 'Floor3D.tsx')]);
  });
});
