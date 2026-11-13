import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM script without type declarations
import { buildBundleCss, buildTokensCss, outputPaths, readDesignSources } from '../scripts/gen-styles.mjs';

const root = join(__dirname, '..');

describe('design system styles have a single source', () => {
  const { tokens, bundle } = readDesignSources();
  const tokensCss = readFileSync(outputPaths.tokens, 'utf8');
  const bundleCss = readFileSync(outputPaths.bundle, 'utf8');

  it('committed tokens.css and psl-bundle.css equal a fresh generation', () => {
    expect(tokensCss).toBe(buildTokensCss(tokens));
    expect(bundleCss).toBe(buildBundleCss(bundle));
  });

  it('psl-bundle.css is bundle.css minus only the font import line and the preview helpers', () => {
    const [firstLine] = bundle.split('\n');
    const tail = bundle.slice(bundle.indexOf('/* ---------- preview-only layout helpers'));
    expect(firstLine).toMatch(/^@import url\('https:\/\/fonts\.googleapis\.com\//);
    expect(tail).toMatch(/^[^\n]*\n(\.ds[^\n]*\n?)+$/);
    expect(`${firstLine}\n${bundleCss}${tail}`).toBe(bundle);
  });

  it('every var(--x) used by psl-bundle.css is defined in tokens.css', () => {
    const defined = new Set([...tokensCss.matchAll(/^\s*(--[\w-]+):/gm)].map((m) => m[1]));
    const used = new Set([...bundleCss.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]));
    expect(used.size).toBeGreaterThan(40);
    expect([...used].filter((name) => !defined.has(name))).toEqual([]);
  });

  it('psl-bundle.css loads no Google Fonts and has no preview-only .ds selectors', () => {
    expect(bundleCss).not.toContain('fonts.googleapis.com');
    expect(bundleCss).not.toMatch(/\.ds[-\s{,]/);
  });

  it('shell.css uses token variables only and the frame has no literal colours', () => {
    const shellCss = readFileSync(join(root, 'src/styles/shell.css'), 'utf8');
    expect(shellCss).not.toMatch(/#[0-9A-Fa-f]{3,6}\b|rgba?\(|hsla?\(/);
    let out = '';
    try {
      out = execFileSync('grep', ['-rnE', '#[0-9A-Fa-f]{3,6}\\b', 'src', '--include=*.css', '--include=*.tsx'], { cwd: root, encoding: 'utf8' });
    } catch {
      out = '';
    }
    const offending = out
      .split('\n')
      .filter(Boolean)
      .filter((line) => !line.startsWith('src/styles/tokens.css:') && !line.startsWith('src/styles/psl-bundle.css:'));
    expect(offending).toEqual([]);
  });
});
