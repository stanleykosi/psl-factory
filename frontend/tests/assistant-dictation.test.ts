// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, expect, it, vi } from 'vitest';

const script = readFileSync(join(__dirname, '../../static/assistant-dictation.js'), 'utf8');
const localOptions = { langs: ['en-US'], processLocally: true };
let mic: LocalSpeech;
class LocalSpeech {
  static available = vi.fn(async () => 'available');
  static install = vi.fn(async () => true);
  private local = false;
  get processLocally() { return this.local; }
  set processLocally(value) { this.local = value; }
  start() { expect(this.processLocally).toBe(true); mic = this; }
  stop = vi.fn();
  abort = vi.fn();
  onresult!: (event: object) => void;
  onend!: () => void;
  onerror!: (event: {error: string}) => void;
}
function screen() {
  window.eval(script);
  const form = document.querySelector('form')!;
  return {
    field: form.querySelector('textarea')!,
    button: form.querySelector<HTMLButtonElement>('[data-dictate]')!,
    status: form.querySelector('[role=status]')!,
    send: form.querySelector<HTMLButtonElement>('[type=submit]')!,
    form,
  };
}
function result(text: string, final = true) {
  return {isFinal: final, 0: {transcript: text}};
}
beforeEach(() => {
  LocalSpeech.available.mockReset().mockResolvedValue('available');
  LocalSpeech.install.mockReset().mockResolvedValue(true);
  vi.stubGlobal('isSecureContext', true);
  vi.stubGlobal('SpeechRecognition', LocalSpeech);
  vi.stubGlobal('webkitSpeechRecognition', undefined);
  document.body.innerHTML = `<form id="assistant-compose"><textarea name="question" maxlength="30"></textarea>
    <div data-dictation hidden><button type="button" data-dictate></button><span role="status"></span></div>
    <button type="submit">Send</button></form>`;
});

it('leaves typing available when the browser can only use online recognition', () => {
  class OnlineOnly { start = vi.fn(); }
  vi.stubGlobal('SpeechRecognition', undefined);
  vi.stubGlobal('webkitSpeechRecognition', OnlineOnly);
  const {button, send, status} = screen();
  expect(button.disabled).toBe(true);
  expect(status.textContent).toContain('type your message');
  expect(send.disabled).toBe(false);
});

it('requires a separate click to set up the local pack and another to listen', async () => {
  LocalSpeech.available.mockResolvedValue('downloadable');
  LocalSpeech.install.mockResolvedValueOnce(false);
  const {button, status, send} = screen();
  await vi.waitFor(() => expect(button.textContent).toBe('Set up dictation'));
  expect(LocalSpeech.available).toHaveBeenCalledWith(localOptions);
  expect(LocalSpeech.install).not.toHaveBeenCalled();
  button.click();
  await vi.waitFor(() => expect(status.textContent).toContain('Retry'));
  button.click();
  await vi.waitFor(() => expect(button.textContent).toBe('Dictate message'));
  expect(LocalSpeech.install).toHaveBeenCalledWith(localOptions);
  expect(send.disabled).toBe(false);
});

it('accepts final words once, preserves edits, and waits for an explicit send', async () => {
  const {button, field, send, form} = screen();
  const submitted = vi.fn();
  form.addEventListener('submit', event => {
    if (!event.defaultPrevented) submitted(field.value);
    event.preventDefault();
  });
  await vi.waitFor(() => expect(button.disabled).toBe(false));
  field.value = 'My draft:';
  button.click();
  expect(send.disabled).toBe(true);
  form.requestSubmit();
  mic.onresult({resultIndex: 0, results:[result('almost', false)]});
  expect(field.value).toBe('My draft:');
  mic.onresult({resultIndex: 0, results:[result('show invoices')]});
  button.click();
  expect(mic.stop).toHaveBeenCalledOnce();
  expect(send.disabled).toBe(true);
  mic.onresult({resultIndex: 0, results:[result('show invoices'), result('for Monday')]});
  mic.onend();
  mic.onresult({resultIndex: 2, results:[result('a'), result('b'), result('late')]});
  expect(field.value).toBe('My draft: show invoices for Monday');
  expect(field.validity.valid).toBe(false);
  expect(submitted).not.toHaveBeenCalled();
  field.value = 'Show invoices for Friday';
  field.dispatchEvent(new Event('input'));
  expect(field.validity.valid).toBe(true);
  send.click();
  expect(submitted).toHaveBeenCalledExactlyOnceWith('Show invoices for Friday');
});

it('restores the draft on microphone denial and stops listening on leaving the page', async () => {
  const {button, field, send, status} = screen();
  await vi.waitFor(() => expect(button.disabled).toBe(false));
  field.value = 'Keep my draft';
  button.click();
  mic.onerror({error:'not-allowed'});
  expect(status.textContent).toContain('permission was denied');
  expect(send.disabled).toBe(false);
  button.click();
  window.dispatchEvent(new Event('pagehide'));
  expect(mic.abort).toHaveBeenCalledOnce();
  mic.onresult({resultIndex:0, results:[result('stale')]});
  expect(field.value).toBe('Keep my draft');
  expect(send.disabled).toBe(false);
});
