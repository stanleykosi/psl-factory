// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Breadcrumb, Disclosure, EmptyState, ErrorState, Loading, PageTitle, Progress, Skeleton, ValidationSummary, VisuallyHidden, When } from '@/components';

import { violations } from './a11y';

describe('Loading, Skeleton, EmptyState, ErrorState, Progress', () => {
  it('three squares and words; placeholder bars hidden; empty with an action; problem callout with Retry', async () => {
    const onRetry = vi.fn();
    render(
      <>
        <Loading>Loading figures…</Loading>
        <Skeleton />
        <EmptyState title="Nothing needs you right now" action={<button type="button">Start work</button>}>
          New work appears here when a station needs your decision.
        </EmptyState>
        <ErrorState title="Couldn’t load the queue." onRetry={onRetry}>
          Your work is safe; nothing was changed.
        </ErrorState>
        <Progress value={214} max={345} label="Import" text="214 of 345 rows" />
      </>,
    );
    expect(screen.getByRole('status').className).toBe('psl-loading');
    expect(screen.getByRole('status').querySelectorAll('.psl-busy i')).toHaveLength(3);
    expect(document.querySelectorAll('.psl-skel')).toHaveLength(3);
    expect(document.querySelector('.cmp-skeleton')?.getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByRole('heading', { name: 'Nothing needs you right now' }).closest('.psl-empty')).not.toBeNull();
    expect(screen.getByRole('alert').className).toBe('psl-callout psl-callout--problem');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalled();
    expect(screen.getByRole('progressbar', { name: 'Import' }).getAttribute('aria-valuetext')).toBe('214 of 345 rows');
    expect(await violations()).toEqual([]);
  });
});

describe('Breadcrumb, PageTitle, VisuallyHidden, When', () => {
  it('two levels in mono caps; the title is the current page', async () => {
    render(
      <PageTitle above={<Breadcrumb items={[{ label: 'Projects', href: '/projects' }, { label: 'Lagoon Health', href: '/projects/1' }]} current="Milestones" />}>
        Lagoon Health · patient app <VisuallyHidden>project</VisuallyHidden>
      </PageTitle>,
    );
    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(nav.querySelector('.psl-crumb')).not.toBeNull();
    expect(screen.getByRole('link', { name: 'Projects' }).getAttribute('href')).toBe('/projects');
    expect(screen.getByText('Milestones').getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('heading', { level: 1 }).className).toBe('cmp-page-title');
    expect(screen.getByText('project').className).toBe('cmp-sr');
    expect(await violations()).toEqual([]);
  });

  it('When writes dates and WAT times, and Unknown when missing', () => {
    const { container } = render(
      <>
        <When value="2026-11-17" />
        <When value="2026-11-17T13:30:00Z" show="time" />
        <When value={null} />
      </>,
    );
    expect([...container.querySelectorAll('time')].map((t) => t.textContent)).toEqual(['17 Nov 2026', '14:30 WAT']);
    expect(container.querySelector('.psl-unknown')?.textContent).toBe('Unknown');
  });
});

describe('Disclosure', () => {
  it('a details/summary that opens and closes', async () => {
    render(<Disclosure summary="Tola’s suggestion (not used)">Mark R-07 as addressed.</Disclosure>);
    const details = screen.getByText('Tola’s suggestion (not used)').closest('details') as HTMLDetailsElement;
    expect(details.className).toBe('psl-disclosure');
    expect(details.open).toBe(false);
    expect(await violations()).toEqual([]);
  });
});

describe('ValidationSummary', () => {
  it('says how many things to fix, links move focus to the field, takes focus on each attempt, gone when fixed', async () => {
    const { rerender } = render(
      <>
        <ValidationSummary attempt={1} problems={[{ fieldId: 'milestone', message: 'Choose the completed milestone' }, { fieldId: 'proof', message: 'Add the client’s acceptance proof' }]} />
        <input id="milestone" aria-label="Milestone" />
        <input id="proof" aria-label="Proof" />
      </>,
    );
    const summary = screen.getByRole('alert');
    expect(summary.className).toBe('psl-summary');
    expect(screen.getByText('2 things to fix')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(summary));
    fireEvent.click(screen.getByRole('link', { name: 'Add the client’s acceptance proof' }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Proof' })));
    expect(await violations()).toEqual([]);
    rerender(<ValidationSummary attempt={2} problems={[{ fieldId: 'proof', message: 'Add the client’s acceptance proof' }]} />);
    expect(screen.getByText('1 thing to fix')).toBeTruthy();
    rerender(<ValidationSummary attempt={3} problems={[]} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
