import axe from 'axe-core';

// The project's axe setup (as in start-work.test.tsx): WCAG 2.x A and AA rules; colour contrast is checked in the
// browser run, since jsdom does not compute colours.
const options: axe.RunOptions = {
  runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
  rules: { 'color-contrast': { enabled: false } },
};

export async function violations(root: Element = document.body): Promise<string[]> {
  return (await axe.run(root, options)).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`);
}
