/** Full page reload after a reconcile answer, so the work item is read again; its own module so tests can stub it. */
export function reloadPage(): void {
  window.location.reload();
}
