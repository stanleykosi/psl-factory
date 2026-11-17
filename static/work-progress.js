(() => {
  const progress = document.querySelector('[data-work-watch]');
  if (!progress) return;

  let edited = progress.dataset.preserveForm === 'true';
  let submitting = false;
  document.addEventListener('input', event => {
    if (event.target.closest('form')) edited = true;
  });
  document.addEventListener('change', event => {
    if (event.target.closest('form')) edited = true;
  });
  document.addEventListener('submit', () => { submitting = true; });

  const notice = document.createElement('div');
  notice.hidden = true;
  notice.setAttribute('role', 'status');
  const message = document.createElement('p');
  message.textContent = 'Background work is continuing. Your form edits are kept on this page.';
  const refresh = document.createElement('button');
  refresh.type = 'button';
  refresh.textContent = 'Refresh this work';
  refresh.addEventListener('click', () => {
    if (!edited || window.confirm('Refresh this work and discard your unsaved form edits?')) {
      window.location.reload();
    }
  });
  notice.append(message, refresh);
  progress.append(notice);

  const update = () => {
    if (submitting) return;
    if (document.visibilityState !== 'visible') {
      document.addEventListener('visibilitychange', update, { once: true });
      return;
    }
    if (edited) {
      notice.hidden = false;
      return;
    }
    window.location.reload();
  };
  window.setTimeout(update, 8000);
})();
