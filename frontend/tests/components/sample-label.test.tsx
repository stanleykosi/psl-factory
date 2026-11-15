// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SampleLabel } from '@/components';

import { violations } from './a11y';

describe('SampleLabel', () => {
  it('labels sample data, test templates and mock deliveries', async () => {
    const { container } = render(
      <>
        <SampleLabel />
        <SampleLabel kind="test" />
        <SampleLabel kind="mock" />
      </>,
    );
    expect([...container.querySelectorAll('.psl-sample')].map((s) => s.textContent)).toEqual(['SAMPLE DATA', 'TEST TEMPLATE', 'MOCK DELIVERY']);
    expect(await violations()).toEqual([]);
  });
});
