(() => {
  const summary = document.getElementById('add-document');
  const details = summary?.closest('details');
  if (!details) return;

  const openForm = () => { details.open = true; };
  document.querySelector('a[href="#add-document"]')?.addEventListener('click', openForm);
  window.addEventListener('hashchange', () => {
    if (window.location.hash === '#add-document') openForm();
  });
  if (window.location.hash === '#add-document') openForm();
})();
