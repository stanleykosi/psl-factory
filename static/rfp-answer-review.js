(() => {
  const form = document.getElementById('answer-review');
  if (!form) return;
  const mode = form.elements.verdict;
  const answer = form.elements.answer;
  const answerField = answer.closest('p');
  const original = answer.value;
  const dialog = document.getElementById('discard-answer-dialog');
  const keepEditing = document.getElementById('keep-answer-editing');
  const discard = document.getElementById('discard-answer-edits');
  let edited = false;
  let submitting = false;
  let pendingNavigation = null;
  let returnFocus = null;

  const confirmDiscard = navigation => {
    pendingNavigation = navigation;
    returnFocus = document.activeElement;
    dialog.showModal();
  };

  keepEditing.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    pendingNavigation = null;
    returnFocus?.focus();
  });
  discard.addEventListener('click', () => {
    const navigate = pendingNavigation;
    edited = false;
    dialog.close();
    navigate?.();
  });

  const update = () => {
    answerField.hidden = mode.value === 'accept';
    answer.required = mode.value !== 'accept';
    if (mode.value === 'replace' && answer.value === original) answer.value = '';
    if (mode.value === 'edit' && !answer.value) answer.value = original;
  };
  mode.addEventListener('change', update);
  form.addEventListener('input', () => { edited = true; });
  form.addEventListener('change', () => { edited = true; });
  form.addEventListener('submit', () => { submitting = true; });
  document.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || !edited || submitting || link.hasAttribute('download') ||
        (link.target && link.target !== '_self') || !link.getAttribute('href') ||
        link.getAttribute('href').startsWith('#')) return;
    event.preventDefault();
    confirmDiscard(() => { window.location.assign(link.href); });
  });
  document.addEventListener('submit', event => {
    if (event.target === form || !edited || submitting) return;
    event.preventDefault();
    const target = event.target;
    const submitter = event.submitter;
    confirmDiscard(() => {
      if (submitter) target.requestSubmit(submitter);
      else target.requestSubmit();
    });
  });
  window.addEventListener('beforeunload', event => {
    if (edited && !submitting) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  update();
})();
