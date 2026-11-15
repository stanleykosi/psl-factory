import { chromium } from '/Users/Hunchoo/psl-factory-worktrees/f-14/frontend/node_modules/playwright/index.mjs';

const BASE = 'http://localhost:4511';
const MOCK = 'http://127.0.0.1:4512';
const D = { width: 1440, height: 900 };
const P = { width: 390, height: 844 };
const out = [];
const log = (name, ok, detail) => { out.push({ name, ok, detail }); console.log(`${ok ? 'OK  ' : 'FAIL'} ${name} :: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`); };
const reset = () => fetch(`${MOCK}/__mock/reset`, { method: 'POST' });

const browser = await chromium.launch();
async function ctx(viewport, persona = 'finance_lead', extra = []) {
  const c = await browser.newContext({ viewport, timezoneId: 'Africa/Lagos' });
  await c.addCookies([{ name: 'psl_mock_persona', value: persona, url: BASE }, ...extra.map(([n, v]) => ({ name: n, value: v, url: BASE }))]);
  const page = await c.newPage();
  const reqs = [];
  page.on('request', (r) => { if (r.url().includes('/api/')) reqs.push(`${r.method()} ${new URL(r.url()).pathname}${new URL(r.url()).search}`); });
  return { c, page, reqs };
}
async function loaded(page) {
  await page.waitForFunction(() => document.querySelectorAll('main h1').length > 0 && !document.querySelector('main [role=status][aria-busy=true]'), null, { timeout: 15000 });
  await page.waitForTimeout(400);
}
const nonGet = (reqs) => reqs.filter((r) => !r.startsWith('GET '));

const BOARDS = {
  'W-1701': ['finance_lead', null], 'W-1702': ['pm', 'Ready to begin'], 'W-1703': ['pm', 'Drafting the invoice'],
  'W-1704': ['pm', 'Waiting on the client'], 'W-1705': ['finance_lead', 'Verified'], 'W-1706': ['finance_lead', 'Issue and send'],
  'W-1707': ['finance_lead', 'Cancelled'], 'W-1708': ['pm', 'Stopped · owner needed'], 'W-1709': ['pm', 'Setup needed'],
  'W-1710': ['finance_lead', 'Awaiting reconciliation'], 'W-1711': ['finance_lead', 'Confirm what happened'],
};
const EXC = new Set(['W-1708', 'W-1709', 'W-1710', 'W-1711']);

await reset();
// 1. Board states at both widths
for (const [id, [persona, heading]] of Object.entries(BOARDS)) {
  for (const [w, vp] of [['1440', D], ['390', P]]) {
    const { c, page, reqs } = await ctx(vp, persona);
    await page.goto(`${BASE}/work/${id}`); await loaded(page);
    const r = await page.evaluate(() => {
      const main = document.querySelector('main');
      const fixed = [...document.querySelectorAll('body *')].filter((e) => getComputedStyle(e).position === 'fixed' && e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().bottom >= innerHeight - 1 && e.getBoundingClientRect().top > innerHeight / 2);
      const facts = [...document.querySelectorAll('[aria-label="Facts"] > *')].map((e) => e.textContent.trim());
      return {
        h1: document.querySelectorAll('h1').length, title: document.querySelector('main h1')?.textContent,
        tabs: [...document.querySelectorAll('nav[aria-label="Work item"] a')].map((a) => `${a.textContent.trim()}->${a.getAttribute('href')}`),
        text: main.textContent, scroll: document.documentElement.scrollWidth,
        bar: fixed.map((e) => `${e.className}|${e.innerText.replace(/\s+/g, ' ').slice(0, 80)}`),
        facts,
        exc: [...main.querySelectorAll('a[href="/exceptions"]')].map((a) => a.className + ':' + a.getBoundingClientRect().height),
        buttons: [...main.querySelectorAll('button')].map((b) => b.textContent.trim()),
      };
    });
    const problems = [];
    if (r.h1 !== 1) problems.push(`h1=${r.h1}`);
    if (w === '1440' && heading && !r.text.includes(heading)) problems.push(`missing heading ${heading}`);
    if (w === '1440' && !(r.tabs.length === 2)) problems.push(`tabs ${r.tabs}`);
    if (r.scroll > vp.width) problems.push(`scroll ${r.scroll}`);
    if (EXC.has(id) !== (r.exc.length > 0)) problems.push(`exceptions link ${JSON.stringify(r.exc)}`);
    if (nonGet(reqs).length) problems.push(`nonGET ${nonGet(reqs)}`);
    if (/Approve|Reject/.test(r.buttons.join('|'))) problems.push(`decision buttons ${r.buttons}`);
    log(`${id} @${w} (${persona})`, problems.length === 0, { problems, tabs: r.tabs, bar: w === '390' ? r.bar : undefined, exc: r.exc, buttons: r.buttons, reqs: [...new Set(reqs)] });
    if (id === 'W-1710' || id === 'W-1711') {
      const sent = r.facts.find((f) => /^SENT/i.test(f));
      log(`${id} @${w} Sent fact`, !!sent && /Unknown/.test(sent) && !/\b0\b/.test(sent), sent ?? r.facts);
    }
    await c.close();
  }
}

// 2. Live items W-1001..W-1006: no presentation block, Unknown facts
for (const n of [1, 2, 3, 4, 5, 6]) {
  const id = `W-100${n}`;
  const api = await (await fetch(`${BASE}/api/v1/work/${id}`, { headers: { cookie: 'psl_mock_persona=finance_lead' } })).json();
  const { c, page, reqs } = await ctx(D);
  await page.goto(`${BASE}/work/${id}`); await loaded(page);
  const r = await page.evaluate(() => ({
    facts: [...document.querySelectorAll('[aria-label="Facts"] > *')].map((e) => e.textContent.trim()),
    statepanel: document.querySelectorAll('.work-statepanel').length, h1: document.querySelectorAll('h1').length,
    tabs: [...document.querySelectorAll('nav[aria-label="Work item"] a')].map((a) => a.textContent.trim()),
    sub: document.querySelector('header, main')?.innerText.match(/revision \d+/)?.[0],
  }));
  const unknownNames = (api.facts ?? []).filter((f) => f.status === 'unknown').map((f) => f.name);
  const problems = [];
  if ('presentation' in api) problems.push('api has presentation');
  if (r.statepanel) problems.push('state panel rendered');
  if (r.facts.length !== 6) problems.push(`facts ${r.facts.length}`);
  for (const f of r.facts) if (/\b0\b|^\w+$/.test(f.replace(/^[A-Z ]+/, '').trim()) && !/Earned|Not yet|Unknown|In progress/.test(f)) problems.push(`odd fact ${f}`);
  const unkShown = r.facts.filter((f) => /Unknown/.test(f)).length;
  if (unkShown < unknownNames.length) problems.push(`unknown facts ${unknownNames} shown ${unkShown}`);
  if (nonGet(reqs).length) problems.push(`nonGET ${nonGet(reqs)}`);
  if (r.tabs.length !== 2) problems.push(`tabs ${r.tabs}`);
  log(`${id} live`, problems.length === 0, { problems, facts: r.facts, unknownNames, sub: r.sub, tabs: r.tabs });
  await c.close();
}

// 3. Tab strip and Open the decision
{
  const { c, page, reqs } = await ctx(D);
  await page.goto(`${BASE}/work/W-1701`); await loaded(page);
  const link = page.getByRole('link', { name: 'Open the decision' });
  const href = await link.getAttribute('href');
  await page.locator('nav[aria-label="Work item"]').getByRole('link', { name: /History/ }).click();
  await page.waitForURL('**/work/W-1701/history'); await loaded(page);
  const histCurrent = await page.locator('nav[aria-label="Work item"] a[aria-current=page]').textContent().catch(() => null);
  await page.locator('nav[aria-label="Work item"]').getByRole('link', { name: 'Overview' }).click();
  await page.waitForURL(/\/work\/W-1701$/); await loaded(page);
  const wiNonGet = nonGet(reqs).length;
  await page.getByRole('link', { name: 'Open the decision' }).click();
  await page.waitForURL('**/decide**'); await loaded(page);
  const decideH1 = await page.locator('main h1').first().textContent();
  log('W-1701 tabs + Open the decision', href === '/work/W-1701/decide?task=T-1701' && /History/.test(histCurrent ?? '') && wiNonGet === 0, { href, histCurrent, decideUrl: page.url(), decideH1, wiNonGet, afterDecidePage: nonGet(reqs) });
  await c.close();
}
{
  const { c, page } = await ctx(D);
  await page.goto(`${BASE}/work/W-1002`); await loaded(page);
  const panelLinks = await page.locator('[aria-label="Current human task"]').evaluateAll((els) => els.map((e) => e.querySelectorAll('a,button').length));
  const r = await page.evaluate(() => { const s = [...document.querySelectorAll('*')].find((e) => e.children.length === 0 && /^revision \d+$/.test(e.textContent.trim())); const t = document.querySelector('nav[aria-label="Work item"]'); const a = s?.getBoundingClientRect(), b = t?.getBoundingClientRect(); return { a: a && [a.left, a.right, a.top, a.bottom], b: b && [b.left, b.right, b.top, b.bottom], overlap: !!(a && b && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) }; });
  log('W-1002 wrong user: no task control; TECH-3-1 revision vs tabs', panelLinks.every((n) => n === 0) && r.a && !r.overlap, { panelLinks, ...r });
  await c.close();
}

// 4. History with paging and filters
{
  const { c, page, reqs } = await ctx(D);
  await page.goto(`${BASE}/work/W-1705/history`); await loaded(page);
  const a = await page.evaluate(() => ({
    tabs: [...document.querySelectorAll('nav[aria-label="Work item"] a')].map((x) => x.textContent.trim()),
    filter: [...document.querySelectorAll('[role=radiogroup][aria-label=Show] [role=radio], [role=radiogroup][aria-label=Show] button, [role=radiogroup][aria-label=Show] label')].map((x) => x.textContent.trim()),
    rows: document.querySelectorAll('main tbody tr').length, about: !!document.querySelector('[aria-label="About history"]'),
  }));
  await page.getByRole('radio', { name: /Decisions/ }).click(); await page.waitForTimeout(800);
  const decRows = await page.locator('main tbody tr').count();
  log('W-1705 history desktop + Decisions filter', a.rows === 7 && a.about && reqs.some((r) => r.includes('kind=decisions')) && nonGet(reqs).length === 0, { ...a, decRows, reqs });
  await c.close();
}
{
  const { c, page, reqs } = await ctx(D);
  await page.goto(`${BASE}/work/W-1004/history`); await loaded(page);
  const count = () => page.locator('main tbody tr').count();
  const n0 = await count();
  await page.locator('main select').selectOption('10'); await page.waitForTimeout(800);
  const n1 = await count();
  await page.getByRole('button', { name: 'Show more' }).click(); await page.waitForTimeout(800);
  const n2 = await count();
  const more = await page.getByRole('button', { name: 'Show more' }).count();
  await page.locator('main select').selectOption('50');
  await page.waitForTimeout(800);
  const n3 = await count();
  log('W-1004 history paging: 10 -> Show more -> 12, rows per page 20', n1 === 10 && n2 === 12 && more === 0 && reqs.some((r) => /cursor=/.test(r)) && reqs.some((r) => /limit=50/.test(r)) && nonGet(reqs).length === 0, { n0, n1, n2, more, n3, reqs: reqs.filter((r) => r.includes('history')) });
  await c.close();
}
{
  const { c, page, reqs } = await ctx(P);
  await page.goto(`${BASE}/work/W-1705/history`); await loaded(page);
  const r = await page.evaluate(() => ({ h1: document.querySelector('main h1')?.textContent, back: [...document.querySelectorAll('a')].filter((a) => /←/.test(a.textContent)).map((a) => `${a.textContent.trim()}->${a.getAttribute('href')}`), text: document.querySelector('main').innerText.slice(0, 120), scroll: document.documentElement.scrollWidth, btn: [...document.querySelectorAll('main button')].map((b) => b.textContent.trim()) }));
  log('W-1705 history phone', r.h1 === 'History · INV-0412' && r.back.some((b) => b === '← Invoice->/work/W-1705') && r.scroll <= 390 && nonGet(reqs).length === 0, r);
  await c.close();
}

// 5. Phone: back link, disclosures, pinned bar
{
  const { c, page, reqs } = await ctx(P);
  await page.goto(`${BASE}/work/W-1701`); await loaded(page);
  const back = await page.evaluate(() => [...document.querySelectorAll('a')].filter((a) => /←/.test(a.textContent)).map((a) => `${a.textContent.trim()}->${a.getAttribute('href')}|inMain=${!!a.closest('main')}`));
  const d = page.getByRole('button', { name: /See his steps/ });
  const e0 = await d.getAttribute('aria-expanded'); await d.click(); const e1 = await page.locator('button[aria-expanded]').first().getAttribute('aria-expanded');
  const bar = await page.evaluate(() => { const e = document.querySelector('.psl-panel--decide'); const r = e?.getBoundingClientRect(); return e && { pos: getComputedStyle(e).position, bottom: r.bottom, text: e.innerText.replace(/\s+/g, ' ').slice(0, 120), linkH: e.querySelector('a')?.getBoundingClientRect().height }; });
  await page.mouse.wheel(0, 3000); await page.waitForTimeout(300);
  const bar2 = await page.evaluate(() => document.querySelector('.psl-panel--decide')?.getBoundingClientRect().bottom);
  log('W-1701 phone back link, See his steps, pinned decide bar', back.includes('← Queue->/my-work|inMain=false') && e0 === 'false' && e1 === 'true' && bar?.pos === 'fixed' && Math.abs(bar.bottom - 844) < 2 && Math.abs(bar2 - 844) < 2 && nonGet(reqs).length === 0, { back, e0, e1, bar, bar2 });
  await c.close();
}
{
  const { c, page, reqs } = await ctx(P);
  await page.goto(`${BASE}/work/W-1706`); await loaded(page);
  const d = page.getByRole('button', { name: /Preview the invoice/ });
  const e0 = await d.getAttribute('aria-expanded'); await d.click();
  const vis = await page.getByText("TEST TEMPLATE · NOT PSL'S REAL INVOICE").first().isVisible();
  log('W-1706 phone Preview the invoice', e0 === 'false' && vis && nonGet(reqs).length === 0, { e0, vis, reqs: [...new Set(reqs)] });
  await c.close();
}
{
  // pinned bar does not cover the last content on a long exception page
  const { c, page } = await ctx(P, 'pm');
  await page.goto(`${BASE}/work/W-1708`); await loaded(page);
  await page.mouse.wheel(0, 5000); await page.waitForTimeout(300);
  const r = await page.evaluate(() => { const bar = document.querySelector('.work-phonebar'); const b = bar?.getBoundingClientRect(); const exc = document.querySelector('main a[href="/exceptions"]')?.getBoundingClientRect(); return { bar: b && [b.top, b.bottom], pos: bar && getComputedStyle(bar).position, exc: exc && [exc.top, exc.bottom], text: bar?.innerText.replace(/\s+/g, ' ') }; });
  log('W-1708 phone pinned bar at scroll end, not covering See all exceptions', r.pos === 'fixed' && r.exc && r.exc[1] <= r.bar[0] + 0.5, r);
  await c.close();
}

// 6. See all exceptions
{
  const { c, page } = await ctx(D, 'pm');
  await page.goto(`${BASE}/work/W-1708`); await loaded(page);
  await page.getByRole('link', { name: 'See all exceptions' }).click();
  await page.waitForURL('**/exceptions'); await loaded(page);
  log('W-1708 See all exceptions opens /exceptions', true, { url: page.url(), h1: await page.locator('main h1').first().textContent() });
  await c.close();
}

// 7. No access 403/404, signed out 401
async function scen(page, id, code) {
  await page.route(`**/api/v1/work/${id}*`, (route) => route.continue({ headers: { ...route.request().headers(), 'x-mock-scenario': code } }));
}
for (const [label, id, code] of [['W-1099 404', 'W-1099', null], ['scenario 403', 'W-1001', '403'], ['scenario 404', 'W-1001', '404']]) {
  for (const [w, vp] of [['1440', D], ['390', P]]) {
    const { c, page } = await ctx(vp, 'finance_lead');
    if (code) await scen(page, id, code);
    await page.goto(`${BASE}/work/${id}`); await loaded(page);
    const r = await page.evaluate((id) => ({ h1: [...document.querySelectorAll('h1')].map((h) => h.textContent), hasId: document.body.innerText.includes(id) || document.title.includes(id), back: [...document.querySelectorAll('main a')].map((a) => `${a.textContent.trim()}->${a.getAttribute('href')}`), tag: document.body.innerText.includes('NO ACCESS'), title: document.title }), id);
    log(`${label} @${w}`, r.h1.length === 1 && r.h1[0] === "You can't open this work item" || r.h1[0] === 'You can’t open this work item' ? !r.hasId && r.back.includes('Back to my queue->/my-work') : false, r);
    await c.close();
  }
}
{
  const { c, page } = await ctx(D, 'finance_lead');
  await scen(page, 'W-1001', '401');
  await page.goto(`${BASE}/work/W-1001`); await loaded(page).catch(() => {});
  const r = await page.evaluate(() => ({ text: document.querySelector('main')?.innerText.slice(0, 200), links: [...document.querySelectorAll('main a')].map((a) => a.getAttribute('href')), hasId: document.body.innerText.includes('W-1001') }));
  log('signed out 401', r.links.some((h) => /next=(%2F|\/)work(%2F|\/)W-1001/.test(h ?? '')), r);
  await c.close();
}

// 8. 500 then retry
{
  const { c, page, reqs } = await ctx(D);
  let first = true;
  await page.route('**/api/v1/work/W-1001', async (route) => {
    if (first) { first = false; return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ code: 'server_error', message: 'boom' }) }); }
    return route.continue();
  });
  await page.goto(`${BASE}/work/W-1001`); await page.waitForSelector('text=Try again', { timeout: 15000 });
  const err = await page.evaluate(() => document.querySelector('main').innerText.replace(/\s+/g, ' ').slice(0, 200));
  await page.getByRole('button', { name: 'Try again' }).click(); await loaded(page);
  const after = await page.evaluate(() => ({ h1: document.querySelector('main h1')?.textContent, facts: document.querySelectorAll('[aria-label="Facts"] > *').length }));
  log('500 then Try again', /Reference/.test(err) && after.facts === 6, { err, after, reqs: reqs.filter((r) => r.includes('W-1001')) });
  await c.close();
}

// 9. Polling: W-1703 polls every 5 s; W-1704 does not
for (const [id, persona, expectPoll] of [['W-1703', 'pm', true], ['W-1704', 'pm', false], ['W-1711', 'finance_lead', false]]) {
  const { c, page, reqs } = await ctx(D, persona);
  await page.goto(`${BASE}/work/${id}`); await loaded(page);
  const t0 = reqs.filter((r) => r === `GET /api/v1/work/${id}`).length;
  await page.waitForTimeout(11000);
  const t1 = reqs.filter((r) => r === `GET /api/v1/work/${id}`).length;
  await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true }); Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); });
  await page.waitForTimeout(11000);
  const t2 = reqs.filter((r) => r === `GET /api/v1/work/${id}`).length;
  const ok = expectPoll ? t1 - t0 >= 2 && t2 - t1 === 0 : t1 === t0 && t2 === t1;
  log(`${id} polling (expect ${expectPoll})`, ok && nonGet(reqs).length === 0, { t0, t1, t2 });
  await c.close();
}

// 10. F-09 response entry on the work item page
{
  await reset();
  const { c, page, reqs } = await ctx(D);
  await page.goto(`${BASE}/work/W-1601`); await loaded(page);
  const links = await page.locator('[aria-label="Current human task"] a').evaluateAll((as) => as.map((a) => `${a.textContent.trim()}->${a.getAttribute('href')}`));
  await page.locator('[aria-label="Current human task"] a').first().click(); await page.waitForLoadState('networkidle'); await loaded(page);
  const h1 = await page.locator('main h1').first().textContent();
  log('W-1601 response entry link from the work item page', links.length === 1 && !/Open the decision/.test(links[0]) && nonGet(reqs).length === 0, { links, url: page.url(), h1 });
  await c.close();
  const { c: c2, page: p2 } = await ctx(D);
  await p2.goto(`${BASE}/work/W-1608`); await loaded(p2);
  const l2 = await p2.locator('[aria-label="Current human task"] a, [aria-label="Current human task"] button').count();
  log('W-1608 response task, you_can_act false: no entry', l2 === 0, { l2 });
  await c2.close();
}

// 11. Reconcile panel on W-1711 (and success on W-1603)
async function reconcile(id, choice, extra = [], vp = D) {
  await reset();
  const { c, page, reqs } = await ctx(vp, 'finance_lead', extra);
  if (extra.length) await c.clearCookies(), await c.addCookies([{ name: 'psl_mock_persona', value: 'finance_lead', url: BASE }]);
  await page.goto(`${BASE}/work/${id}`); await loaded(page);
  if (extra.length) await c.addCookies(extra.map(([n, v]) => ({ name: n, value: v, url: BASE })));
  const before = await page.evaluate(() => document.querySelector('main [class*=tag]')?.textContent);
  const opts = await page.getByRole('radiogroup', { name: 'Confirm what happened' }).getByRole('radio').evaluateAll((rs) => rs.map((r) => r.value));
  await page.locator(`input[type=radio][value=${choice}]`).check();
  await page.getByRole('button', { name: 'Record and continue' }).click();
  await page.waitForTimeout(2500);
  const r = await page.evaluate(() => ({ alert: [...document.querySelectorAll('[role=alert],[role=status]')].map((e) => e.textContent.trim()).filter(Boolean), tag: document.querySelector('main [class*=tag]')?.textContent, h1: document.querySelector('main h1')?.textContent, text: document.querySelector('main').innerText.slice(0, 300).replace(/\s+/g, ' ') }));
  const posts = reqs.filter((x) => !x.startsWith('GET '));
  await c.close();
  return { opts, before, ...r, posts };
}
{
  const s = await reconcile('W-1603', 'not_delivered');
  log('W-1603 reconcile success (not_delivered) through the F-14 page', s.posts.length === 1 && s.tag !== s.before, s);
  const u = await reconcile('W-1711', 'unknown');
  log('W-1711 reconcile Unknown', u.posts.length === 1, u);
  const n = await reconcile('W-1711', 'not_delivered');
  log('W-1711 reconcile Not delivered', n.posts.length === 1, n);
  const st = await reconcile('W-1711', 'unknown', [['psl_mock_scenario', '409']]);
  log('W-1711 reconcile 409 stale', st.posts.length === 1 && st.alert.some((a) => /changed/.test(a)), st);
  const fb = await reconcile('W-1711', 'unknown', [['psl_mock_scenario', '403']]);
  log('W-1711 reconcile 403', fb.posts.length === 1, fb);
  const iv = await reconcile('W-1711', 'unknown', [['psl_mock_scenario', '422']]);
  log('W-1711 reconcile 422', iv.posts.length === 1, iv);
  const ph = await reconcile('W-1711', 'unknown', [], P);
  log('W-1711 reconcile Unknown @390', ph.posts.length === 1, ph);
}
await reset();
await browser.close();
console.log(`\n${out.filter((o) => o.ok).length}/${out.length} OK`);
