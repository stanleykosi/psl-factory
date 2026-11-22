document.addEventListener('click', event => {
  const button = event.target.closest('[data-add-requirement]');
  if (!button) return;
  const form = button.form;
  const total = form?.querySelector('[name="requirements-TOTAL_FORMS"]');
  const template = form?.querySelector('[data-requirement-template]');
  const rows = form?.querySelector('[data-requirement-rows]');
  if (!total || !template || !rows) return;
  const count = Number(total.value);
  if (!Number.isInteger(count) || count < 0 || count >= 100) return;
  const prefix = form.closest('#start-work-dialog') ? 'intake-' : '';
  const fragment = template.content.cloneNode(true);
  for (const node of fragment.querySelectorAll('[name], [id], [for], [aria-describedby]')) {
    for (const attribute of ['name', 'id', 'for', 'aria-describedby']) {
      const value = node.getAttribute(attribute);
      if (value) node.setAttribute(attribute, (attribute === 'name' ? '' : prefix) + value.replaceAll('__prefix__', String(count)));
    }
  }
  rows.append(fragment);
  total.value = String(count + 1);
  button.disabled = count + 1 >= 100;
  rows.lastElementChild?.querySelector('input')?.focus();
});
