import { expectTypeOf, it } from 'vitest';

import { api, call } from '@/api/client';
import type { Me } from '@/api/types';

// Typecheck-only: these functions are never called, `npm run typecheck` checks them.
const loadMe = () => call(api.GET('/api/v1/me'));
const wrongPath = () =>
  // @ts-expect-error '/api/v1/nope' is not an operation in openapi.json
  api.GET('/api/v1/nope');

it('the generated client types paths and responses', () => {
  expectTypeOf(loadMe).returns.resolves.toEqualTypeOf<Me>();
  expectTypeOf(wrongPath).toBeFunction();
});
