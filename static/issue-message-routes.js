(() => {
  const form = document.querySelector('[data-message-settings]');
  if (!form) return;
  const button = form.querySelector('[data-add-message-route]');
  const total = form.querySelector('[name="routes-TOTAL_FORMS"]');
  const template = form.querySelector('[data-message-route-template]');
  const rows = form.querySelector('[data-message-routes]');
  if (!button || !total || !template || !rows) return;
  button.addEventListener('click', () => {
    const index = Number(total.value);
    if (!Number.isInteger(index) || index < 0 || index >= 40) return;
    const fragment = template.content.cloneNode(true);
    fragment.querySelectorAll('[name], [id], label[for]').forEach(element => {
      ['name', 'id', 'for'].forEach(attribute => {
        const value = element.getAttribute(attribute);
        if (value) element.setAttribute(attribute, value.replaceAll('__prefix__', String(index)));
      });
    });
    rows.appendChild(fragment);
    total.value = String(index + 1);
    button.disabled = index + 1 >= 40;
    rows.lastElementChild?.querySelector('select, input')?.focus();
  });
})();
