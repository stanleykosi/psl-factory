// @vitest-environment jsdom
// D-160 (a sent message shows at once; the button is busy until the agent replies; no skeleton, no reload) and D-161
// (attach images: PROPOSAL, mock only). The real assistant mock answers in process through the bridge; a test holds one
// request at a time to look at the page while it is in flight.
import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { AssistantFrame } from '@/features/assistant/AssistantFrame';
import { AssistantHome } from '@/features/assistant/AssistantHome';
import { ThreadPage } from '@/features/assistant/ThreadPage';
import { AppShell } from '@/shell/AppShell';

import { json, startBridge, useNodeUploads } from './assistant-bridge';

configure({ asyncUtilTimeout: 5000 });

const nav = vi.hoisted(() => ({ pathname: '/assistant', go: (_to: string) => {} }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: (to: string) => nav.go(to), replace: (to: string) => nav.go(to), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(''),
}));

let bridge: ReturnType<typeof startBridge>;
let skeletons = 0;
let watcher: MutationObserver;

/** The page as the route layout renders it; `nav.go` moves it from the home to a thread, the frame staying put. */
function App({ start }: { start: string }) {
  const [path, setPath] = useState(start);
  useEffect(() => {
    nav.go = (to) => {
      nav.pathname = to.split('?')[0];
      setPath(nav.pathname);
    };
  }, []);
  const id = /^\/assistant\/([^/]+)/.exec(path)?.[1];
  return (
    <AppShell>
      <AssistantFrame>{id ? <ThreadPage key={id} id={id} /> : <AssistantHome />}</AssistantFrame>
    </AppShell>
  );
}

async function open(path: string, persona = 'pm') {
  nav.pathname = path;
  bridge = startBridge(persona);
  vi.stubGlobal('fetch', bridge.stub);
  setCsrfToken(`mock-csrf-${persona}`);
  const view = render(<App start={path} />);
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
  // Any skeleton that appears from here on is a flash: counted, never read at one instant.
  skeletons = 0;
  watcher = new MutationObserver(() => {
    if (document.querySelector('.psl-skel')) skeletons += 1;
  });
  watcher.observe(document.body, { childList: true, subtree: true });
  return view;
}

/** Holds the requests matching `match` until `release()`; the mock answers them then. */
function hold(match: (request: Request, url: URL) => boolean) {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  let held = 0;
  bridge.override(async (request, url) => {
    if (!match(request, url)) return undefined;
    held += 1;
    await gate;
    return undefined;
  });
  return { release, held: () => held };
}
const isMessage = (request: Request, url: URL) => request.method === 'POST' && url.pathname.endsWith('/messages');
const isUpload = (request: Request, url: URL) => request.method === 'POST' && url.pathname === '/api/v1/assistant/uploads';

afterEach(() => {
  watcher?.disconnect();
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setCsrfToken(null);
});
beforeEach(() => {
  nav.go = () => {};
});

const box = () => screen.getByRole('textbox', { name: /^Message / }) as HTMLTextAreaElement;
const type = (text: string) => fireEvent.change(box(), { target: { value: text } });
const sendButton = () => screen.getByRole('button', { name: 'Send' });
const press = () => fireEvent.click(sendButton());
const isBusy = () => sendButton().getAttribute('aria-busy') === 'true';
const thread = () => screen.getByRole('region', { name: 'Conversation' });
const messagePosts = () => bridge.posts(/\/messages$/);

describe('D-160: a sent message shows at once', () => {
  it('in a thread: the message, "Sending…" and the working step appear on the press; the composer is empty and the button busy', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    const gate = hold(isMessage);
    type('Where are we on the Harmattan invoice?');
    press();
    expect(within(thread()).getByText('Where are we on the Harmattan invoice?')).toBeTruthy();
    expect(within(thread()).getByText('Sending…')).toBeTruthy();
    expect(within(thread()).getByText('Reading your message')).toBeTruthy();
    expect(box().value).toBe('');
    expect(isBusy()).toBe(true);
    await waitFor(() => expect(gate.held()).toBe(1));
    gate.release();
    // the server confirms and the agent answers; the button is free again
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(within(thread()).queryByText('Sending…')).toBeNull();
    expect(within(thread()).getAllByText('Where are we on the Harmattan invoice?')).toHaveLength(1);
    expect(messagePosts()).toHaveLength(1);
    expect(skeletons).toBe(0);
  });

  it('shows the person’s @ chips with the message,', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    fireEvent.click(screen.getByRole('button', { name: '@ Mention a project or record' }));
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search projects and records' }), { target: { value: 'harm' } });
    fireEvent.click(await screen.findByRole('button', { name: /^Harmattan Bank · mobile onboarding/ }));
    const gate = hold(isMessage);
    type('Where are we');
    press();
    const mentions = within(thread()).getByRole('list', { name: 'Mentions' });
    expect(within(mentions).getByText('@Harmattan Bank · mobile onboarding')).toBeTruthy();
    gate.release();
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(messagePosts()[0].body).toEqual({ text: 'Where are we', mentions: [{ kind: 'project', id: 'P-0102' }] });
  });

  it('stays busy until the agent’s reply, not just until the POST returns; typing is allowed, sending waits', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    type('Plan it [working]');
    press();
    await waitFor(() => expect(messagePosts()).toHaveLength(1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    // the POST is done and the agent is still working
    expect(within(thread()).queryByText('Sending…')).toBeNull();
    expect(isBusy()).toBe(true);
    type('And one more thing');
    expect(box().value).toBe('And one more thing');
    press();
    expect(messagePosts()).toHaveLength(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000 * 3 + 200);
    });
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(within(thread()).getByText(/Sample answer from the contract mock/)).toBeTruthy();
    // the typed text is still there, and can now be sent
    expect(box().value).toBe('And one more thing');
    press();
    await waitFor(() => expect(messagePosts()).toHaveLength(2));
    expect(skeletons).toBe(0);
  });

  it('reconciles in place: the same scrolling thread, no skeleton, and the person’s text once', async () => {
    await open('/assistant/CV-2401');
    const before = await screen.findByRole('region', { name: 'Conversation' });
    type('One more question');
    press();
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(screen.getByRole('region', { name: 'Conversation' })).toBe(before);
    expect(screen.queryByText('Loading…')).toBeNull();
    expect(within(before).getAllByText('One more question')).toHaveLength(1);
    expect(skeletons).toBe(0);
  });

  it('the conversation list changes in place: its rows stay while it is read again', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    const list = screen.getByRole('complementary', { name: 'Conversations' });
    const rows = within(list).getAllByRole('link').length;
    const reads = bridge.gets(/\/assistant\/conversations$/).length;
    type('Another');
    press();
    await waitFor(() => expect(bridge.gets(/\/assistant\/conversations$/).length).toBe(reads + 1));
    expect(within(list).getAllByRole('link').length).toBe(rows);
    expect(skeletons).toBe(0);
  });
});

describe('D-160: the first message from the home', () => {
  it('shows at once in place of the hello, then the thread opens with no skeleton and the same message', async () => {
    await open('/assistant');
    const gate = hold((request, url) => isMessage(request, url));
    type('Draft the SOW for Kora');
    press();
    // before the conversation has a message on the server
    expect(screen.queryByRole('heading', { level: 1, name: /I’m Tola/ })).toBeNull();
    expect(within(thread()).getByText('Draft the SOW for Kora')).toBeTruthy();
    expect(within(thread()).getByText('Sending…')).toBeTruthy();
    expect(box().value).toBe('');
    expect(isBusy()).toBe(true);
    await waitFor(() => expect(gate.held()).toBe(1));
    // now hold the thread's first read: the thread must already show the message while it loads
    bridge.override(async (request, url) => {
      if (request.method === 'GET' && /\/conversations\/CV-N1$/.test(url.pathname)) await new Promise((resolve) => setTimeout(resolve, 150));
      return undefined;
    });
    gate.release();
    await waitFor(() => expect(nav.pathname).toBe('/assistant/CV-N1'));
    expect(within(thread()).getByText('Draft the SOW for Kora')).toBeTruthy();
    expect(screen.queryByText('Loading…')).toBeNull();
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(within(thread()).getAllByText('Draft the SOW for Kora')).toHaveLength(1);
    expect(within(thread()).getByText(/Sample answer from the contract mock/)).toBeTruthy();
    expect(skeletons).toBe(0);
    expect(bridge.posts(/\/assistant\//).map((p) => p.path)).toEqual(['/api/v1/assistant/conversations', '/api/v1/assistant/conversations/CV-N1/messages']);
  });
});

describe('D-160: failures keep today’s rules', () => {
  it('a refused send removes the message and puts the text back with the error', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    type('Please check [422]');
    press();
    expect((await screen.findByRole('alert')).textContent).toBe('The mock refused this message: check the text and try again.');
    expect(within(thread()).queryByText('Please check [422]')).toBeNull();
    expect(within(thread()).queryByText('Sending…')).toBeNull();
    expect(box().value).toBe('Please check [422]');
    expect(isBusy()).toBe(false);
    expect(messagePosts()).toHaveLength(1);
  });

  it('a refused first message on the home brings the hello back with the text', async () => {
    await open('/assistant');
    type('Plan [422]');
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('The mock refused');
    expect(screen.getByRole('heading', { level: 1, name: /I’m Tola/ })).toBeTruthy();
    expect(box().value).toBe('Plan [422]');
    expect(isBusy()).toBe(false);
    expect(nav.pathname).toBe('/assistant');
  });

  it('an uncertain send found on the re-read stays, with no "Sending…" and no second POST', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    let first = true;
    bridge.override(async (request, url) => {
      if (!isMessage(request, url) || !first) return undefined;
      first = false;
      bridge.assistant.handle({ operationId: 'E-MESSAGE', url, raw: await request.clone().text(), persona: 'pm', agents: [] });
      return json(502, { code: 'bad_gateway', message: 'Lost on the way.' });
    });
    type('Went through');
    press();
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(within(thread()).getAllByText('Went through')).toHaveLength(1);
    expect(within(thread()).queryByText('Sending…')).toBeNull();
    expect(box().value).toBe('');
    expect(messagePosts()).toHaveLength(1);
  });

  it('an uncertain send not found on the re-read takes the message out, restores the text and offers Try again', async () => {
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    type('Lost [500]');
    press();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t confirm that was sent.');
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(within(thread()).queryByText('Lost [500]')).toBeNull();
    expect(box().value).toBe('Lost [500]');
    expect(isBusy()).toBe(false);
    expect(messagePosts()).toHaveLength(1);
  });
});

describe('D-161: attach images (proposal, mock only)', () => {
  const picker = () => document.querySelector('input[type="file"]') as HTMLInputElement;
  const choose = (...files: File[]) => fireEvent.change(picker(), { target: { files } });

  it('a paperclip icon button named "Attach images", the same size as the microphone, opens an image chooser (several, images only)', async () => {
    await open('/assistant');
    const attach = screen.getByRole('button', { name: 'Attach images' });
    const mic = screen.getByRole('button', { name: 'Speak your request' });
    expect(attach.className).toContain('psl-iconbtn');
    expect(mic.className).toContain('psl-iconbtn');
    expect(picker().accept).toBe('image/*');
    expect(picker().multiple).toBe(true);
    const click = vi.spyOn(picker(), 'click');
    fireEvent.click(attach);
    expect(click).toHaveBeenCalledTimes(1);
  });

  it('is on a phone too (the microphone is not)', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('max-width'), media: query, addEventListener: () => {}, removeEventListener: () => {} }));
    await open('/assistant');
    expect(screen.getByRole('button', { name: 'Attach images' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Speak your request' })).toBeNull();
  });

  it('a chosen image is a thumbnail with a remove button; it uploads, one request each; Send waits for it', async () => {
    const file = await useNodeUploads();
    await open('/assistant');
    const gate = hold(isUpload);
    choose(file('plan.png'), file('site.jpg', 'image/jpeg'));
    const images = within(screen.getByRole('list', { name: 'Images' }));
    expect(images.getAllByRole('listitem')).toHaveLength(2);
    expect(images.getByRole('img', { name: 'plan.png' })).toBeTruthy();
    expect(images.getByRole('button', { name: 'Remove site.jpg' })).toBeTruthy();
    expect(images.getAllByRole('status')).toHaveLength(2);
    // still uploading: Send is disabled even with words
    type('See these');
    expect(sendButton().getAttribute('aria-disabled')).toBe('true');
    await waitFor(() => expect(gate.held()).toBe(2));
    gate.release();
    await waitFor(() => expect(images.queryAllByRole('status')).toHaveLength(0));
    expect(sendButton().getAttribute('aria-disabled')).toBeNull();
    const uploads = bridge.posts(/\/uploads$/);
    expect(uploads).toHaveLength(2);
    expect(uploads[0].headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(uploads.map((u) => u.file?.name)).toEqual(['plan.png', 'site.jpg']);
  });

  it('remove takes the image off, and it is not sent', async () => {
    const file = await useNodeUploads();
    await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    choose(file('a.png'), file('b.png'));
    await waitFor(() => expect(screen.queryAllByRole('status')).toHaveLength(0));
    fireEvent.click(screen.getByRole('button', { name: 'Remove a.png' }));
    expect(screen.queryByRole('img', { name: 'a.png' })).toBeNull();
    type('Just the one');
    press();
    await waitFor(() => expect(messagePosts()).toHaveLength(1));
    expect(messagePosts()[0].body).toEqual({ text: 'Just the one', attachments: [{ file_id: 'F-2' }] });
  });

  it('an image the server refuses shows its words, word for word, and holds the Send until it is removed', async () => {
    const file = await useNodeUploads();
    await open('/assistant');
    choose(file('notes.txt', 'text/plain'), file('huge.png', 'image/png', 10 * 1024 * 1024 + 1));
    const alerts = await screen.findAllByRole('alert');
    expect(alerts.map((a) => a.textContent)).toEqual(['Attach an image file.', 'Images up to 10 MB.']);
    type('With a bad one');
    expect(sendButton().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Remove notes.txt' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove huge.png' }));
    expect(sendButton().getAttribute('aria-disabled')).toBeNull();
  });

  it('an upload that may have gone through is said so, and is not resent', async () => {
    const file = await useNodeUploads();
    await open('/assistant');
    bridge.override((request, url) => (isUpload(request, url) ? Promise.reject(new TypeError('fetch failed')) : undefined));
    choose(file('lost.png'));
    expect((await screen.findByRole('alert')).textContent).toBe('We couldn’t confirm that image was uploaded. Remove it and attach it again.');
    expect(bridge.posts(/\/uploads$/)).toHaveLength(1);
  });

  it('sends with images and no text: the thumbnails show at once, then the server’s copy, and survive a reload', async () => {
    const file = await useNodeUploads();
    const view = await open('/assistant/CV-2401');
    await screen.findByRole('region', { name: 'Conversation' });
    choose(file('floor.png'));
    await waitFor(() => expect(screen.queryAllByRole('status')).toHaveLength(0));
    expect(sendButton().getAttribute('aria-disabled')).toBeNull();
    const gate = hold(isMessage);
    press();
    // at once: the local preview, no words, "Sending…"
    const sent = within(thread()).getByRole('list', { name: 'Images' });
    expect(within(sent).getByRole('img', { name: 'floor.png' }).getAttribute('src')).toMatch(/^blob:/);
    expect(within(thread()).getByText('Sending…')).toBeTruthy();
    expect(screen.getAllByRole('list', { name: 'Images' })).toHaveLength(1);
    await waitFor(() => expect(gate.held()).toBe(1));
    gate.release();
    await waitFor(() => expect(isBusy()).toBe(false));
    expect(messagePosts()[0].body).toEqual({ text: '', attachments: [{ file_id: 'F-1' }] });
    const kept = within(thread()).getByRole('img', { name: 'floor.png' });
    expect(kept.getAttribute('src')).toBe('/api/v1/assistant/uploads/F-1');
    expect(kept.closest('a')?.getAttribute('href')).toBe('/api/v1/assistant/uploads/F-1');
    expect(kept.closest('a')?.getAttribute('target')).toBe('_blank');
    // a fresh page over the same mock still has it
    view.unmount();
    vi.stubGlobal('fetch', bridge.stub);
    render(<App start="/assistant/CV-2401" />);
    expect((await screen.findByRole('img', { name: 'floor.png' })).getAttribute('src')).toBe('/api/v1/assistant/uploads/F-1');
  });
});
