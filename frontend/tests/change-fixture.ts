// F-112: the change read of a mock fixture, for the model tests (no page).
import type { Change } from '@/features/change-request/changeModel';

// @ts-expect-error plain ESM module without type declarations
import { changeLive } from '../mock/change-live.mjs';

export const start = (id: number): Change => {
  const [, body] = changeLive({ method: 'get', url: new URL(`http://mock/api/v1/work/${id}/change`), scenario: undefined, csrfOk: true, persona: 'finance_lead' }) as [number, Change];
  return body;
};
