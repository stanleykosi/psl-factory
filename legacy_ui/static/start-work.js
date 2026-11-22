(() => {
  const target = document.getElementById(location.hash.slice(1));
  if (target instanceof HTMLDetailsElement) target.open = true;

  const dialog = document.querySelector('#start-work-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  const body = dialog.querySelector('[data-start-work-body]');
  const back = dialog.querySelector('.start-work-back');
  const chooser = new URL(back.href);
  const create = new URL(dialog.dataset.createUrl, location.href);
  let opener;
  let request;

  function intakePage(url) {
    return url.origin === location.origin && [chooser.pathname, create.pathname].includes(url.pathname);
  }

  function carryContext(url, previous) {
    for (const key of ['queue', 'q', 'definition', 'assistant_turn']) {
      if (!url.searchParams.has(key) && previous.searchParams.has(key)) {
        url.searchParams.set(key, previous.searchParams.get(key));
      }
    }
    return url;
  }

  function status(text, url) {
    const message = document.createElement('p');
    message.setAttribute('role', 'status');
    message.textContent = text;
    body.replaceChildren(message);
    if (url) {
      const fallback = document.createElement('a');
      fallback.href = url;
      fallback.textContent = 'Open the full page';
      fallback.dataset.nativeNavigation = '';
      body.append(fallback);
    }
  }

  function searchable(container) {
    const processSearch = container.querySelector('[data-process-search]');
    if (processSearch) {
      processSearch.hidden = false;
      processSearch.querySelector('input').addEventListener('input', (event) => {
        const query = event.target.value.trim().toLocaleLowerCase();
        let found = false;
        for (const group of container.querySelectorAll('[data-process-group]')) {
          let hasRows = false;
          for (const row of group.querySelectorAll('[data-process]')) {
            row.hidden = !`${row.dataset.process} ${row.textContent}`.toLocaleLowerCase().includes(query);
            hasRows ||= !row.hidden;
          }
          group.hidden = !hasRows;
          found ||= hasRows;
        }
        container.querySelector('[data-process-empty]').hidden = found;
      });
    }
    const search = container.querySelector('[data-start-search]');
    if (!search) return;
    search.hidden = false;
    search.querySelector('input').addEventListener('input', (event) => {
      const query = event.target.value.trim().toLocaleLowerCase();
      let matches = 0;
      let startable = 0;
      for (const group of container.querySelectorAll('[data-start-group]')) {
        let groupMatches = 0;
        for (const option of group.querySelectorAll('[data-start-option]')) {
          const input = option.querySelector('input');
          option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
          input.disabled = option.hidden || input.hasAttribute('data-start-unavailable');
          if (option.hidden) input.checked = false;
          else {
            groupMatches += 1;
            if (!input.disabled) startable += 1;
          }
        }
        group.hidden = groupMatches === 0;
        matches += groupMatches;
      }
      container.querySelector('[data-start-empty]').hidden = matches !== 0;
      container.querySelector('button[type="submit"]').disabled = startable === 0;
    });
  }

  async function load(url, submission) {
    request?.abort();
    const control = new AbortController();
    request = control;
    body.setAttribute('aria-busy', 'true');
    if (!submission) {
      back.hidden = true;
      status('Loading…');
    }
    try {
      const response = await fetch(url, {
        cache: 'no-store', signal: control.signal,
        ...(submission && { method: 'POST', body: submission }),
      });
      const current = new URL(response.url);
      if (!dialog.open || control.signal.aborted) return;
      if (response.redirected && !intakePage(current)) {
        if (current.origin === location.origin) location.assign(current);
        return;
      }
      if ((!response.ok && response.status !== 422 && response.status !== 409) || !intakePage(current)) {
        throw new Error('Intake unavailable');
      }
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!dialog.open || control.signal.aborted) return;
      const panel = doc.querySelector('main[data-start-work-page]');
      if (!panel) throw new Error('Missing intake form');
      const idReferences = ['for', 'aria-describedby', 'aria-labelledby', 'aria-controls'];
      const ids = new Set([...panel.querySelectorAll('[id]')].map((element) => element.id));
      for (const element of panel.querySelectorAll('[id], [for], [aria-describedby], [aria-labelledby], [aria-controls]')) {
        if (element.id) element.id = `intake-${element.id}`;
        for (const name of idReferences) {
          const value = element.getAttribute(name);
          if (value) element.setAttribute(name, value.split(/\s+/).map((id) => ids.has(id) ? `intake-${id}` : id).join(' '));
        }
      }
      for (const link of panel.querySelectorAll('a[href]')) {
        const href = new URL(link.getAttribute('href'), current);
        link.href = href.pathname === create.pathname ? carryContext(href, current) : href;
      }
      for (const form of panel.querySelectorAll('form')) {
        form.setAttribute('action', new URL(form.getAttribute('action') || current.href, current).href);
      }
      body.replaceChildren(...panel.childNodes);
      back.hidden = current.pathname === chooser.pathname;
      searchable(body);
      const heading = body.querySelector('h1');
      if (heading) {
        heading.tabIndex = -1;
        heading.focus();
      }
    } catch (error) {
      if (control.signal.aborted) return;
      if (!submission) {
        status('The form could not be loaded.', url);
        return;
      }
      body.querySelector('[data-start-uncertain]')?.remove();
      const warning = document.createElement('p');
      warning.dataset.startUncertain = '';
      warning.setAttribute('role', 'alert');
      warning.textContent = 'The request outcome could not be confirmed. Check My work, or submit this same form again to check the original request.';
      body.prepend(warning);
    } finally {
      if (request === control) body.removeAttribute('aria-busy');
    }
  }

  document.addEventListener('click', (event) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || 'nativeNavigation' in link.dataset) return;
    const entry = link.dataset.startWork;
    if (entry === undefined && !dialog.contains(link)) return;
    const url = entry === 'default' && matchMedia('(max-width: 650px)').matches ? chooser : new URL(link.href);
    if (!intakePage(url)) return;
    event.preventDefault();
    if (!dialog.open) {
      opener = link;
      dialog.showModal();
    }
    void load(url);
  });

  dialog.addEventListener('submit', (event) => {
    const form = event.target;
    // The weekly report has submit buttons named action. Read the attribute
    // directly so a named control cannot shadow the native form property.
    const action = new URL(form.getAttribute('action') || location.href, location.href);
    if (!intakePage(action)) return;
    event.preventDefault();
    if ((form.getAttribute('method') || 'get').toLowerCase() === 'post') {
      if (!body.hasAttribute('aria-busy')) void load(action, new FormData(form, event.submitter));
      return;
    }
    const url = new URL(action.pathname, action.origin);
    url.search = new URLSearchParams(new FormData(form, event.submitter));
    void load(carryContext(url, action));
  });
  dialog.querySelector('[data-close-start-work]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    request?.abort();
    body.replaceChildren();
    opener?.focus();
  });
  document.querySelectorAll('[data-start-chooser]').forEach(searchable);
})();
