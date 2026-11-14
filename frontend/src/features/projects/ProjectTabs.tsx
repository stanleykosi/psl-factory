import Link from 'next/link';

export type ProjectTab = 'journey';

// The project's tabs as links. Only Journey exists today; later features add their entries here.
const TABS: readonly { key: ProjectTab; label: string; path: string }[] = [{ key: 'journey', label: 'Journey', path: '' }];

export function ProjectTabs({ base, current }: { base: string; current: ProjectTab }) {
  return (
    <nav aria-label="Project" className="psl-tabs projects__tabs">
      {TABS.map((t) => (
        <Link key={t.key} className="psl-tab" href={`${base}${t.path}`} aria-current={t.key === current ? 'page' : undefined}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
