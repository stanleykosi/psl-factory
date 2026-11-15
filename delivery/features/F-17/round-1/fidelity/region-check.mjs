#!/usr/bin/env node
// F-17 region-level design check (D-59, design engineer, 14 Nov). The line workspace frame has no board of its
// own, so each named area of the line boards is compared with the same area of the frame's fixture page.
// For each region and width: draw the board with the fidelity tool's own renderer, open both screens, find the
// region by its text on each side, hide everything outside it (its ancestors stay, so their styles apply), lay
// the page region out at the board region's width, then run the tool's extractInBrowser and compare on what is
// left and visualInBrowser on the two element screenshots. Pass: coverage 100% after approved exceptions and
// visual >= 85 (D-59). Nothing here changes the tool.
//
// usage: node region-check.mjs --tool <software-factory>/packages/design/fidelity --playwright <playwright/index.mjs>
//          --design <worktree>/design --base http://localhost:4701 --regions regions.json --exceptions fidelity-exceptions.json
//          --out <dir> [--mock http://127.0.0.1:4702] [--only name,...] [--widths 1440,390]
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function args(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i += 2) o[argv[i].replace(/^--/, '')] = argv[i + 1];
  return o;
}

const o = args(process.argv.slice(2));
for (const k of ['tool', 'playwright', 'design', 'base', 'regions', 'out']) if (!o[k]) throw new Error(`--${k} is required`);
const tool = path.resolve(o.tool);
const { renderBoard, canvasSize } = await import(pathToFileURL(path.join(tool, 'dc-template.mjs')).href);
const { extractInBrowser } = await import(pathToFileURL(path.join(tool, 'extract.mjs')).href);
const { compare } = await import(pathToFileURL(path.join(tool, 'compare.mjs')).href);
const { visualInBrowser } = await import(pathToFileURL(path.join(tool, 'visual.mjs')).href);
const pw = await import(pathToFileURL(path.resolve(o.playwright)).href);
const chromium = (pw.chromium ?? pw.default.chromium);

const MIN_VISUAL = 85;
const MIN_COVERAGE = 100;
const regions = JSON.parse(fs.readFileSync(o.regions, 'utf8')).regions;
const allExceptions = o.exceptions ? JSON.parse(fs.readFileSync(o.exceptions, 'utf8')).exceptions : [];
const only = o.only ? new Set(o.only.split(',')) : null;
const widths = (o.widths ?? '1440,390').split(',').map(Number);
const out = path.resolve(o.out);
fs.mkdirSync(out, { recursive: true });

/** Runs in the browser: finds the region by its text, hides everything outside it, marks its root. */
function isolate({ text, root, width }) {
  const norm = (s) => (s || '').replace(/[⁣⁤]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  const target = norm(text);
  // The smallest visible element whose words include the text.
  let found = null;
  for (const el of document.body.querySelectorAll('*')) {
    if (!el.getClientRects().length || !norm(el.innerText).includes(target)) continue;
    if (!found || norm(el.innerText).length <= norm(found.innerText).length) found = el;
  }
  if (!found) return { error: `no element reads "${text}"` };
  const top = (root && found.closest(root)) || found;
  for (let el = top; el && el !== document.documentElement; el = el.parentElement) {
    for (const sib of el.parentElement ? el.parentElement.children : []) {
      if (sib !== el && !['SCRIPT', 'STYLE', 'LINK'].includes(sib.tagName)) sib.style.setProperty('display', 'none', 'important');
    }
    if (el !== top) {
      el.style.setProperty('padding', '0', 'important');
      el.style.setProperty('margin', '0', 'important');
      el.style.setProperty('min-height', '0', 'important');
      el.style.setProperty('gap', '0', 'important');
    }
  }
  top.setAttribute('data-region-root', '');
  top.style.setProperty('margin', '0', 'important');
  if (width) {
    top.style.setProperty('width', `${width}px`, 'important');
    top.style.setProperty('max-width', `${width}px`, 'important');
    top.style.setProperty('flex', 'none', 'important');
  }
  window.scrollTo(0, 0);
  const r = top.getBoundingClientRect();
  return { width: Math.round(r.width), height: Math.round(r.height) };
}

const b64 = (buf) => 'data:image/png;base64,' + buf.toString('base64');
const browser = await chromium.launch();
const lines = [];
let failed = 0;
try {
  for (const region of regions) {
    if (only && !only.has(region.name)) continue;
    for (const width of widths) {
      const phone = width < 720;
      const side = phone ? (region.board.mobile ?? region.board) : region.board;
      const pageSide = phone ? (region.page.mobile ?? region.page) : region.page;
      const file = path.join(path.resolve(o.design), phone ? region.board.mobile_file : region.board.desktop_file);
      const dir = path.join(out, `${region.name}-${width}`);
      fs.mkdirSync(dir, { recursive: true });
      const notes = [];

      const src = fs.readFileSync(file, 'utf8');
      const board = renderBoard(src, { width, canvas: canvasSize(file), base: pathToFileURL(path.dirname(file) + '/').href });
      const rendered = path.join(dir, 'board.rendered.html');
      fs.writeFileSync(rendered, board.html);
      const bctx = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
      const bpage = await bctx.newPage();
      await bpage.goto(pathToFileURL(rendered).href, { waitUntil: 'load' }).catch((e) => notes.push(`board load: ${e.message.split('\n')[0]}`));
      await bpage.evaluate(() => Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 4000))]));
      const bbox = await bpage.evaluate(isolate, { text: side.text, root: side.root });
      if (bbox.error) {
        await bctx.close();
        failed += 1;
        lines.push(`FAIL  ${region.name.padEnd(22)} ${String(width).padStart(4)}  board region not found: ${bbox.error}`);
        console.log(lines.at(-1));
        continue;
      }
      const boardPng = await bpage.locator('[data-region-root]').screenshot();
      const boardData = await bpage.evaluate(extractInBrowser, { board: true });
      await bctx.close();

      // each page starts from the fixtures as committed (a press writes to the mock)
      if (o.mock) await fetch(new URL('/__mock/reset', o.mock), { method: 'POST' });
      const pctx = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1, timezoneId: 'Africa/Lagos' });
      await pctx.addCookies([{ name: 'psl_mock_persona', value: region.persona ?? 'pm', url: o.base }]);
      const ppage = await pctx.newPage();
      await ppage.goto(new URL(pageSide.path, o.base).href, { waitUntil: 'networkidle' });
      // the workspace renders after the item read; wait for the region's words before isolating them
      await ppage.locator('.ws').waitFor({ timeout: 20000 }).catch(() => notes.push('page: the workspace never appeared'));
      if (pageSide.press) {
        await ppage.getByRole('button', { name: pageSide.press, exact: true }).first().click();
        await ppage.waitForTimeout(400);
      }
      await ppage.evaluate(() => Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 4000))]));
      await ppage.waitForTimeout(300);
      const pbox = await ppage.evaluate(isolate, { text: pageSide.text, root: pageSide.root, width: bbox.width });
      if (pbox.error) {
        await pctx.close();
        failed += 1;
        lines.push(`FAIL  ${region.name.padEnd(22)} ${String(width).padStart(4)}  page region not found: ${pbox.error}`);
        console.log(lines.at(-1));
        continue;
      }
      const pagePng = await ppage.locator('[data-region-root]').screenshot();
      const pageData = await ppage.evaluate(extractInBrowser, { board: false });
      await pctx.close();

      const exceptions = allExceptions.filter((e) => !e.regions || e.regions.includes(region.name));
      const result = compare(boardData, pageData, { exceptions, threshold: 0.8 });
      const toolPage = await (await browser.newContext({ viewport: { width: 800, height: 600 } })).newPage();
      const visual = await toolPage.evaluate(visualInBrowser, {
        boardPng: b64(boardPng), pagePng: b64(pagePng), cell: 12, heightMode: 'board',
        labels: [`BOARD · ${path.basename(file)} · ${side.text}`, `FRAME · ${pageSide.path}`],
      });
      fs.writeFileSync(path.join(dir, 'side-by-side.png'), Buffer.from(visual.sideBySidePng.split(',')[1], 'base64'));
      delete visual.sideBySidePng;
      delete visual.diffPng;
      fs.rmSync(rendered);
      const open = result.missing.filter((m) => !m.exception);
      const coverage = result.total ? Math.round(((result.total - open.length) / result.total) * 1000) / 10 : 100;
      const pass = coverage >= MIN_COVERAGE && visual.score >= MIN_VISUAL;
      if (!pass) failed += 1;
      const report = {
        region: region.name, width, board: path.relative(path.resolve(o.design, '..'), file), page: pageSide.path,
        boardText: side.text, pageText: pageSide.text, boardRegion: bbox, pageRegion: pbox,
        pass, scores: { coverage: result.coverage, coverageWithExceptions: coverage, visual: visual.score },
        missing: result.missing.map((m) => ({ role: m.role, name: m.name ?? m.text, exception: m.exception ? m.exception.reason : undefined })),
        misplaced: result.misplaced.map((m) => ({ role: m.role, name: m.name ?? m.text })),
        extra: result.extra.map((m) => ({ role: m.role, name: m.name ?? m.text })),
        visual, notes,
      };
      fs.writeFileSync(path.join(dir, 'report.json'), JSON.stringify(report, null, 2));
      const line = `${pass ? 'PASS' : 'FAIL'}  ${region.name.padEnd(22)} ${String(width).padStart(4)}  coverage ${coverage}% (${result.total - open.length}/${result.total}, ${result.missing.length - open.length} by exception)  visual ${visual.score}`;
      lines.push(line);
      console.log(line);
      for (const m of open) console.log(`      missing: ${m.role} "${m.name ?? m.text}"`);
    }
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(out, 'region-scores.txt'), `${lines.join('\n')}\n`);
process.exit(failed ? 1 : 0);
