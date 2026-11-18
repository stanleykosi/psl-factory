(() => {
  const form = document.getElementById('answer-review');
  if (!form) return;
  const mode = form.elements.verdict;
  const answer = form.elements.answer;
  const answerField = answer.closest('p');
  const original = answer.value;
  let edited = false;
  let submitting = false;

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
    if (!event.target.closest('a') || !edited || submitting) return;
    if (!window.confirm('Leave this answer and discard your unsaved changes?')) event.preventDefault();
    else edited = false;
  });
  window.addEventListener('beforeunload', event => {
    if (edited && !submitting) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  update();
})();
