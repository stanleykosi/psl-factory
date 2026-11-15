// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Panel } from '@/components';

import { violations } from './a11y';

describe('Panel', () => {
  it('draws the default, decision, agent, dark-head and read-only panels, named by their heads', async () => {
    render(
      <>
        <Panel head="Contract terms">Stage 2 of 4</Panel>
        <Panel kind="decide" head="Your decision">
          Approve invoice v3?
        </Panel>
        <Panel kind="agent" head="Chidi · Finance agent">
          Drafted v3.
        </Panel>
        <Panel head="Owed on this project" darkHead>
          2 invoices issued.
        </Panel>
        <Panel kind="readonly" head="Earlier version">
          v2 returned.
        </Panel>
      </>,
    );
    const decision = screen.getByRole('region', { name: 'Your decision' });
    expect(decision.className).toBe('psl-panel cmp-panelbox psl-panel--decide');
    expect(decision.querySelector('.psl-panel__head')?.className).toBe('psl-panel__head psl-panel__head--decide');
    expect(screen.getByRole('region', { name: 'Chidi · Finance agent' }).className).toContain('psl-panel--agent');
    expect(screen.getByRole('region', { name: 'Owed on this project' }).querySelector('.psl-panel__head--dark')).not.toBeNull();
    expect(screen.getByRole('region', { name: 'Earlier version' }).className).toContain('psl-panel--readonly');
    expect(await violations()).toEqual([]);
  });
});
