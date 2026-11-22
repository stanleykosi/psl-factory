const recoveryCodeForm = document.querySelector('#recovery-code-form');
const recoveryCode = window.location.hash.slice(1);
if (recoveryCodeForm && /^[a-f0-9-]{36}:[A-Za-z0-9_-]{43}$/.test(recoveryCode)) {
  window.history.replaceState(null, '', window.location.pathname);
  recoveryCodeForm.elements.namedItem('token').value = recoveryCode;
  recoveryCodeForm.requestSubmit();
}
