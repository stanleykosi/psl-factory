// usage: node measure.mjs <board.rendered.html> <url> <width> <persona> : y/height of the main blocks on both
import { chromium } from '/Users/Hunchoo/psl-factory-worktrees/f-14/frontend/node_modules/playwright/index.mjs';
const [board, url, width, persona] = process.argv.slice(2);
const b = await chromium.launch();
const probe = () => {
  const out = [];
  const main = document.querySelector('main') || document.body;
  const walk = (el, depth) => {
    for (const c of el.children) {
      const r = c.getBoundingClientRect();
      if (r.height > 8 && r.width > 40) out.push(`${'  '.repeat(depth)}${c.tagName.toLowerCase()}${c.className && typeof c.className === 'string' ? '.' + c.className.split(' ')[0] : ''} y=${Math.round(r.y)} h=${Math.round(r.height)} x=${Math.round(r.x)} w=${Math.round(r.width)} ${(c.innerText || '').slice(0, 30).replace(/\n/g, ' ')}`);
      if (depth < 3) walk(c, depth + 1);
    }
  };
  walk(main, 0);
  return out.join('\n');
};
for (const [label, target, cookie] of [['BOARD', 'file://' + board, false], ['PAGE', url, true]]) {
  const ctx = await b.newContext({ viewport: { width: Number(width), height: 900 } });
  if (cookie) await ctx.addCookies([{ name: 'psl_mock_persona', value: persona, url }]);
  const p = await ctx.newPage();
  await p.goto(target, { waitUntil: 'networkidle' });
  await p.waitForTimeout(800);
  console.log('=====', label); console.log(await p.evaluate(probe));
  await ctx.close();
}
await b.close();
