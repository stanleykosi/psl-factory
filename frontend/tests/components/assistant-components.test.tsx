// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AgentChecklist, AGENTS, ChatMessage, Composer, DraftCard, Link, SourceTag } from '@/components';

import { violations } from './a11y';

afterEach(() => vi.unstubAllGlobals());

/** Below 720px, as the phone boards draw. */
function phone() {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
}

describe('AGENTS', () => {
  it('names each agent’s team for the Talk to chips', () => {
    expect(Object.values(AGENTS).map((a) => a.team)).toEqual(['PMO', 'Finance', 'HR']);
  });
});

describe('AgentChecklist inline', () => {
  const steps = [
    { text: 'Read the award letter', status: 'done' as const, source: 'AWARD LETTER · 04 DEC' },
    { text: 'Matching estimates', status: 'now' as const },
    { text: 'Hand it over', status: 'next' as const },
  ];

  it('is a mono header line over the steps, with no avatar head and no foot', async () => {
    const { container } = render(<AgentChecklist inline agent="tola" task="Planning packet" status="working" steps={steps} foot="Started 14:02" ask="/assistant" />);
    expect(screen.getByText('WORKING · STEP 2 OF 3').className).toBe('cmp-agent__line');
    expect(container.querySelector('.psl-agent__head, .psl-agent__foot, img')).toBeNull();
    expect(screen.queryByText('Started 14:02')).toBeNull();
    // the state is in words for screen readers, not only the pulse
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual(['Done: Read the award letterRead: AWARD LETTER · 04 DEC', 'In progress: Matching estimates', '3To do: Hand it over']);
    expect(await violations()).toEqual([]);
  });

  it('reads "3 STEPS · DONE" when every step is done, and "1 STEP" for one', () => {
    const { rerender } = render(<AgentChecklist inline task="x" status="done" steps={steps.map((s) => ({ ...s, status: 'done' as const }))} />);
    expect(screen.getByText('3 STEPS · DONE')).toBeTruthy();
    rerender(<AgentChecklist inline task="x" status="done" steps={[steps[0]]} />);
    expect(screen.getByText('1 STEP · DONE')).toBeTruthy();
  });

  it('keeps the card without inline: the head names the task, agent and step', () => {
    render(<AgentChecklist agent="tola" task="Planning packet" status="working" steps={steps} foot="Started 14:02" />);
    expect(screen.getByText('Tola · PMO agent · step 2 of 3')).toBeTruthy();
    expect(screen.getByText('Started 14:02')).toBeTruthy();
  });

  it('a step record can be a link', () => {
    render(<AgentChecklist inline task="x" status="done" steps={[{ text: 'Read it', status: 'done', source: <Link href="/work/W-1">GO-LIVE</Link> }]} />);
    expect(screen.getByRole('link', { name: 'GO-LIVE' }).getAttribute('href')).toBe('/work/W-1');
  });
});

describe('SourceTag', () => {
  it('default is plain mono text; a link goes to the record', async () => {
    render(
      <>
        <SourceTag label="SIGNED SOW v2 · stage 2" />
        <SourceTag label="MILESTONE · HB-M2" href="/projects/C-0102" />
      </>,
    );
    expect(screen.queryByRole('link', { name: 'SIGNED SOW v2 · stage 2' })).toBeNull();
    expect(screen.getByRole('link', { name: 'MILESTONE · HB-M2' }).getAttribute('href')).toBe('/projects/C-0102');
    expect(await violations()).toEqual([]);
  });

  it('restricted draws a lock and the word Restricted only: no label, no reference, no link', () => {
    const { container } = render(<SourceTag restricted />);
    expect(container.textContent).toBe('Restricted');
    expect(container.querySelector('a, svg.psl-icon')?.tagName).toBe('svg');
    expect(container.querySelector('a')).toBeNull();
    expect(container.querySelector('.cmp-source--restricted')).toBeTruthy();
  });
});

describe('DraftCard', () => {
  const rows = [
    { label: 'Amount', value: '₦6,800,000.00' },
    { label: 'Template', value: 'Invoice · TEST TEMPLATE' },
  ];

  it('drafted: header, rows, the start button and Next beside it', async () => {
    const onStart = vi.fn();
    render(<DraftCard title="Invoice draft" status="DRAFTED · NOT REVIEWED" rows={rows} next="Finance review by a Finance Lead" action={<button onClick={onStart}>Start this invoice</button>} />);
    const card = screen.getByRole('region', { name: 'Draft' });
    expect(within(card).getByText('Invoice draft')).toBeTruthy();
    expect(within(card).getByText('DRAFTED · NOT REVIEWED')).toBeTruthy();
    expect(within(card).getByText('Amount').tagName).toBe('DT');
    expect(within(card).getByText('Invoice · TEST TEMPLATE').tagName).toBe('DD');
    expect(within(card).getByText('Next: Finance review by a Finance Lead')).toBeTruthy();
    fireEvent.click(within(card).getByRole('button', { name: 'Start this invoice' }));
    expect(onStart).toHaveBeenCalledOnce();
    // no decision controls exist in the card
    expect(within(card).queryByRole('button', { name: /approve|send|pay/i })).toBeNull();
    expect(await violations()).toEqual([]);
  });

  it('on a phone Next is a row', () => {
    phone();
    render(<DraftCard title="Invoice draft" rows={rows} next="Finance review by a Finance Lead" />);
    expect(screen.getByText('Next').tagName).toBe('DT');
    expect(screen.queryByText(/^Next: /)).toBeNull();
  });

  it('started: the line is a polite status that can take focus; the start button is the caller’s and absent', () => {
    render(<DraftCard title="Invoice draft" rows={rows} started={<>Started INV-0415. <Link href="/work/W-1401">Open the work item</Link></>} />);
    const line = screen.getByRole('status');
    expect(line.textContent).toBe('Started INV-0415. Open the work item');
    expect(line.getAttribute('tabindex')).toBe('-1');
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('ChatMessage', () => {
  it('person: your words in the ink box, line breaks kept, nothing parsed as HTML or markdown', () => {
    const { container } = render(<ChatMessage from="person">{'<img src=x onerror=alert(1)>\n**bold**'}</ChatMessage>);
    expect(container.querySelector('img, strong, b')).toBeNull();
    expect(container.textContent).toBe('<img src=x onerror=alert(1)>\n**bold**');
    expect(container.querySelector('.cmp-chat--person')).toBeTruthy();
  });

  it('agent: avatar, name and team, hand-off, steps, answer, sources, cannot line and draft, in that order', async () => {
    render(
      <ChatMessage from="agent" agent="chidi" handoff="Tola passed this to him." steps={<p>STEPS</p>} sources={<span>SOURCES</span>} cannot="Restricted to HR." draft={<p>DRAFT</p>}>
        The answer
      </ChatMessage>,
    );
    const article = screen.getByRole('article', { name: 'Chidi, Finance agent' });
    expect(within(article).getByText('Chidi').tagName).toBe('STRONG');
    expect(within(article).getByText('· Finance agent')).toBeTruthy();
    const body = article.querySelector('.cmp-chat__body')!;
    expect([...body.children].map((c) => c.textContent)).toEqual(['Tola passed this to him.', 'STEPS', 'The answer', 'Restricted to HR.', 'SOURCES', 'DRAFT']);
    expect(article.querySelector('img')?.getAttribute('src')).toBe('/agents/chidi.png');
    expect(await violations()).toEqual([]);
  });

  it('agent text is text: an <img> in an answer makes no element', () => {
    const { container } = render(<ChatMessage from="agent" agent="tola">{'<img src=x onerror=alert(1)>'}</ChatMessage>);
    expect(container.querySelectorAll('img')).toHaveLength(1); // the avatar only
    expect(container.querySelector('.cmp-chat__answer')?.textContent).toBe('<img src=x onerror=alert(1)>');
  });
});

describe('Composer', () => {
  function setup(props: Partial<Parameters<typeof Composer>[0]> = {}) {
    const onSend = vi.fn();
    const onChange = vi.fn();
    const view = render(<Composer agentName="Tola" value="Draft a SOW" onChange={onChange} onSend={onSend} canSend heldMic placeholder="Ask Tola…" {...props} />);
    return { onSend, onChange, ...view };
  }

  it('is labelled "Message Tola"; Enter sends; Shift+Enter adds a line and sends nothing', async () => {
    const { onSend } = setup();
    const box = screen.getByRole('textbox', { name: 'Message Tola' });
    expect(box.getAttribute('placeholder')).toBe('Ask Tola…');
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(onSend).toHaveBeenCalledTimes(2);
    expect(await violations()).toEqual([]);
  });

  it('does nothing while it cannot send or while busy', () => {
    const blank = setup({ canSend: false });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(blank.onSend).not.toHaveBeenCalled();
    blank.unmount();
    const busy = setup({ busy: true });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(busy.onSend).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Send' }).getAttribute('aria-busy')).toBe('true');
  });

  it('chips can be removed by name; an error is an alert tied to the box', () => {
    const onRemoveChip = vi.fn();
    setup({ chips: [{ id: 'project:P-1', label: '@Harmattan Bank' }], onRemoveChip, error: 'Keep it under 4,000 characters.' });
    fireEvent.click(screen.getByRole('button', { name: 'Remove @Harmattan Bank' }));
    expect(onRemoveChip).toHaveBeenCalledWith('project:P-1');
    expect(screen.getByRole('alert').textContent).toBe('Keep it under 4,000 characters.');
    expect(screen.getByRole('textbox').getAttribute('aria-invalid')).toBe('true');
  });

  it('draws no paperclip unless a caller takes files; with one it is "Attach images", an image chooser for several files', () => {
    const none = setup();
    expect(screen.queryByRole('button', { name: 'Attach images' })).toBeNull();
    none.unmount();
    const onAttach = vi.fn();
    const { container } = setup({ onAttach });
    const attach = screen.getByRole('button', { name: 'Attach images' });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect([input.accept, input.multiple]).toEqual(['image/*', true]);
    const click = vi.spyOn(input, 'click');
    fireEvent.click(attach);
    expect(click).toHaveBeenCalledOnce();
    const file = new File(['x'], 'a.png', { type: 'image/png' });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onAttach).toHaveBeenCalledWith([file]);
  });

  it('draws each image as a thumbnail with its own remove button, busy while uploading, and the server’s words when refused', () => {
    const onRemoveImage = vi.fn();
    setup({
      onAttach: vi.fn(),
      onRemoveImage,
      images: [
        { id: 'a', name: 'ready.png', src: 'blob:a', state: 'ready' },
        { id: 'b', name: 'busy.png', src: 'blob:b', state: 'uploading' },
        { id: 'c', name: 'bad.txt', src: 'blob:c', state: 'error', error: 'Attach an image file.' },
      ],
    });
    const items = within(screen.getByRole('list', { name: 'Images' })).getAllByRole('listitem');
    expect(items.map((i) => i.getAttribute('aria-busy'))).toEqual([null, 'true', null]);
    expect(within(items[1]).getByRole('status', { name: 'Uploading busy.png' })).toBeTruthy();
    expect(within(items[2]).getByRole('alert').textContent).toBe('Attach an image file.');
    fireEvent.click(screen.getByRole('button', { name: 'Remove busy.png' }));
    expect(onRemoveImage).toHaveBeenCalledWith('b');
  });

  it('the held microphone is focusable and disabled in words, has no handler, and sends or changes nothing', () => {
    const { onSend, onChange } = setup();
    const mic = screen.getByRole('button', { name: 'Speak your request' });
    expect(mic.getAttribute('aria-disabled')).toBe('true');
    expect(mic.hasAttribute('disabled')).toBe(false);
    mic.focus();
    expect(document.activeElement).toBe(mic);
    fireEvent.click(mic);
    fireEvent.keyDown(mic, { key: 'Enter' });
    fireEvent.keyDown(mic, { key: ' ' });
    expect(onSend).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox')).toHaveProperty('value', 'Draft a SOW');
  });

  it('offers no attach button; the microphone is not drawn on a phone or when not held', () => {
    const wide = setup({ heldMic: false });
    expect(screen.queryByRole('button', { name: /attach|file/i })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Speak your request' })).toBeNull();
    wide.unmount();
    phone();
    setup();
    expect(screen.queryByRole('button', { name: 'Speak your request' })).toBeNull();
  });
});
