import { describe, expect, it } from 'vitest';

import { buildTabQuery, isTabResponse } from '@/features/projects/tabsModel';

describe('request', () => {
  it('builds the request: limit always, q only when set, cursor for more', () => {
    expect(buildTabQuery({})).toEqual({ limit: 10 });
    expect(buildTabQuery({ q: 'a' }, 'o20')).toEqual({ limit: 10, q: 'a', cursor: 'o20' });
  });
});

describe('response check', () => {
  it('needs the typed array of the tab with well-formed rows; items alone is not enough', () => {
    expect(isTabResponse({ items: [{}], as_of: 'x' }, 'documents')).toBe(false);
    expect(isTabResponse({ documents: [] }, 'documents')).toBe(true);
    expect(isTabResponse({ documents: [{ title: 'x' }] }, 'documents')).toBe(false);
    expect(isTabResponse(null, 'documents')).toBe(false);
  });
});
