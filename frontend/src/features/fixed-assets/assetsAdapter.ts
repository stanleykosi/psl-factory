// F-102: the fixed asset schedule panel, read only (GET /work/{id}/assets), through the shared line adapter. The panel key is
// 'assets'. The proof and accounting-note links are drawn by AssetsActions (the Actions slot). Every write on this page (register
// capture, dates, opening proof, reviews) is F-102B: `commands()` is absent.
import { ApiError } from '@/api/errors';
import type { LiveAssets } from '@/api/types';
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';

import { AssetsActions } from './AssetsActions';
import { assetsSections, errorWords } from './labels';

/** The read, or the page's own words for a read that failed in a way the person can act on (401, 403, 404, 409, 422, csrf).
 *  Any other failure is thrown, so the shared panel frame shows its Try again. */
export type AssetsReadback = { assets: LiveAssets; error?: never } | { assets?: never; error: { words: string; signIn: boolean } };

export async function readAssets(ref: Parameters<typeof readPanel>[0]): Promise<AssetsReadback> {
  try {
    return { assets: await readPanel<LiveAssets>(ref) };
  } catch (e) {
    const words = e instanceof ApiError ? errorWords(e) : null;
    if (!(e instanceof ApiError) || words === null) throw e;
    return { error: { words, signIn: e.kind === 'unauthenticated' } };
  }
}

export function assetsReadSections(readback: AssetsReadback): Section[] {
  if (readback.error) return [{ key: 'error', kind: 'text', note: readback.error.words, items: [] }];
  return assetsSections(readback.assets);
}

export const assetsAdapter: LineAdapter<AssetsReadback> = {
  key: 'assets',
  read: readAssets,
  sections: (readback) => assetsReadSections(readback),
  Actions: AssetsActions,
};

registerLineAdapter(assetsAdapter as LineAdapter);
