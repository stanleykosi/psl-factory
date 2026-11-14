import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// A My work row and the work item page it opens must describe the same item.
const fixtures = join(__dirname, '..', 'mock', 'fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));

describe('mock rows match their work item fixtures', () => {
  const rows: { item: { id: string; title: string; reference?: string } }[] = read('E-WORK-LIST.rows.json').rows;
  const withItem = rows.filter((r) => existsSync(join(fixtures, 'work', `${r.item.id}.json`)));

  it('covers the shared ids', () => {
    expect(withItem.length).toBeGreaterThan(0);
  });

  it.each(withItem.map((r) => [r.item.id, r.item]))('%s has the same title and reference', (id, row) => {
    const body = read(join('work', `${id}.json`));
    const item = body.item ?? body;
    expect(row.title).toBe(item.title);
    if (row.reference && item.reference) expect(row.reference).toBe(item.reference);
  });
});
