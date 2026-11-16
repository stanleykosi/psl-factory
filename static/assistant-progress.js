if (document.querySelector('[data-assistant-wait]')) {
  window.setTimeout(() => {
    if (document.visibilityState === 'visible') window.location.reload();
  }, 8000);
}
