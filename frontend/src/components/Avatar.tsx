// Avatar (design/system/project/components/Avatar, CMP-18): people get a round avatar with their initials (or
// photo) on neutral-tint; agents (Tola, Chidi, Zainab) get their mascot on their own tint, so agent work is never
// mistaken for a person. Sizes 20, 32 and 40px. A thin blue ring turns while an agent works (it stops when motion
// is reduced). Decorative beside the name it goes with; never beside an approval, amount or signature.
/* eslint-disable @next/next/no-img-element -- fixed small mascot assets from public/agents, as the features use */
import { cx } from './internal';

export type AgentKey = 'tola' | 'chidi' | 'zainab';

export const AGENTS: Record<AgentKey, { name: string; role: string; /** The team's own name ("PMO"), as the Talk to chips write it. */ team: string }> = {
  tola: { name: 'Tola', role: 'PMO agent', team: 'PMO' },
  chidi: { name: 'Chidi', role: 'Finance agent', team: 'Finance' },
  zainab: { name: 'Zainab', role: 'HR agent', team: 'HR' },
};

/** The agent for a name ("Chidi" → chidi); undefined for anything else. */
export function agentKey(name: string | undefined | null): AgentKey | undefined {
  const key = name?.trim().toLowerCase();
  return key && key in AGENTS ? (key as AgentKey) : undefined;
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return (words.length > 1 ? `${words[0][0]}${words[words.length - 1][0]}` : (words[0] ?? '').slice(0, 2)).toUpperCase();
}

type Size = 20 | 32 | 40;
const sizeClass = (size: Size) => (size === 32 ? undefined : `psl-avatar--${size}`);

export function AgentAvatar({ agent, size = 32, working = false, className }: { agent: AgentKey; size?: Size; working?: boolean; className?: string }) {
  const img = <img className={cx('psl-avatar', `psl-avatar--${agent}`, sizeClass(size), className)} src={`/agents/${agent}.png`} alt="" width={size} height={size} />;
  return working ? <span className="psl-avatar-wrap is-working">{img}</span> : img;
}

export function PersonAvatar({ name, photo, size = 32, onDark = false, className }: { name: string; photo?: string; size?: Size; onDark?: boolean; className?: string }) {
  if (photo) return <img className={cx('psl-avatar', sizeClass(size), className)} src={photo} alt="" width={size} height={size} />;
  return (
    <span className={cx('psl-avatar', sizeClass(size), onDark && 'psl-avatar--dark', className)} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

/** The avatar with the name and role, for inline mentions ("Tola · PMO agent"). */
export function AgentChip({ agent }: { agent: AgentKey }) {
  const { name, role } = AGENTS[agent];
  return (
    <span className="psl-agentchip">
      <AgentAvatar agent={agent} size={20} />
      {name} · {role}
    </span>
  );
}
