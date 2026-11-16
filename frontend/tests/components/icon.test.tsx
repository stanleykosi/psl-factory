// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Icon, ICON_NAMES } from '@/components';

import { violations } from './a11y';

describe('Icon', () => {
  it('has the whole design-system set, decorative, 2px square-capped strokes', async () => {
    expect(ICON_NAMES).toEqual([
      'plus', 'chev', 'chev-r', 'back', 'search', 'filter', 'close', 'check', 'warn', 'info', 'ok', 'cal', 'clip',
      'upload', 'more', 'menu', 'send', 'doc', 'lock', 'external', 'sort', 'down', 'bell',
    ]);
    const { container } = render(
      <>
        {ICON_NAMES.map((name) => (
          <Icon key={name} name={name} />
        ))}
      </>,
    );
    const svgs = [...container.querySelectorAll('svg')];
    expect(svgs).toHaveLength(ICON_NAMES.length);
    for (const svg of svgs) {
      expect(svg.getAttribute('class')).toBe('psl-icon');
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.getAttribute('stroke-width')).toBe('2');
      expect(svg.getAttribute('stroke-linecap')).toBe('square');
      expect(svg.getAttribute('viewBox')).toBe('0 0 18 18');
    }
    expect(svgs[ICON_NAMES.indexOf('sort')].getAttribute('width')).toBe('14');
    expect(svgs[0].getAttribute('width')).toBe('18');
    expect(await violations()).toEqual([]);
  });

  it('adds a class such as psl-chev', () => {
    const { container } = render(<Icon name="chev" className="psl-chev" />);
    expect(container.querySelector('svg')?.getAttribute('class')).toBe('psl-icon psl-chev');
  });
});
