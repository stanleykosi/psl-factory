// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AgentAvatar, AgentChecklist, AgentChip, agentKey, FactsStrip, initials, MiniStationBar, PersonAvatar, PhoneActionBar, StationTrack } from '@/components';

import { violations } from './a11y';

describe('Avatar', () => {
  it('people get initials on neutral; agents their mascot on their tint; the working ring', async () => {
    const { container } = render(
      <>
        <PersonAvatar name="Ada Okafor" />
        <PersonAvatar name="Tunde Bello" size={20} onDark />
        <AgentAvatar agent="chidi" size={40} working />
        <AgentChip agent="tola" />
      </>,
    );
    expect(initials('Ada Okafor')).toBe('AO');
    expect(agentKey('Chidi')).toBe('chidi');
    expect(agentKey('Bisi')).toBeUndefined();
    expect(screen.getByText('AO').className).toBe('psl-avatar');
    expect(screen.getByText('TB').className).toBe('psl-avatar psl-avatar--20 psl-avatar--dark');
    const working = container.querySelector('.psl-avatar-wrap.is-working img') as HTMLImageElement;
    expect(working.className).toBe('psl-avatar psl-avatar--chidi psl-avatar--40');
    expect(working.getAttribute('src')).toBe('/agents/chidi.png');
    expect(screen.getByText('Tola · PMO agent').className).toBe('psl-agentchip');
    expect(await violations()).toEqual([]);
  });
});

describe('FactsStrip', () => {
  it('six separate facts in order; a fact the record lacks is Unknown; paid sits apart', async () => {
    render(<FactsStrip facts={{ drafted: { status: 'earned', text: '10 Nov' }, reviewed: { status: 'earned', text: '11 Nov' }, approved: { status: 'current', text: 'Needs you' }, sent: { status: 'not_yet' }, verified: { status: 'not_yet' } }} />);
    const items = within(screen.getByRole('list', { name: 'Facts earned' })).getAllByRole('listitem');
    expect(items.map((i) => i.querySelector('b')?.textContent)).toEqual(['DRAFTED', 'REVIEWED', 'APPROVED', 'SENT', 'RECEIPT RECORDED', 'VERIFIED']);
    expect(items.map((i) => i.className)).toEqual(['psl-fact psl-fact--earned', 'psl-fact psl-fact--earned', 'psl-fact psl-fact--current', 'psl-fact', 'psl-fact psl-fact--unknown', 'psl-fact']);
    expect(items[4].querySelector('strong')?.textContent).toBe('Unknown');
    expect(items[3].querySelector('strong')?.textContent).toBe('Not yet');
    expect(items[0].textContent).toBe('DRAFTEDEarned: 10 Nov');
    expect(screen.getByText('Paid is tracked by Finance on the receipt, not here.').className).toBe('psl-doesnt cmp-paidnote');
    expect(await violations()).toEqual([]);
  });

  it('a verified fact takes the verified fill', () => {
    render(<FactsStrip facts={{ verified: { status: 'earned', text: '6 Nov' } }} paidNote={null} />);
    expect(screen.getByText('VERIFIED').parentElement?.className).toBe('psl-fact psl-fact--verified');
  });
});

describe('StationTrack and MiniStationBar', () => {
  it('numbered stations; the held one is the current step; the mini bar always has its words', async () => {
    render(
      <>
        <StationTrack
          stations={[
            { name: 'Draft', status: 'done', text: 'Chidi drafted v2' },
            { name: 'Finance review', status: 'person', text: 'Needs your decision' },
            { name: 'Issue', status: 'todo', text: 'Not started' },
          ]}
        />
        <MiniStationBar stations={['done', 'person', 'todo']} text="2 of 3 · Finance review" />
      </>,
    );
    const stations = within(screen.getByRole('list', { name: 'Stations in order' })).getAllByRole('listitem');
    expect(stations.map((s) => s.className)).toEqual(['psl-station psl-station--done', 'psl-station psl-station--person', 'psl-station psl-station--todo']);
    expect(stations[1].getAttribute('aria-current')).toBe('step');
    expect(stations[0].querySelector('b')?.textContent).toBe('01');
    const mini = screen.getByText('2 of 3 · Finance review').parentElement as HTMLElement;
    expect(mini.className).toBe('psl-mini');
    expect([...mini.querySelectorAll('.psl-mini__bar i')].map((i) => i.className)).toEqual(['d', 'p', 't']);
    expect(mini.querySelector('.psl-mini__bar')?.getAttribute('aria-hidden')).toBe('true');
    expect(await violations()).toEqual([]);
  });
});

describe('AgentChecklist', () => {
  it('steps by state with the records read; WORKING pulses; "Ask Tola"; never Approve, Send or Pay', async () => {
    render(
      <AgentChecklist
        agent="tola"
        task="Assembling the weekly client report"
        status="working"
        foot="Started 14:02 WAT"
        ask="/assistant"
        steps={[
          { text: 'Read the milestone register', status: 'done', source: 'MS register · 4 records' },
          { text: 'Drafting the progress section', status: 'now' },
          { text: 'Waiting for Kunle Ade to reply', status: 'wait' },
          { text: 'Check every figure cites a record', status: 'next' },
        ]}
      />,
    );
    const card = screen.getByRole('region', { name: 'Agent at work' });
    expect(card.className).toBe('psl-agent');
    expect(screen.getByText('Tola · PMO agent · step 2 of 4')).toBeTruthy();
    expect(screen.getByText('WORKING').className).toBe('psl-tag psl-tag--agent');
    const steps = [...card.querySelectorAll('.psl-step')];
    expect(steps.map((s) => s.className)).toEqual(['psl-step psl-step--done', 'psl-step psl-step--now', 'psl-step psl-step--wait', 'psl-step psl-step--next']);
    expect(steps[1].querySelector('.psl-step__box')?.className).toBe('psl-step__box psl-now');
    expect(steps[3].querySelector('.psl-step__box')?.textContent).toBe('4');
    expect(steps[0].textContent).toBe('Done: Read the milestone registerRead: MS register · 4 records');
    expect(screen.getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(card.textContent).not.toMatch(/Approve|Send|Pay\b/);
    expect(await violations()).toEqual([]);
  });

  it('stopped shows "!" and Action needed; done shows DONE', () => {
    const { rerender } = render(<AgentChecklist agent="chidi" task="Matching the bank import" status="stopped" steps={[{ text: 'Read 345 bank lines', status: 'done' }, { text: 'Stopped: 3 lines match two invoices', status: 'stopped' }]} />);
    expect(screen.getByText('Chidi · Finance agent · stopped at step 2')).toBeTruthy();
    expect(screen.getByText('Action needed').className).toBe('psl-tag psl-tag--person');
    expect(document.querySelector('.psl-step--stopped .psl-step__box')?.textContent).toBe('!');
    rerender(<AgentChecklist agent="chidi" task="Drafted invoice v3" status="done" steps={[{ text: 'Read the contract terms', status: 'done' }]} />);
    expect(screen.getByText('DONE').className).toBe('psl-tag psl-tag--agent');
    expect(screen.getByText('Chidi · Finance agent · done')).toBeTruthy();
  });
});

describe('PhoneActionBar', () => {
  it('Approve full width, Return and Reject side by side, what approving does not do; submitting and disabled', async () => {
    const onDecide = vi.fn();
    const { rerender } = render(<PhoneActionBar approveLabel="Approve v3" onDecide={onDecide} doesNot="Approving does not send the invoice." />);
    const approve = screen.getByRole('button', { name: 'Approve v3' });
    expect(approve.className).toBe('psl-btn psl-btn--xl psl-btn--block');
    expect(screen.getByRole('button', { name: 'Return' }).className).toBe('psl-btn psl-btn--secondary psl-btn--lg');
    expect(screen.getByRole('button', { name: 'Reject' }).className).toBe('psl-btn psl-btn--reject psl-btn--lg');
    expect(screen.getByText('Approving does not send the invoice.').className).toBe('psl-doesnt');
    fireEvent.click(approve);
    expect(onDecide).toHaveBeenCalledWith('approve');
    expect(await violations()).toEqual([]);
    rerender(<PhoneActionBar approveLabel="Approve v3" onDecide={onDecide} doesNot="Approving does not send the invoice." submitting="approve" />);
    expect(screen.getByRole('button', { name: 'Approving…' }).getAttribute('aria-busy')).toBe('true');
    expect((screen.getByRole('button', { name: 'Return' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('status').textContent).toBe('Recording your decision…');
    rerender(<PhoneActionBar approveLabel="Approve v3" onDecide={onDecide} doesNot="x" disabledReason="Only a Finance Lead can decide." />);
    expect(screen.getByText('Only a Finance Lead can decide.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Approve v3' }) as HTMLButtonElement).disabled).toBe(true);
  });
});
