import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { describe, expect, it } from 'vitest';

// D-151: what a just-finished action did is a toast (useToast), never a success Callout. A success callout is only for the
// lasting state of a record. Each allowed file says why; a new one needs a reason here.
const ALLOWED: Record<string, string> = {
  'src/features/decide/DecideStates.tsx': 'the next-step card on the decided page: a lasting statement about what follows for the record, not the result of the press (that is the "Your decision was recorded." toast)',
};
const SUCCESS = /kind="success"|kind=\{[^}]*'success'|callout--success|callout--\$\{[^}]*success/;

const files = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.tsx$/.test(name) ? [path] : [];
  });

describe('no success callouts for an action result', () => {
  const root = join(__dirname, '..');
  const found = files(join(root, 'src'))
    .filter((file) => SUCCESS.test(readFileSync(file, 'utf8')))
    .map((file) => relative(root, file));

  it('renders a success callout only in the allowlisted files', () => {
    expect(found.filter((file) => !(file in ALLOWED))).toEqual([]);
  });

  it('keeps the allowlist honest: every entry still has one', () => {
    expect(Object.keys(ALLOWED).filter((file) => !found.includes(file))).toEqual([]);
  });
});
