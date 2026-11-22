(() => {
  const menu = document.querySelector('[data-alert-preview]');
  if (!menu) return;
  const content = menu.querySelector('[data-alert-rows]');
  let request;

  menu.addEventListener('toggle', async () => {
    request?.abort();
    if (!menu.open) return;
    const controller = new AbortController();
    request = controller;
    content.setAttribute('aria-busy', 'true');
    content.textContent = 'Loading alerts…';
    try {
      const response = await fetch(menu.dataset.alertPreview, { cache: 'no-store', signal: controller.signal });
      if (!response.ok || response.redirected) throw new Error('Alerts unavailable');
      const template = document.createElement('template');
      template.innerHTML = await response.text();
      if (menu.open && !controller.signal.aborted) content.replaceChildren(template.content);
    } catch (error) {
      if (!controller.signal.aborted) content.textContent = 'Open all alerts to see the latest updates.';
    } finally {
      if (request === controller) content.removeAttribute('aria-busy');
    }
  });

  menu.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !menu.open) return;
    menu.open = false;
    menu.querySelector('summary').focus();
  });
})();
