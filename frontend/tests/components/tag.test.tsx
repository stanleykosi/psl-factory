// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PriorityTag, STATE_TAGS, StateTag, Tag, type FactoryState } from '@/components';

import { violations } from './a11y';

// The README's state words, in its order, plus the stopped follow-up state CMP-05 lists.
const README_WORDS = [
  'Ready to continue', 'Processing', 'Waiting', 'Awaiting Finance decision', 'Owner needed', 'Setup needed', 'Action needed',
  'Effect uncertain', 'Awaiting reconciliation', 'Verified', 'Cancellation requested', 'Cancelled', 'Stopped: invoice follow-up needed',
];

describe('StateTag and Tag', () => {
  it('uses only the README state words, never Done or Complete', () => {
    const words = Object.values(STATE_TAGS).map((t) => t.text);
    expect(words).toEqual(README_WORDS);
    expect(words.some((w) => /^(done|complete)/i.test(w))).toBe(false);
  });

  it('one colour family per state; Effect uncertain is amber (D-92)', () => {
    const tone = (s: FactoryState) => STATE_TAGS[s].tone;
    expect(tone('effect_uncertain')).toBe('waiting');
    expect(tone('processing')).toBe('agent');
    expect(tone('verified')).toBe('done');
    expect(tone('cancelled')).toBe('neutral');
    expect(tone('action_needed')).toBe('person');
    expect(new Set(Object.values(STATE_TAGS).map((t) => t.tone))).toEqual(new Set(['person', 'waiting', 'agent', 'done', 'neutral']));
  });

  it('renders the words in the bundle tag classes', async () => {
    render(
      <>
        <StateTag state="effect_uncertain" />
        <Tag tone="agent" pulse>
          WORKING
        </Tag>
        <PriorityTag priority="medium" />
      </>,
    );
    expect(screen.getByText('Effect uncertain').className).toBe('psl-tag psl-tag--waiting');
    const working = screen.getByText('WORKING');
    expect(working.querySelector('.psl-pulse.psl-now')?.getAttribute('aria-hidden')).toBe('true');
    const prio = screen.getByText('Medium');
    expect(prio.className).toBe('psl-tag psl-tag--neutral');
    expect(prio.querySelector('.psl-prio')?.textContent).toBe('■■□');
    expect(await violations()).toEqual([]);
  });
});
