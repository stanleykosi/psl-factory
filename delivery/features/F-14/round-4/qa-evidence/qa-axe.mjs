import { chromium } from '/Users/Hunchoo/psl-factory-worktrees/f-14/frontend/node_modules/playwright/index.mjs';
import AxeMod from '/Users/Hunchoo/psl-factory-worktrees/f-14/frontend/node_modules/@axe-core/playwright/dist/index.mjs';
const AxeBuilder = AxeMod.default ?? AxeMod;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const PM = new Set(['W-1702','W-1703','W-1704','W-1708','W-1709']);
const paths = [...Array.from({ length: 11 }, (_, i) => `W-17${String(i + 1).padStart(2, '0')}`), 'W-1099', 'W-1705/history', 'W-1002'];
const b = await chromium.launch(); let bad = 0, n = 0;
for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) for (const p of paths) {
  const c = await b.newContext({ viewport: vp, timezoneId: 'Africa/Lagos' });
  await c.addCookies([{ name: 'psl_mock_persona', value: PM.has(p) ? 'pm' : 'finance_lead', url: 'http://localhost:4511' }]);
  const page = await c.newPage(); await page.goto('http://localhost:4511/work/' + p); await page.waitForTimeout(2000);
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze(); n++;
  const v = r.violations.map((x) => `${x.id}: ${x.nodes.map((nn) => nn.target.join(' ')).join(' | ')}`);
  if (v.length) { bad++; console.log('VIOLATION', vp.width, p, v); }
  await c.close();
}
console.log(`axe: ${n - bad}/${n} pages clean`); await b.close();
