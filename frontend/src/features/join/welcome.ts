export type Workspace = { name: string; access: string };

const joined = (names: string[]) => (names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`);

/** One sentence per run of identical access words, in the order returned: "You've been given PMO for A and B." */
export function welcomeSentences(workspaces: Workspace[]): { lead: string; access: string; names: string }[] {
  const groups: { access: string; names: string[] }[] = [];
  for (const { name, access } of workspaces) {
    const group = groups.find((g) => g.access === access);
    if (group) group.names.push(name);
    else groups.push({ access, names: [name] });
  }
  return groups.map((g, i) => ({ lead: i === 0 ? 'You’ve been given' : 'You’ve also been given', access: g.access, names: joined(g.names) }));
}
