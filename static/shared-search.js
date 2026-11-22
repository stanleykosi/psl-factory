(() => {
  for (const field of document.querySelectorAll('[data-shared-search]')) {
    const input = field.querySelector('input[type="search"]');
    const clear = field.querySelector('[data-clear-search]');
    const update = () => { clear.hidden = !input.value && !input.defaultValue; };

    input.addEventListener('input', update);
    input.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || clear.hidden) return;
      event.preventDefault();
      event.stopPropagation();
      clear.click();
    });
    clear.addEventListener('keydown', event => {
      if (event.key !== ' ') return;
      event.preventDefault();
      clear.click();
    });
    clear.addEventListener('click', event => {
      if (input.defaultValue || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      event.stopPropagation();
      input.value = '';
      update();
      input.focus();
    });

    update();
    if (location.hash === '#' + input.id) input.focus({ preventScroll: true });
  }
})();
