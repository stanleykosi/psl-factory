(() => {
  const correction = document.querySelector('[data-returned-schedule-correction]');
  if (!correction) return;

  const drawer = correction.querySelector('dialog');
  if (typeof drawer.showModal !== 'function') return;

  const form = correction.querySelector('[data-correction-form]');
  const trigger = correction.querySelector('[data-open-correction]');
  const body = drawer.querySelector('[data-correction-drawer-body]');
  const mobile = window.matchMedia('(max-width: 650px)');

  function positionForm() {
    if (mobile.matches) {
      body.lastElementChild.before(form);
      trigger.hidden = false;
    } else {
      if (drawer.open) drawer.close();
      trigger.hidden = true;
      trigger.after(form);
    }
  }

  trigger.addEventListener('click', () => drawer.showModal());
  drawer.addEventListener('close', () => {
    if (!trigger.hidden) trigger.focus();
  });
  drawer.querySelectorAll('[data-close-correction]').forEach(button => {
    button.addEventListener('click', () => drawer.close());
  });
  mobile.addEventListener('change', positionForm);
  positionForm();
  if (mobile.matches && form.hasAttribute('data-show-errors')) drawer.showModal();
})();
