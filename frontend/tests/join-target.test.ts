import { describe, expect, it } from 'vitest';

import { signInTarget } from '@/features/join/signInTarget';

describe('the sign-in target after set-up', () => {
  it.each([
    '/sign-in',
    '/accounts/login/',
    'https://evil.example',
    '//evil.example',
    '/sign-in?next=https%3A%2F%2Fevil.example',
    '/sign-in/',
    '/Sign-In',
    '/sign-in/../accounts/login/',
    '/sign-in?other=%2Fsettings%2Falerts',
    '/sign-in?next=%2Fsettings%2Falerts&other=1',
    '/sign-in?next=%2Fsettings%2Falerts&next=%2F',
    '/sign-in?next=%2F%2Fevil.example',
    '/sign-in?next=%2Fsign-in',
    '/sign-in?next=%252Fsettings',
    '/sign-in?next=',
    '/sign-in?next=%2Fsettings%2Falerts?x=1?',
    ' /sign-in?next=%2Fsettings%2Falerts',
    'https://evil.example/sign-in?next=%2Fsettings%2Falerts',
    '/sign-in#x',
    undefined,
    null,
    42,
  ])('%s gives plain /sign-in', (value) => {
    expect(signInTarget(value)).toBe('/sign-in');
  });

  it('keeps one safe next', () => {
    expect(signInTarget('/sign-in?next=%2Fsettings%2Falerts')).toBe('/sign-in?next=%2Fsettings%2Falerts');
  });
});
