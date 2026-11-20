document.querySelectorAll('[data-source-picker]').forEach((picker) => {
  const summary = picker.querySelector('summary');
  const searchLabel = picker.querySelector('[data-source-search]');
  const search = searchLabel.querySelector('input');
  const empty = picker.querySelector('[data-source-no-matches]');
  const choices = Array.from(picker.querySelectorAll('[data-source-choices] input[type="checkbox"]'));
  const labels = choices.map((choice) => choice.closest('label'));
  if (choices.length === 0 || labels.some((label) => !label)) return;

  searchLabel.hidden = false;
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    labels.forEach((label) => {
      label.hidden = !label.textContent.toLocaleLowerCase().includes(query);
    });
    empty.hidden = labels.some((label) => !label.hidden);
  });

  picker.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      picker.open = false;
      summary.focus();
      return;
    }

    if (event.key === 'Enter' && (event.target === search || choices.includes(event.target))) {
      event.preventDefault();
      if (event.target !== search) event.target.click();
      return;
    }

    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
    const visible = choices.filter((choice, index) => !choice.disabled && !labels[index].hidden);
    if (event.target !== search && !visible.includes(event.target)) return;
    event.preventDefault();
    const direction = event.key === 'ArrowDown' ? 1 : -1;
    let next = visible[visible.indexOf(event.target) + direction];
    if (event.target === search && direction === -1) next = visible.at(-1);
    (next || search).focus();
  });
});
