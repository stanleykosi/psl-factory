import { expectTypeOf, it } from 'vitest';

import { call, liveApi } from '@/api/client';
import type { Me } from '@/api/types';

// Typecheck-only: these functions are never called, `npm run typecheck` checks them.
const loadMe = () => call(liveApi.GET('/api/v1/me'));
const wrongPath = () =>
  // @ts-expect-error '/api/v1/nope' is not an operation in the live contract
  liveApi.GET('/api/v1/nope');

it('the generated client types paths and responses', () => {
  expectTypeOf(loadMe).returns.resolves.toEqualTypeOf<Me>();
  expectTypeOf(wrongPath).toBeFunction();
});
