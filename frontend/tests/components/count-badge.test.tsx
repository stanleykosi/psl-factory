// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CountBadge } from '@/components';

import { violations } from './a11y';

describe('CountBadge', () => {
  it('shows 0 rather than hiding, in the three tones', async () => {
    const { container } = render(
      <>
        <CountBadge count={0} />
        <CountBadge count={4} tone="onDark" />
        <CountBadge count={2} tone="signal" />
      </>,
    );
    const badges = [...container.querySelectorAll('span')];
    expect(badges.map((b) => [b.className, b.textContent])).toEqual([
      ['psl-badge', '0'],
      ['psl-badge psl-badge--on-dark', '4'],
      ['psl-badge psl-badge--signal', '2'],
    ]);
    expect(await violations()).toEqual([]);
  });
});
