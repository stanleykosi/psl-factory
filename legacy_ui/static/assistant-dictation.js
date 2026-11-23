// Audio is handled exclusively by the browser's on-device recognizer.
(() => {
  const form = document.getElementById('assistant-compose');
  const panel = form?.querySelector('[data-dictation]');
  const field = form?.querySelector('textarea[name="question"]');
  if (!panel || !field) return;

  const button = panel.querySelector('[data-dictate]');
  const status = panel.querySelector('[role="status"]');
  const send = form.querySelector('button[type="submit"]');
  const Recognition = [window.SpeechRecognition, window.webkitSpeechRecognition].find(api =>
    api && 'processLocally' in api.prototype && typeof api.available === 'function');
  let language = navigator.language || 'en-US';
  let mode;
  let session = null;
  let stopTimer;
  let revision = 0;

  function show(next, label, message, disabled = false) {
    mode = next;
    button.textContent = label;
    button.disabled = disabled;
    status.textContent = message;
  }
  function ready(message = 'Audio stays on this device. Review your words before sending.') {
    show('ready', 'Dictate message', message);
  }
  function unavailable() {
    show('unavailable', 'Dictate message', 'On-device dictation is unavailable here. You can type your message.', true);
  }
  function options() {
    return {langs: [language], processLocally: true};
  }
  async function check() {
    const ticket = ++revision;
    if (!window.isSecureContext || !Recognition) return unavailable();
    show('checking', 'Dictate message', 'Checking on-device dictation…', true);
    try {
      let result = await Recognition.available(options());
      if (ticket !== revision) return;
      if (result === 'unavailable' && /^en(?:-|$)/i.test(language) && language !== 'en-US') {
        language = 'en-US';
        result = await Recognition.available(options());
      }
      if (ticket !== revision) return;
      if (result === 'available') ready();
      else if (['downloadable', 'downloading'].includes(result) && typeof Recognition.install === 'function') {
        show('install', 'Set up dictation', 'Your browser needs a local speech pack (' + language + ').');
      } else unavailable();
    } catch {
      if (ticket === revision) unavailable();
    }
  }

  // Ending a session invalidates late callbacks before the text can be edited or sent.
  function finish(message, abort = false) {
    const previous = session;
    session = null;
    clearTimeout(stopTimer);
    send.disabled = false;
    ready(message);
    if (abort && previous) {
      try { previous.abort(); } catch { /* The microphone may already have stopped. */ }
    }
  }
  function checkLength() {
    const tooLong = field.maxLength >= 0 && field.value.length > field.maxLength;
    field.setCustomValidity(tooLong ? 'Shorten your message to ' + field.maxLength + ' characters before sending.' : '');
  }
  function start() {
    try {
      const speech = new Recognition();
      speech.processLocally = true;
      if (speech.processLocally !== true) return unavailable();
      speech.lang = language;
      speech.continuous = true;
      speech.interimResults = false;
      let accepted = 0;
      let heard = false;
      speech.onresult = event => {
        if (session !== speech) return;
        for (let i = Math.max(accepted, event.resultIndex); i < event.results.length; i++) {
          const result = event.results[i];
          if (!result.isFinal) continue;
          accepted = i + 1;
          const words = result[0].transcript.trim();
          if (!words) continue;
          const space = field.value && !/\s$/.test(field.value) ? ' ' : '';
          field.setRangeText(space + words, field.value.length, field.value.length, 'preserve');
          field.dispatchEvent(new Event('input', {bubbles: true}));
          heard = true;
        }
      };
      speech.onend = () => {
        if (session !== speech) return;
        finish(heard ? 'Review and edit your message, then press Send.' : 'No words were added. Try again or type your message.');
        if (document.activeElement === button || document.activeElement === document.body) field.focus();
      };
      speech.onerror = event => {
        if (session !== speech) return;
        const messages = {
          'not-allowed': 'Microphone permission was denied. You can type or allow microphone access in your browser.',
          'audio-capture': 'Your microphone is unavailable. Check the microphone or type your message.',
          'no-speech': 'No speech was heard. Try again or type your message.',
        };
        finish(messages[event.error] || 'On-device dictation stopped. You can edit your message or try again.', true);
      };
      session = speech;
      send.disabled = true;
      show('listening', 'Stop dictation', 'Listening on this device…');
      speech.start();
    } catch {
      finish('On-device dictation could not start. You can type your message.', true);
    }
  }
  button.addEventListener('click', async () => {
    if (mode === 'ready') start();
    else if (mode === 'listening') {
      show('stopping', 'Stopping…', 'Finishing the last words…', true);
      stopTimer = setTimeout(() => finish('Dictation stopped. Review the words in your message.', true), 5000);
      try { session.stop(); } catch { finish('Dictation stopped. Review the words in your message.', true); }
    } else if (mode === 'install') {
      const ticket = ++revision;
      show('installing', 'Setting up…', 'Preparing the speech pack. You can type while it installs.', true);
      try {
        if (await Recognition.install(options())) {
          if (ticket === revision) ready('Ready. Press Dictate message when you want to speak.');
          return;
        }
      } catch { /* A declined or interrupted installation can be retried. */ }
      if (ticket === revision) show('install', 'Set up dictation', 'The local speech pack was not installed. Retry or type your message.');
    }
  });
  field.addEventListener('input', checkLength);
  form.addEventListener('submit', event => { if (session) event.preventDefault(); });
  function leave() {
    if (session) finish('Dictation stopped. Review your message before sending.', true);
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) leave(); });
  window.addEventListener('pagehide', () => { ++revision; leave(); });
  window.addEventListener('pageshow', event => { if (event.persisted) check(); });
  panel.hidden = false;
  check();
})();
