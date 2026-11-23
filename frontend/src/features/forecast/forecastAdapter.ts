// F-103: the cash forecast panel, read only (GET /work/{id}/forecast), through the shared line adapter. The panel key is
// 'forecast' (the work item lists it with 'forecast/disclosure' and 'forecast/lifecycle', which are write routes and have no
// adapter). Every write on this panel (review, withdraw, post, match, disclosure, observation, retry) is F-103B: `commands()` is absent.
import { ApiError } from '@/api/errors';
import type { LiveForecast } from '@/api/types';
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';

import { ForecastExtra } from './ForecastExtra';
import { errorWords, forecastSections } from './labels';

/** The read, or the page's own words for a read that failed in a way the person can act on (401, 403, 404, 409, 422).
 *  Any other failure is thrown, so the shared panel frame shows its Try again. */
export type ForecastReadback = { forecast: LiveForecast; error?: never } | { forecast?: never; error: { words: string; signIn: boolean } };

export async function readForecast(ref: Parameters<typeof readPanel>[0]): Promise<ForecastReadback> {
  try {
    return { forecast: await readPanel<LiveForecast>(ref) };
  } catch (e) {
    const words = e instanceof ApiError ? errorWords(e) : null;
    if (!(e instanceof ApiError) || words === null) throw e;
    return { error: { words, signIn: e.kind === 'unauthenticated' } };
  }
}

export function forecastReadSections(readback: ForecastReadback): Section[] {
  if (readback.error) return [{ key: 'error', kind: 'text', note: readback.error.words, items: [] }];
  return forecastSections(readback.forecast);
}

export const forecastAdapter: LineAdapter<ForecastReadback> = {
  key: 'forecast',
  read: readForecast,
  sections: (readback) => forecastReadSections(readback),
  Extra: ForecastExtra,
};

registerLineAdapter(forecastAdapter as LineAdapter);
