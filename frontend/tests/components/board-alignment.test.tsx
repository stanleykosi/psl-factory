// @vitest-environment jsdom
// D-93: the shared components take the approved boards' look (titles, date formats, link disclosure, one-line
// breadcrumb, facts words, filter sheet) and the library gaps the migration lanes found.
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { createRef, useRef, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  AgentChecklist,
  BottomSheet,
  Breadcrumb,
  Callout,
  Disclosure,
  DisclosureLink,
  formatClock,
  formatDate,
  formatDateTime,
  formatDayMonth,
  formatDayTime,
  formatTime,
  formatWeekdayDayTime,
  MenuButton,
  PageTitle,
  Panel,
  Segmented,
  Table,
  Tabs,
  TextArea,
  Toast,
  When,
} from '@/components';

import { violations } from './a11y';

afterEach(() => vi.useRealTimers());

describe('date and time formats', () => {
  it('the boards’ formats as named variants, all in WAT', () => {
    const at = '2026-11-12T15:40:00Z';
    expect(formatDayTime(at)).toBe('12 Nov 16:40');
    expect(formatWeekdayDayTime('2026-11-10T13:05:00Z')).toBe('Tue 10 Nov 14:05');
    expect(formatClock(at)).toBe('16:40');
    expect(formatTime(at)).toBe('16:40 WAT');
    expect(formatDayMonth(at)).toBe('12 Nov');
    expect(formatDate(at)).toBe('12 Nov 2026');
    expect(formatDateTime(at)).toBe('12 Nov 2026 · 16:40 WAT');
  });

  it('DSC-1: a calendar date has no time, so the time formats say Unknown and the date-time is the date alone', () => {
    expect(formatTime('2026-11-17')).toBe('Unknown');
    expect(formatClock('2026-11-17')).toBe('Unknown');
    expect(formatDayTime('2026-11-17')).toBe('Unknown');
    expect(formatDateTime('2026-11-17')).toBe('17 Nov 2026');
    expect(formatDayMonth('2026-11-17')).toBe('17 Nov');
    render(<When value="2026-11-17" show="time" />);
    expect(screen.getByText('Unknown').className).toBe('psl-unknown');
  });

  it('missing or unreadable is Unknown in every format', () => {
    for (const f of [formatDayTime, formatWeekdayDayTime, formatClock, formatDayMonth, formatDateTime]) {
      expect(f(null)).toBe('Unknown');
      expect(f('')).toBe('Unknown');
      expect(f('not a date')).toBe('Unknown');
    }
  });

  it('When writes the named format inside <time>', () => {
    render(<When value="2026-11-12T15:40:00Z" show="daytime" />);
    const time = screen.getByText('12 Nov 16:40');
    expect(time.tagName).toBe('TIME');
    expect(time.getAttribute('datetime')).toBe('2026-11-12T15:40:00Z');
  });
});

describe('PageTitle', () => {
  it('40px by default, the board’s size where it draws a smaller one; ref and focus target pass through', () => {
    const ref = createRef<HTMLHeadingElement>();
    render(
      <>
        <PageTitle>My work</PageTitle>
        <PageTitle size={34} phoneSize={22} ref={ref} tabIndex={-1}>
          Lagoon Health
        </PageTitle>
      </>,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'My work' }).className).toBe('cmp-page-title');
    const record = screen.getByRole('heading', { level: 1, name: 'Lagoon Health' });
    expect(record.className).toBe('cmp-page-title cmp-page-title--34 cmp-page-title--p22');
    expect(ref.current).toBe(record);
    expect(record.getAttribute('tabindex')).toBe('-1');
  });
});

describe('Breadcrumb', () => {
  it('reads as one line with visible separators; links stay links; a level without a page is text', async () => {
    render(<Breadcrumb items={[{ label: 'My work', href: '/my-work' }, { label: 'Invoice preparation and delivery' }]} current={<span className="psl-mono">INV-0412</span>} />);
    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    const line = nav.querySelector('.psl-crumb') as HTMLElement;
    expect(line.textContent).toBe('My work / Invoice preparation and delivery / INV-0412');
    expect(line.querySelector('[aria-hidden]')).toBeNull();
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['My work']);
    expect(await violations()).toEqual([]);
  });
});

describe('Disclosure', () => {
  it('the link look: a summary drawn as a link, the open words while open', () => {
    const { container } = render(
      <Disclosure look="link" summary="Preview the invoice" openSummary="Hide the invoice">
        The invoice
      </Disclosure>,
    );
    const details = container.querySelector('details') as HTMLDetailsElement;
    expect(details.className).toBe('cmp-disclosure--link');
    const summary = details.querySelector('summary') as HTMLElement;
    expect(summary.className).toBe('psl-link');
    expect(summary.textContent).toBe('Preview the invoice');
    details.open = true;
    fireEvent(details, new Event('toggle'));
    expect(summary.textContent).toBe('Hide the invoice');
  });

  it('DisclosureLink: an inline link-look button that shows the detail it controls', async () => {
    function Agent() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <p>
            Chidi drafted v2 from 3 sources.{' '}
            <DisclosureLink open={open} onToggle={() => setOpen((v) => !v)} controls="steps" openLabel="Hide his steps">
              See his steps
            </DisclosureLink>
          </p>
          <ol id="steps" hidden={!open}>
            <li>Read the SOW</li>
          </ol>
        </>
      );
    }
    render(<Agent />);
    const button = screen.getByRole('button', { name: 'See his steps' });
    expect(button.className).toBe('psl-link cmp-disclosurelink');
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(button.getAttribute('aria-controls')).toBe('steps');
    fireEvent.click(button);
    expect(screen.getByRole('button', { name: 'Hide his steps' }).getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('Read the SOW')).toBeTruthy();
    expect(await violations()).toEqual([]);
  });
});

describe('Tabs and Segmented', () => {
  it('a count reads "History 7"; a disabled tab is skipped by the arrows and does not open', () => {
    const onSelect = vi.fn();
    render(
      <Tabs
        label="Work item"
        selected="overview"
        onSelect={onSelect}
        tabs={[
          { key: 'overview', label: 'Overview' },
          { key: 'documents', label: 'Documents', disabled: true },
          { key: 'history', label: 'History', count: 7 },
        ]}
      />,
    );
    const tabs = screen.getAllByRole('tab');
    expect(tabs[2].textContent).toBe('History 7');
    expect(tabs[1].getAttribute('aria-disabled')).toBe('true');
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    expect(document.activeElement).toBe(tabs[2]);
    fireEvent.click(tabs[1]);
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(tabs[2]);
    expect(onSelect).toHaveBeenCalledWith('history');
  });

  it('each segmented option carries its name', () => {
    render(
      <Segmented
        label="View"
        value="flat"
        onChange={() => {}}
        options={[
          { value: 'flat', label: 'Flat' },
          { value: 'floor', label: '3D floor' },
          { value: 'waiting', label: 'Waiting', count: 4 },
        ]}
      />,
    );
    expect(screen.getAllByRole('radio').map((r) => r.getAttribute('aria-label'))).toEqual(['Flat', '3D floor', 'Waiting 4']);
    expect(screen.getByRole('radio', { name: 'Waiting 4' }).textContent).toBe('Waiting 4');
  });
});

describe('Menu', () => {
  it('DSC-4: Space runs a link item, as Enter does', () => {
    const clicked = vi.fn((event: MouseEvent) => event.preventDefault());
    render(<MenuButton label="More" items={[{ key: 'history', label: 'Open history', href: '/work/W-1/history' }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'More' }));
    document.addEventListener('click', clicked);
    const item = screen.getByRole('menuitem', { name: 'Open history' });
    fireEvent.keyDown(item, { key: ' ' });
    expect(clicked).toHaveBeenCalled();
    expect((clicked.mock.calls[0][0].target as HTMLElement).closest('a')?.getAttribute('href')).toBe('/work/W-1/history');
    document.removeEventListener('click', clicked);
  });
});

describe('Toast', () => {
  it('DSC-2: the live region is drawn first and the message written into it a moment later', () => {
    vi.useFakeTimers();
    render(<Toast onDismiss={() => {}}>R-07 accepted</Toast>);
    const region = screen.getByRole('status');
    expect(region.textContent).not.toContain('R-07 accepted');
    act(() => vi.advanceTimersByTime(0));
    expect(region.textContent).toContain('R-07 accepted');
  });
});

describe('BottomSheet', () => {
  it('returns focus to the named opener; the handle and close button can be left out, with a head action', () => {
    function Sheet() {
      const opener = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      return (
        <>
          <button ref={opener} type="button" onClick={() => setOpen(true)}>
            Filter
          </button>
          {open && (
            <BottomSheet title="Filter" onClose={() => setOpen(false)} returnFocus={opener} grab={false} closeButton={false} headAction={<button type="button">Clear</button>}>
              <input aria-label="Line" />
            </BottomSheet>
          )}
        </>
      );
    }
    render(<Sheet />);
    const filter = screen.getByRole('button', { name: 'Filter' });
    fireEvent.click(filter);
    filter.blur();
    const sheet = screen.getByRole('dialog', { name: 'Filter' });
    expect(sheet.querySelector('.psl-sheet__grab')).toBeNull();
    expect(within(sheet).queryByRole('button', { name: 'Close' })).toBeNull();
    expect(within(sheet).getByRole('button', { name: 'Clear' })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Line' }));
    fireEvent.keyDown(sheet, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(filter);
  });
});

describe('Callout, Panel, TextArea, Table, AgentChecklist options', () => {
  it('Callout: another picture or none; plain children', () => {
    const { container } = render(
      <>
        <Callout kind="info" icon={false} plain>
          <strong>Stale</strong> <span>Review version 3</span>
        </Callout>
        <Callout kind="success" announce={false} icon={<span className="psl-avatar" aria-hidden="true" />}>
          Done
        </Callout>
      </>,
    );
    const [plain, pictured] = container.querySelectorAll('.psl-callout');
    expect(plain.querySelector('svg')).toBeNull();
    expect(plain.firstElementChild?.tagName).toBe('STRONG');
    expect(pictured.querySelector('.psl-avatar')).not.toBeNull();
    expect(pictured.querySelector('svg')).toBeNull();
  });

  it('Panel: a ref, data attributes and a heading head pass through', async () => {
    const ref = createRef<HTMLElement>();
    render(
      <Panel ref={ref} head="Decision" headingLevel={2} data-pinned="yes">
        Body
      </Panel>,
    );
    const region = screen.getByRole('region', { name: 'Decision' });
    expect(ref.current).toBe(region);
    expect(region.getAttribute('data-pinned')).toBe('yes');
    expect(screen.getByRole('heading', { level: 2, name: 'Decision' }).className).toBe('psl-panel__head');
    expect(await violations()).toEqual([]);
  });

  it('TextArea: one line where the board draws one', () => {
    render(<TextArea label="Anything Chidi should know" optional value="" onChange={() => {}} oneLine />);
    const box = screen.getByRole('textbox', { name: /Anything Chidi should know/ });
    expect(box.className).toBe('psl-input psl-input--area cmp-area--line');
    expect(box.getAttribute('rows')).toBe('1');
  });

  it('Table: a row opens a full-width row under it', () => {
    render(
      <Table
        caption="Templates"
        columns={[
          { key: 'name', header: 'TEMPLATE', cell: (r: { id: string }) => r.id },
          { key: 'v', header: 'VERSION', cell: () => 'v3' },
        ]}
        rows={[{ id: 'Invoice' }, { id: 'SOW' }]}
        rowKey={(r) => r.id}
        empty="No templates"
        expanded={(r) => (r.id === 'Invoice' ? <div>Upload a new version</div> : null)}
      />,
    );
    const rows = screen.getAllByRole('row');
    expect(rows.map((r) => r.textContent)).toEqual(['TEMPLATEVERSION', 'Invoicev3', 'Upload a new version', 'SOWv3']);
    expect(within(rows[2]).getByRole('cell').getAttribute('colspan')).toBe('2');
  });

  it('AgentChecklist: checks without an agent still show; nothing at all is drawn when there is neither', () => {
    const { container, rerender } = render(<AgentChecklist task="Follow-up email" status="working" steps={[{ text: 'Read the RFP', status: 'done' }]} label="Agent checks" />);
    expect(screen.getByRole('region', { name: 'Agent checks' })).toBeTruthy();
    expect(container.querySelector('.psl-avatar')).toBeNull();
    expect(screen.getByText('step 1 of 1')).toBeTruthy();
    rerender(<AgentChecklist task="Follow-up email" status="working" steps={[]} />);
    expect(container.innerHTML).toBe('');
  });
});
