import { readFileSync } from 'node:fs';
import { chromium } from '/Users/Hunchoo/psl-factory-worktrees/f-08/frontend/node_modules/playwright/index.mjs';
import { visualInBrowser } from '/Users/Hunchoo/software-factory/packages/design/fidelity/visual.mjs';
const dir = process.argv[2];
const url = (f) => 'data:image/png;base64,' + readFileSync(`${dir}/${f}`).toString('base64');
const b = await chromium.launch(); const p = await b.newPage();
const crop = async (src, y0, y1, mask) => p.evaluate(async ({ src, y0, y1, mask }) => {
  const i = new Image(); await new Promise((r) => { i.onload = r; i.src = src; });
  const c = document.createElement('canvas'); c.width = i.width; c.height = y1 - y0; const x = c.getContext('2d');
  x.drawImage(i, 0, -y0);
  if (mask) { x.fillStyle = '#FFFFFF'; for (const [mx, my, mw, mh] of mask) x.fillRect(mx, my - y0, mw, mh); }
  return c.toDataURL('image/png');
}, { src, y0, y1, mask });
const B = url('board.png'), P = url('page.png');
for (const [name, y0, y1] of [['frame header 0-56', 0, 56], ['F-08 content 56-696', 56, 696], ['bottom 696-844 (board: F-06 preview; page: lines 7-8)', 696, 844], ['whole 0-844', 0, 844]]) {
  const r = await p.evaluate(visualInBrowser, { boardPng: await crop(B, y0, y1), pagePng: await crop(P, y0, y1) });
  console.log(name, r.score, r.contentCells, r.mismatchedCells);
}
await b.close();
