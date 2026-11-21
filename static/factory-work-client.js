/* The hosted desk and the separate frontend use the same live work contract. */
function element(tag, text, attributes = {}) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

class FactoryWorkClient extends HTMLElement {
  connectedCallback() {
    this.load().catch(error => this.showError(error));
  }

  showError(error) {
    this.replaceChildren(element('h2', 'Work could not be opened'), element('p', error.message),
      element('a', 'Reload current work', { href: location.href }));
  }

  async api(path, data) {
    const options = { credentials: 'same-origin', cache: 'no-store' };
    if (data) Object.assign(options, { method: 'POST', body: JSON.stringify(data),
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.profile.csrf_token } });
    const response = await fetch('/api/v1/' + path, options);
    const value = await response.json();
    if (!response.ok) throw new Error(value.message || 'Reload and check the current record.');
    return value;
  }

  native(label, path) {
    const url = new URL((this.getAttribute('form-prefix') || '') + path, this.getAttribute('factory-origin') || location.origin);
    return element('a', label, { href: url.href });
  }

  link(label, params = {}) {
    const url = new URL(this.getAttribute('desk-path') || location.pathname, location.origin);
    url.search = new URLSearchParams(params).toString();
    return element('a', label, { href: url.href });
  }

  async load() {
    this.profile = await this.api('me');
    const nav = element('nav', undefined, { 'aria-label': 'Factory sections' });
    for (const item of this.profile.destinations) {
      nav.append(item.key === 'my_work' ? this.link(item.title) : this.native(item.title, item.django_url), ' ');
    }
    if (this.profile.startable_lines.length) nav.append(this.native('Start work', '/factory/start/'));
    this.body = element('section');
    this.replaceChildren(nav, this.body);
    const params = new URLSearchParams(location.search);
    const path = location.pathname.match(/^\/work\/(\d+)(?:\/(\w+))?\/?$/);
    const work = params.get('work') || path?.[1];
    const task = params.get('task');
    if (task && /^\d+$/.test(task)) return this.review(task);
    if (work && /^\d+$/.test(work)) return this.detail(work, params.get('history') || (path?.[2] === 'history' ? 'worker' : ''));
    if (this.profile.destinations.some(item => item.key === 'my_work')) return this.queue(params);
    this.body.append(element('h1', 'Your work'), element('p', 'Open your role assignments to see your assigned work.'));
  }

  async queue(params) {
    const selected = params.get('queue') || 'needs_me';
    const query = { queue: selected, page: params.get('page') || '1' };
    const queue = await this.api('work?' + new URLSearchParams(query));
    this.body.append(element('h1', 'My work'));
    for (const [key, label] of Object.entries({ needs_me: 'Needs my attention', mine: 'Started by me',
      active: 'Active work', decisions: 'Decisions', exceptions: 'Exceptions', verified: 'Verified outcomes' })) {
      this.body.append(this.link(label, { queue: key }), ' ');
    }
    const list = element('ul');
    for (const row of queue.items) {
      const item = element('li');
      item.append(this.link(row.title, { work: row.id }), ' · ' + row.status_label);
      list.append(item);
    }
    this.body.append(list);
    if (!queue.items.length) this.body.append(element('p', 'No matching work on this page.'));
    if (queue.limited) this.body.append(element('p', 'Some work could not be checked on this page.'));
    this.body.append(element('p', 'Page ' + queue.page));
    if (queue.page > 1) this.body.append(this.link('Previous page', { queue: selected, page: queue.page - 1 }), ' ');
    if (queue.next_page) this.body.append(this.link('Next page', { queue: selected, page: queue.next_page }));
  }

  async detail(id, history) {
    const work = await this.api('work/' + id);
    this.body.append(element('h1', work.title), element('p', work.status_label), element('p', work.next_step),
      this.native('Open full work record', work.django_url));
    for (const screen of work.screens) this.body.append(' · ', this.native('Open ' + screen.key, screen.django_url));
    for (const task of work.tasks) {
      if (task.can_decide || task.can_claim) {
        const entry = element('p');
        entry.append(this.link('Review ' + task.role + ' task ' + task.id, { work: id, task: task.id }));
        this.body.append(entry);
      }
    }
    this.body.append(element('h2', 'History'));
    for (const [key, label] of Object.entries({ worker: 'Worker steps', decision: 'Decisions', evidence: 'Evidence changes' })) {
      this.body.append(this.link(label, { work: id, history: key }), ' ');
    }
    const events = await this.api('work/' + id + '/history?kind=' + encodeURIComponent(history || 'worker'));
    for (const item of events.items) this.body.append(element('p',
      new Date(item.at).toLocaleString() + ' · ' + item.station + ' · ' + item.status));
    if (!events.items.length) this.body.append(element('p', 'No recorded entries for this filter.'));
  }

  async review(id) {
    const result = await this.api('tasks/' + id);
    const task = result.task;
    this.body.replaceChildren(element('h1', result.label), this.link('Back to work', { work: result.work_id }),
      ' · ', this.native('Open full review and supporting records', '/work/' + result.work_id + '/decision/'));
    const packet = result.invoice_packet;
    if (!packet) return;
    this.body.append(element('p', 'Invoice ' + packet.invoice_id + ' · Version ' + packet.version +
      ' · ' + packet.amount + ' ' + packet.currency));
    for (const source of packet.sources) this.body.append(element('p', 'Source ' + source.id + ' · ' +
      source.kind + ' · Version ' + source.version + ' · ' + source.sha256));
    const form = element('form');
    if (task.can_claim) {
      this.submit(form, 'Claim review', async () => {
        await this.api('tasks/' + id + '/claim', { expected_revision: task.revision });
        await this.review(id);
      });
    } else if (task.can_decide) {
      const evidence = this.select(form, 'Evidence you reviewed', result.review_evidence.map(row =>
        [row.id, '#' + row.id + ' · ' + row.source + ' · Version ' + row.version]));
      const verdict = this.select(form, 'Decision', task.verdicts.map(value => [value, value]));
      const label = element('label', 'Reason for this decision ');
      const note = element('textarea', undefined, { required: '', maxlength: '2000' });
      label.append(note);
      form.append(label);
      this.submit(form, 'Record decision', async () => {
        const saved = await this.api('tasks/' + id + '/decision', { expected_revision: task.revision,
          evidence_id: Number(evidence.value), verdict: verdict.value, note: note.value.trim() });
        form.replaceChildren(element('p', 'Decision recorded · ' + saved.verdict + ' · Review ' + saved.review_id));
      });
    }
    this.body.append(form);
  }

  select(form, title, choices) {
    const label = element('label', title + ' ');
    const select = element('select', undefined, { required: '', 'aria-label': title });
    select.append(element('option', 'Choose…', { value: '' }));
    for (const [value, name] of choices) select.append(element('option', name, { value }));
    label.append(select);
    form.append(label);
    return select;
  }

  submit(form, label, execute) {
    const button = element('button', label, { type: 'submit' });
    form.append(button);
    form.onsubmit = async event => {
      event.preventDefault();
      if (button.disabled) return;
      button.disabled = true;
      try { await execute(); }
      catch (error) {
        form.append(element('p', error.message + ' Open the current review before trying again.'),
          element('a', 'Reload review', { href: location.href }));
      }
    };
  }
}

if (!customElements.get('psl-work-client')) customElements.define('psl-work-client', FactoryWorkClient);
