#!/usr/bin/env node
// Design-fidelity check: compares an approved Claude Design board with the built
// page and scores how closely the page follows it. See README.md.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderBoard, canvasSize, parseBoard } from '/Users/Hunchoo/software-factory/packages/design/fidelity/dc-template.mjs';
import { extractInBrowser } from '/Users/Hunchoo/software-factory/packages/design/fidelity/extract.mjs';
import { compare } from '/Users/Hunchoo/software-factory/packages/design/fidelity/compare.mjs';
import { visualInBrowser, annotateInBrowser } from '/Users/Hunchoo/software-factory/packages/design/fidelity/visual.mjs';
import { renderReport } from '/Users/Hunchoo/software-factory/packages/design/fidelity/report.mjs';

const USAGE = `usage: node fidelity.mjs --playwright <playwright/index.mjs> --board <board.dc.html> --page <url> --out <dir>
  [--width N] [--height N] [--cookies k=v,...] [--exceptions <file.json>]
  [--min-visual 90] [--min-coverage 100] [--visual-height board|overlap|union] [--cell 12]
  [--wait-for <css selector>] [--wait-ms 500] [--threshold 0.8] [--strict-position]
exit code: 0 pass, 1 fail, 2 could not run`;

function args(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) throw new Error(`unexpected argument ${a}`);
    const k = a.slice(2);
    if (k === 'strict-position' || k === 'help') { o[k] = true; continue; }
    if (i + 1 >= argv.length) throw new Error(`${a} needs a value`);
    o[k] = argv[++i];
  }
  return o;
}

async function loadPlaywright(p) {
  if (!p) throw new Error('--playwright is required (path to an installed playwright/index.mjs or its folder)');
  let f = path.resolve(p);
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = fs.existsSync(path.join(f, 'playwright', 'index.mjs')) ? path.join(f, 'playwright', 'index.mjs') : path.join(f, 'index.mjs');
  const m = await import(pathToFileURL(f).href);
  return m.chromium ? m : m.default;
}

const b64 = (buf) => 'data:image/png;base64,' + buf.toString('base64');
const writeDataUrl = (file, url) => fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64'));

async function main() {
  const o = args(process.argv.slice(2));
  if (o.help) { console.log(USAGE); return 0; }
  for (const k of ['board', 'page', 'out']) if (!o[k]) throw new Error(`--${k} is required\n${USAGE}`);
  const pw = await loadPlaywright(o.playwright || process.env.FIDELITY_PLAYWRIGHT);
  const boardPath = path.resolve(o.board);
  const out = path.resolve(o.out);
  fs.mkdirSync(out, { recursive: true });

  const rules = {
    minVisual: Number(o['min-visual'] ?? 90),
    minCoverage: Number(o['min-coverage'] ?? 100),
    threshold: Number(o.threshold ?? 0.8),
    strictPosition: !!o['strict-position'],
  };
  let exceptions = [];
  if (o.exceptions) {
    const ex = JSON.parse(fs.readFileSync(o.exceptions, 'utf8'));
    exceptions = Array.isArray(ex) ? ex : ex.exceptions || [];
  }

  const src = fs.readFileSync(boardPath, 'utf8');
  const canvas = canvasSize(boardPath);
  const width = o.width ? Number(o.width) : undefined;
  const board = renderBoard(src, { width, height: o.height ? Number(o.height) : undefined, canvas, base: pathToFileURL(path.dirname(boardPath) + '/').href });
  // When the width comes from the command line but the height does not, keep the
  // board's own height only if the board was drawn at that width.
  const preview = parseBoard(src).props.$preview || canvas || {};
  const vp = { width: board.width, height: o.height ? Number(o.height) : (preview.width === board.width && preview.height) || board.height };
  const renderedFile = path.join(out, 'board.rendered.html');
  fs.writeFileSync(renderedFile, board.html);
  const warnings = board.warnings.map((w) => `Board template: ${w}`);

  const browser = await pw.chromium.launch();
  try {
    // Board.
    const bctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1 });
    const bpage = await bctx.newPage();
    const failedFonts = new Set();
    bpage.on('requestfailed', (rq) => { if (/fonts\.(googleapis|gstatic)\.com/.test(rq.url())) failedFonts.add(new URL(rq.url()).host); });
    await bpage.goto(pathToFileURL(renderedFile).href, { waitUntil: 'load', timeout: 30000 }).catch((e) => warnings.push(`Board load: ${e.message.split('\n')[0]}`));
    await bpage.evaluate(() => Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 5000))]));
    const missingFonts = await bpage.evaluate(() => {
      const fams = new Set();
      for (const el of document.querySelectorAll('body *')) {
        if (!Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
        const f = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim();
        if (f && !/^(system-ui|sans-serif|serif|monospace)$/i.test(f)) fams.add(f);
      }
      return [...fams].filter((f) => ![...document.fonts].some((ff) => ff.family.replace(/["']/g, '') === f && ff.status === 'loaded'));
    });
    if (failedFonts.size) warnings.push(`Fonts: Google Fonts could not be reached (${[...failedFonts].join(', ')}); the board was drawn with fallback fonts, so text widths may differ slightly. The run continues.`);
    else if (missingFonts.length) warnings.push(`Fonts: these board fonts did not load and fell back to system fonts: ${missingFonts.join(', ')}.`);
    const boardShot = await bpage.screenshot({ fullPage: true });
    fs.writeFileSync(path.join(out, 'board.png'), boardShot);
    const boardData = await bpage.evaluate(extractInBrowser, { board: true });
    await bctx.close();

    // Built page.
    const pctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1 });
    if (o.cookies) {
      const cookies = o.cookies.split(',').filter(Boolean).map((kv) => { const i = kv.indexOf('='); return { name: kv.slice(0, i).trim(), value: kv.slice(i + 1).trim(), url: o.page }; });
      await pctx.addCookies(cookies);
    }
    const ppage = await pctx.newPage();
    const resp = await ppage.goto(o.page, { waitUntil: 'networkidle', timeout: 45000 }).catch(async (e) => {
      warnings.push(`Page did not settle (${e.message.split('\n')[0]}); compared what had loaded.`);
      return null;
    });
    if (resp && resp.status() >= 400) warnings.push(`Page answered HTTP ${resp.status()}.`);
    if (o['wait-for']) await ppage.waitForSelector(o['wait-for'], { timeout: 20000 }).catch(() => warnings.push(`Page: "${o['wait-for']}" never appeared.`));
    await ppage.evaluate(() => Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 5000))]));
    if (o.actions) { const act = (await import(pathToFileURL(path.resolve(o.actions)).href)).default; await act(ppage, o); }
    await ppage.waitForTimeout(Number(o['wait-ms'] ?? 500));
    const pageShot = await ppage.screenshot({ fullPage: true });
    fs.writeFileSync(path.join(out, 'page.png'), pageShot);
    const pageData = await ppage.evaluate(extractInBrowser, { board: false });
    await pctx.close();

    // Compare.
    const result = compare(boardData, pageData, { exceptions, threshold: rules.threshold });
    const tool = await (await browser.newContext({ viewport: { width: 800, height: 600 } })).newPage();
    const visual = await tool.evaluate(visualInBrowser, {
      boardPng: b64(boardShot), pagePng: b64(pageShot), cell: Number(o.cell ?? 12), heightMode: o['visual-height'] || 'board',
      labels: [`BOARD · ${path.basename(boardPath)}`, `BUILT PAGE · ${o.page}`],
    });
    writeDataUrl(path.join(out, 'side-by-side.png'), visual.sideBySidePng);
    writeDataUrl(path.join(out, 'diff.png'), visual.diffPng);
    delete visual.sideBySidePng; delete visual.diffPng;
    const boardMarks = result.missing.map((m, i) => ({ box: m.boardBox, color: '#C8201B', label: `M${i + 1}` }))
      .concat(result.misplaced.map((m, i) => ({ box: m.boardBox, color: '#B07800', label: `P${i + 1}`, dashed: true })));
    const pageMarks = result.misplaced.map((m, i) => ({ box: m.pageBox, color: '#B07800', label: `P${i + 1}` }))
      .concat(result.extra.map((m, i) => ({ box: m.pageBox, color: '#2459D6', label: `E${i + 1}` })));
    writeDataUrl(path.join(out, 'board-marked.png'), await tool.evaluate(annotateInBrowser, { png: b64(boardShot), marks: boardMarks }));
    writeDataUrl(path.join(out, 'page-marked.png'), await tool.evaluate(annotateInBrowser, { png: b64(pageShot), marks: pageMarks }));

    // Pass rule.
    const reasons = [];
    const missingOpen = result.missing.filter((m) => !m.exception);
    const effCoverage = result.total ? Math.round(((result.found + (result.missing.length - missingOpen.length)) / result.total) * 1000) / 10 : 100;
    let pass = true;
    if (effCoverage < rules.minCoverage) { pass = false; reasons.push(`${missingOpen.length} board item(s) are missing from the page and are not approved exceptions (coverage ${effCoverage}% with exceptions, needs ${rules.minCoverage}%).`); }
    else reasons.push(`Every board item is on the page${result.missing.length ? ' or approved as an exception' : ''} (${effCoverage}%).`);
    if (visual.score < rules.minVisual) { pass = false; reasons.push(`Visual match ${visual.score} is below ${rules.minVisual}.`); }
    else reasons.push(`Visual match ${visual.score} meets ${rules.minVisual}.`);
    if (rules.strictPosition && result.misplaced.length) { pass = false; reasons.push(`${result.misplaced.length} item(s) are in a different place (strict position check is on).`); }
    else if (result.misplaced.length) reasons.push(`${result.misplaced.length} item(s) are in a different place; review them (not part of the pass rule unless --strict-position).`);

    const report = {
      tool: 'design-fidelity-check', version: 1,
      generatedAt: new Date().toISOString(),
      boardPath, boardName: path.basename(boardPath), pageUrl: o.page,
      viewport: vp, rules, exceptionsPath: o.exceptions ? path.resolve(o.exceptions) : null,
      pass, passReasons: reasons,
      scores: { coverage: result.coverage, coverageWithExceptions: effCoverage, visual: visual.score },
      visual,
      coverage: result,
      warnings,
      images: { board: 'board.png', page: 'page.png', sideBySide: 'side-by-side.png', diff: 'diff.png', boardMarked: 'board-marked.png', pageMarked: 'page-marked.png' },
    };
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    fs.writeFileSync(path.join(out, 'report.html'), renderReport(report));
    console.log(`${pass ? 'PASS' : 'FAIL'}  coverage ${result.coverage}% (${result.found}/${result.total}; ${effCoverage}% with exceptions)  visual ${visual.score}  missing ${result.missing.length}  moved ${result.misplaced.length}  extra ${result.extra.length}`);
    for (const w of warnings) console.log(`note: ${w}`);
    console.log(`report: ${path.join(out, 'report.html')}`);
    return pass ? 0 : 1;
  } finally {
    await browser.close();
  }
}

main().then((code) => process.exit(code), (e) => { console.error(`fidelity: ${e.message}`); process.exit(2); });
