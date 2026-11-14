import { afterEach, describe, expect, it, vi } from 'vitest';

import PhoneBackFixturePage from '@/app/frame-fixtures/phone-back/page';

const notFound = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND');
  }),
);
vi.mock('next/navigation', () => ({ notFound }));

afterEach(() => {
  vi.unstubAllEnvs();
  notFound.mockClear();
});

describe('frame fixture pages are closed unless the server opts in', () => {
  it('the phone back-link fixture is a 404 without FRAME_FIXTURES=1', () => {
    vi.stubEnv('FRAME_FIXTURES', '');
    expect(() => PhoneBackFixturePage()).toThrow('NEXT_NOT_FOUND');
    vi.stubEnv('FRAME_FIXTURES', 'true');
    expect(() => PhoneBackFixturePage()).toThrow('NEXT_NOT_FOUND');
    expect(notFound).toHaveBeenCalledTimes(2);
  });

  it('renders the fixture with FRAME_FIXTURES=1', () => {
    vi.stubEnv('FRAME_FIXTURES', '1');
    expect(PhoneBackFixturePage()).toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  });
});
