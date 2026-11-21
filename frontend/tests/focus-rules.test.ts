import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// D-143 / D-144: focus changes the control's own border (or an inset edge of the same width). No stylesheet in src sets
// an outline with the focus colour, and no stylesheet sets an outline-offset on a focus state.
const src = join(__dirname, '..', 'src');

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? cssFiles(path) : path.endsWith('.css') ? [path] : [];
  });
}

describe('focus is a border, never an outline', () => {
  const files = cssFiles(src);

  it('finds the stylesheets', () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it('no rule sets an outline with var(--focus) or var(--focus-on-strong)', () => {
    const found = files.flatMap((file) =>
      readFileSync(file, 'utf8')
        .split('\n')
        .filter((line) => /outline[^;}]*var\(--focus/.test(line))
        .map((line) => `${file.slice(src.length)}: ${line.trim().slice(0, 120)}`),
    );
    expect(found).toEqual([]);
  });

  it('no rule offsets an outline on a focus state', () => {
    const found = files.flatMap((file) =>
      readFileSync(file, 'utf8')
        .split('\n')
        .filter((line) => /:focus|\.is-focus/.test(line) && /outline-offset\s*:/.test(line))
        .map((line) => `${file.slice(src.length)}: ${line.trim().slice(0, 120)}`),
    );
    expect(found).toEqual([]);
  });
});
