// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Segmented, Tabs } from '@/components';

import { violations } from './a11y';

function Period() {
  const [value, setValue] = useState<'week' | 'month' | 'quarter' | 'year'>('week');
  return (
    <Segmented
      label="Period"
      value={value}
      onChange={setValue}
      options={[
        { value: 'week', label: 'Week', count: 0 },
        { value: 'month', label: 'Month', count: 4 },
        { value: 'quarter', label: 'Quarter', disabled: true },
        { value: 'year', label: 'Year' },
      ]}
    />
  );
}

describe('Segmented', () => {
  it('one tab stop; arrows move and choose, skipping disabled; Home/End; counts as badges, 0 shown', async () => {
    render(<Period />);
    const group = screen.getByRole('radiogroup', { name: 'Period' });
    expect(group.className).toBe('psl-seg');
    const [week, month, quarter, year] = screen.getAllByRole('radio');
    expect(week.querySelector('.psl-badge')?.textContent).toBe('0');
    expect([week, month, quarter, year].map((r) => r.getAttribute('tabindex'))).toEqual(['0', '-1', '-1', '-1']);
    expect(quarter.getAttribute('aria-disabled')).toBe('true');
    expect(await violations()).toEqual([]);
    week.focus();
    fireEvent.keyDown(week, { key: 'ArrowRight' });
    expect(month.getAttribute('aria-checked')).toBe('true');
    fireEvent.keyDown(month, { key: 'ArrowRight' });
    expect(year.getAttribute('aria-checked')).toBe('true');
    expect(document.activeElement).toBe(year);
    fireEvent.keyDown(year, { key: 'Home' });
    expect(week.getAttribute('aria-checked')).toBe('true');
    fireEvent.keyDown(week, { key: 'End' });
    expect(year.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(quarter);
    expect(quarter.getAttribute('aria-checked')).toBe('false');
  });
});

function Sections() {
  const [tab, setTab] = useState<'journey' | 'milestones' | 'money'>('journey');
  return (
    <>
      <Tabs
        label="Project"
        selected={tab}
        onSelect={setTab}
        panelId="panel"
        tabs={[
          { key: 'journey', label: 'Journey' },
          { key: 'milestones', label: 'Milestones', count: 4 },
          { key: 'money', label: 'Money', count: 0 },
        ]}
      />
      <div id="panel" role="tabpanel" aria-label={tab}>
        {tab}
      </div>
    </>
  );
}

describe('Tabs', () => {
  it('roving focus with arrows and Home/End; Enter or click selects; selected controls the panel', async () => {
    render(<Sections />);
    const tabs = screen.getAllByRole('tab');
    expect(screen.getByRole('tablist', { name: 'Project' }).className).toBe('psl-tabs');
    expect(tabs[2].querySelector('.psl-badge')?.textContent).toBe('0');
    expect(tabs[0].getAttribute('aria-selected')).toBe('true');
    expect(tabs[0].getAttribute('aria-controls')).toBe('panel');
    expect(await violations()).toEqual([]);
    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    expect(document.activeElement).toBe(tabs[1]);
    fireEvent.keyDown(tabs[1], { key: 'End' });
    expect(document.activeElement).toBe(tabs[2]);
    fireEvent.keyDown(tabs[2], { key: 'ArrowRight' });
    expect(document.activeElement).toBe(tabs[0]);
    fireEvent.keyDown(tabs[0], { key: 'ArrowLeft' });
    fireEvent.click(document.activeElement as Element);
    expect(screen.getAllByRole('tab')[2].getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').textContent).toBe('money');
  });

  it('link tabs, and the phone strip', () => {
    render(<Tabs label="Work item" strip selected="a" tabs={[{ key: 'a', label: 'Overview', href: '/w/1' }, { key: 'b', label: 'History', href: '/w/1/history' }]} />);
    expect(screen.getByRole('tablist').className).toBe('psl-tabs psl-tabs--strip');
    expect(screen.getByRole('tab', { name: 'History' }).getAttribute('href')).toBe('/w/1/history');
  });
});
