// @vitest-environment jsdom
// F-24: the Start work drawer opened from the assistant's draft (additive `prefill` and `onStarted` props). The
// drawer fills the line's form once, the person checks it, and only the drawer's own button starts anything.
import { configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';

import { startBridge } from './assistant-bridge';

configure({ asyncUtilTimeout: 5000 });

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/assistant/CV-2401',
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

let bridge: ReturnType<typeof startBridge>;
beforeEach(() => {
  nav.push.mockReset();
  bridge = startBridge('pm');
  vi.stubGlobal('fetch', bridge.stub);
  setCsrfToken('mock-csrf-pm');
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

/** The draft's conversation was read, as the assistant page does before it offers the button (the mock arms the start). */
const arm = () => bridge.assistant.handle({ operationId: 'E-CONVERSATION', url: new URL('http://mock.local/api/v1/assistant/conversations/CV-2401'), raw: '', persona: 'pm', agents: [] });

const dialog = () => screen.getByRole('dialog');
const shown = (name: string) => within(dialog()).getByRole('combobox', { name }).querySelector('.sw-picker__value')!.textContent;
const starts = () => bridge.posts(/^\/api\/v1\/work$/);

type Intake = Record<string, unknown>;
async function openWith(intake: Intake, extra: { lineKey?: string; onStarted?: (id: string) => void } = {}) {
  const onClose = vi.fn();
  render(<StartWorkDrawer entry="default" prefill={{ line_key: extra.lineKey ?? 'invoice', intake }} onClose={onClose} onStarted={extra.onStarted} />);
  return onClose;
}
const ready = () => screen.findByRole('button', { name: 'Start the invoice' });

describe('prefill', () => {
  it('opens the line directly with record values resolved to the options this person is served', async () => {
    await openWith({ project: 'P-0102', milestone: 'M-0202' });
    await screen.findByRole('dialog', { name: 'Invoice preparation and delivery' });
    await waitFor(() => expect(shown('Completed milestone')).toBe('Milestone 2 · beta signed 30 Oct'));
    expect(shown('Project')).toBe('Harmattan Bank · mobile onboarding');
    // no chooser step, and nothing was sent
    expect(screen.queryByText('Choose a line')).toBeNull();
    expect(starts()).toEqual([]);
  });

  it('the start button waits until the values are in, then one press sends one start from the chosen options', async () => {
    arm();
    const onStarted = vi.fn();
    await openWith({ project: 'P-0102', milestone: 'M-0202', note: 'PO number on it' }, { onStarted });
    const button = await ready();
    expect((button as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    expect(within(dialog()).getByLabelText(/Anything Chidi should know/)).toHaveProperty('value', 'PO number on it');
    fireEvent.click(button);
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith('W-1401'));
    expect(starts()).toHaveLength(1);
    expect(starts()[0].body).toEqual({
      line: 'invoice',
      case_id: 'C-0102',
      case_revision: 3,
      intake: { project: 'P-0102', milestone: 'M-0202', note: 'PO number on it' },
      idempotency_key: expect.any(String),
    });
    // onStarted replaces the default (close and go to the work item)
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('a value the person is not served is left empty with the "no longer available" note', async () => {
    await openWith({ project: 'P-0102', milestone: 'M-9999' });
    await screen.findByRole('dialog');
    await waitFor(() => expect(within(dialog()).getByText('That choice is no longer available. Choose again.')).toBeTruthy());
    expect(shown('Project')).toBe('Harmattan Bank · mobile onboarding');
    expect(shown('Completed milestone')).not.toContain('M-9999');
    // an unusable choice can't be started: the case still comes from the project option and the milestone is required
    expect(starts()).toEqual([]);
  });

  it('a milestone that is not complete is not chosen for the person', async () => {
    await openWith({ project: 'P-0101', milestone: 'M-0104' });
    await waitFor(() => expect(within(dialog()).getByText('That choice is no longer available. Choose again.')).toBeTruthy());
    expect(shown('Project')).toBe('Lagoon Health · patient app');
  });

  it('a project this person is not served leaves both record fields empty', async () => {
    await openWith({ project: 'P-0999', milestone: 'M-0202' });
    await waitFor(() => expect(within(dialog()).getAllByText('That choice is no longer available. Choose again.')).toHaveLength(2));
    expect(starts()).toEqual([]);
  });

  it('a line this person cannot start shows "You can’t start this here." and no form', async () => {
    bridge = startBridge('finance_lead');
    vi.stubGlobal('fetch', bridge.stub);
    setCsrfToken('mock-csrf-finance_lead');
    await openWith({}, { lineKey: 'weekly_report' });
    expect(await screen.findByText('You can’t start this here.')).toBeTruthy();
    expect(within(dialog()).queryByRole('combobox')).toBeNull();
    expect(within(dialog()).queryByRole('button', { name: /^Start/ })).toBeNull();
    expect(starts()).toEqual([]);
  });

  it('with no onStarted the default still closes and goes to the work item', async () => {
    arm();
    const onClose = await openWith({ project: 'P-0102', milestone: 'M-0202' });
    const button = await ready();
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-1401'));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('a start the mock does not know as the draft’s', () => {
  it('falls through to Start work’s own answer, here the pinned billing-contact 422, shown by the drawer', async () => {
    const onStarted = vi.fn();
    await openWith({ project: 'P-0102', milestone: 'M-0202' }, { onStarted });
    const button = await ready();
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect(await within(dialog()).findByText(/The client register has no billing contact for Harmattan Bank/)).toBeTruthy();
    expect(onStarted).not.toHaveBeenCalled();
  });
});

describe('without prefill (existing callers)', () => {
  it('opens the chooser as before', async () => {
    render(<StartWorkDrawer entry="chooser" onClose={() => {}} />);
    expect(await screen.findByRole('dialog', { name: 'Choose a line' })).toBeTruthy();
  });
});
