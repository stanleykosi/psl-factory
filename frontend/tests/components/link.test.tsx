// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Link, RestrictedLink } from '@/components';

import { violations } from './a11y';

describe('Link', () => {
  it('draws the reading and quiet links, and a restricted record with a lock, never hidden', async () => {
    render(
      <p>
        <Link href="/sow/31">the signed SOW</Link> <Link href="/projects/1" quiet>Lagoon Health · patient app</Link>{' '}
        <RestrictedLink>Payroll batch · restricted</RestrictedLink>
      </p>,
    );
    expect(screen.getByRole('link', { name: 'the signed SOW' }).className).toBe('psl-link');
    expect(screen.getByRole('link', { name: 'Lagoon Health · patient app' }).className).toBe('psl-link psl-link--quiet');
    const restricted = screen.getByText('Payroll batch · restricted');
    expect(restricted.className).toBe('psl-link is-restricted cmp-restricted');
    expect(restricted.querySelector('svg')).not.toBeNull();
    expect(screen.queryByRole('link', { name: /Payroll/ })).toBeNull();
    expect(await violations()).toEqual([]);
  });
});
