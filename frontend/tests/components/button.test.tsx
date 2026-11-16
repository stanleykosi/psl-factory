// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Button, buttonClass, IconButton } from '@/components';

import { violations } from './a11y';

describe('Button', () => {
  it('draws each kind and size with the bundle classes', () => {
    expect(buttonClass()).toBe('psl-btn');
    expect(buttonClass('start', 'lg')).toBe('psl-btn psl-btn--start psl-btn--lg');
    expect(buttonClass('secondary', 'xl', true)).toBe('psl-btn psl-btn--secondary psl-btn--xl psl-btn--block');
    render(<Button kind="reject">Reject</Button>);
    const button = screen.getByRole('button', { name: 'Reject' });
    expect(button.className).toBe('psl-btn psl-btn--reject');
    expect(button.getAttribute('type')).toBe('button');
  });

  it('a small button is marked for the 44px phone target', () => {
    render(<Button size="sm">Filter</Button>);
    expect(screen.getByRole('button').className).toBe('psl-btn psl-btn--sm cmp-btn-sm');
  });

  it('busy shows the squares and what is happening, and ignores presses', () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Record</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
    rerender(
      <Button onClick={onClick} busy busyLabel="Recording…">
        Record
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Recording…' });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.classList.contains('is-busy')).toBe(true);
    expect(button.querySelectorAll('.psl-busy > i')).toHaveLength(3);
    expect(button.hasAttribute('disabled')).toBe(false);
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('disabled writes its reason beside it and is described by it', () => {
    render(
      <Button kind="dark" disabled reason="Add the proof file to record.">
        Record response
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Record response' });
    expect(button.hasAttribute('disabled')).toBe(true);
    const reason = document.getElementById(button.getAttribute('aria-describedby') ?? '');
    expect(reason?.textContent).toBe('Add the proof file to record.');
    expect(reason?.className).toBe('psl-reason');
  });

  it('a leading icon is decorative', () => {
    render(
      <Button kind="start" icon="plus">
        Start work
      </Button>,
    );
    expect(screen.getByRole('button', { name: 'Start work' }).querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('has no axe violations in every state', async () => {
    render(
      <>
        <Button>Approve</Button>
        <Button kind="text">Change line</Button>
        <Button busy busyLabel="Working…">
          Approve
        </Button>
        <Button disabled reason="Only the PMO Lead can approve.">
          Approve
        </Button>
      </>,
    );
    expect(await violations()).toEqual([]);
  });
});

describe('IconButton', () => {
  it('names its action and puts a count in the label and the ink badge (the boards)', async () => {
    render(
      <>
        <IconButton icon="close" label="Close" bare />
        <IconButton icon="filter" label="Filter" count={2} />
      </>,
    );
    expect(screen.getByRole('button', { name: 'Close' }).className).toBe('psl-iconbtn psl-iconbtn--bare');
    const filter = screen.getByRole('button', { name: 'Filter, 2 on' });
    expect(filter.querySelector('.psl-badge.cmp-badge--ink')?.textContent).toBe('2');
    expect(await violations()).toEqual([]);
  });
});
