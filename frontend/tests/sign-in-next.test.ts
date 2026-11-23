import { describe, expect, it } from 'vitest';

import { safeNext } from '@/shell/signInNext';

describe('safeNext: only a page of this app, never another place', () => {
  it.each([
    'https://evil.example',
    'https://evil.example/my-work',
    '//evil.example',
    '///evil.example',
    '/\\evil.example',
    '\\\\evil.example',
    '/my-work\\..\\evil',
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    ' /my-work',
    '/my-work ',
    '\t/my-work',
    '/my-work\n/evil',
    '/my-work\r',
    '/my-work\u0000',
    '/%2F%2Fevil.example',
    '/%2f%2fevil.example',
    '/my-work%0d%0aSet-Cookie:x=1',
    '/%5Cevil.example',
    '/my-work/%2e%2e/api/v1/me',
    '/my-work/../api/v1/me',
    '/my-work/./../../accounts/login/',
    '/projects/..',
    '/api/v1/me',
    '/api',
    '/accounts/login/',
    '/accounts/recovery/link/',
    '/getting-started/',
    '/sign-in',
    '/sign-in?next=/my-work',
    '/staff/join/',
    '/MY-WORK',
    '/my-workshop',
    '/%',
    '/my-work%',
    'my-work',
    '',
    '?next=/my-work',
    `/my-work/${'a'.repeat(2048)}`,
    null,
    undefined,
    42,
    ['/my-work'],
    {},
  ])('rejects %j', (value) => {
    expect(safeNext(value)).toBeNull();
  });

  it.each(['/', '/my-work', '/my-work/', '/projects/P-0101?tab=money', '/projects/P-0101/money#top', '/clients', '/work/W-1001', '/exceptions', '/finance/month-end?period=2026-10', '/notifications?q=pay', '/settings/alerts', '/setup/rules', '/overview', '/assistant', '/projects?q=a%20b'])(
    'accepts %s unchanged',
    (value) => {
      expect(safeNext(value)).toBe(value);
    },
  );

  it('accepts a value of exactly 2048 characters and rejects one more', () => {
    const exact = `/my-work?q=${'a'.repeat(2048 - '/my-work?q='.length)}`;
    expect(exact).toHaveLength(2048);
    expect(safeNext(exact)).toBe(exact);
    expect(safeNext(`${exact}a`)).toBeNull();
  });
});
