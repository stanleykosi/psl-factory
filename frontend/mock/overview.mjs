// E-OVERVIEW in the contract mock: the SCR-06 sample floor, or a variant named by cookie
// psl_mock_overview (fixtures/overview/<variant>.json). Sample data only; no business rules.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', path), 'utf8'));

export const OVERVIEW_VARIANTS = ['empty', 'zero', 'changed'];
const fallback = read('E-OVERVIEW.json');
const variants = Object.fromEntries(OVERVIEW_VARIANTS.map((v) => [v, read(`overview/${v}.json`)]));

export function overview({ cookies }) {
  const variant = cookies.psl_mock_overview;
  return { status: 200, body: OVERVIEW_VARIANTS.includes(variant) ? variants[variant] : fallback };
}
