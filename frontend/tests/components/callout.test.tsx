// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Callout } from '@/components';

import { violations } from './a11y';

describe('Callout', () => {
  it('each kind has its tint, its leading icon, and the role the spec gives it', async () => {
    const { container } = render(
      <>
        <Callout kind="info">Approving does not send the invoice.</Callout>
        <Callout kind="warning">The client has not replied for 5 days.</Callout>
        <Callout kind="problem">Can’t send yet.</Callout>
        <Callout kind="success">Payment recorded.</Callout>
      </>,
    );
    const boxes = [...container.querySelectorAll('.psl-callout')];
    expect(boxes.map((b) => b.className)).toEqual([
      'psl-callout psl-callout--info',
      'psl-callout psl-callout--warning',
      'psl-callout psl-callout--problem',
      'psl-callout psl-callout--success',
    ]);
    expect(boxes.map((b) => b.getAttribute('role'))).toEqual([null, null, 'alert', 'status']);
    for (const box of boxes) expect(box.firstElementChild?.tagName.toLowerCase()).toBe('svg');
    expect(await violations()).toEqual([]);
  });

  it('a problem that is part of the page as loaded is not announced', () => {
    render(<Callout kind="problem" announce={false}>No billing contact.</Callout>);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('takes focus when it appears with focusOnShow', () => {
    render(
      <Callout kind="problem" focusOnShow>
        Fix the amount.
      </Callout>,
    );
    expect(document.activeElement).toBe(screen.getByRole('alert'));
    expect(screen.getByRole('alert').getAttribute('tabindex')).toBe('-1');
  });
});
