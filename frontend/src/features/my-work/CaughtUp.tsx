'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { api, call } from '@/api/client';

import { AGENT_AVATAR, AGENTS, type Agent, type Counts, type WaitingOn, type WorkItem } from './model';
import { AgentAvatar } from './WorkRows';

const GROUPS: WaitingOn[] = ['agent', 'outside_party', 'someone_else'];
const SHOWN = 3;

type Group = { waiting: WaitingOn; items: WorkItem[]; more: boolean };

function groupTitle(group: Group): string {
  if (group.waiting === 'outside_party') return 'Waiting on the client';
  if (group.waiting === 'someone_else') return 'Other people are reviewing';
  const agents = new Set(group.items.map((i) => i.agent).filter(Boolean));
  return agents.size === 1 ? `${AGENTS[[...agents][0] as Agent]} is drafting` : 'Agents are drafting';
}

/**
 * SCR-01-*-empty: Needs me is empty. Says so, points to the work the person started and, on desktop,
 * shows where that work is, grouped by who it waits on (E-WORK-LIST waiting_on, D-WORKLIST-FILTERS).
 */
export function CaughtUp({ counts, phone, onSeeStarted }: { counts: Counts | null | undefined; phone: boolean; onSeeStarted: () => void }) {
  const started = counts?.waiting_on_others;
  const [groups, setGroups] = useState<Group[] | 'error'>();

  useEffect(() => {
    if (phone || !started) return;
    let live = true;
    Promise.all(
      GROUPS.map(async (waiting) => {
        const data = await call(api.GET('/api/v1/work', { params: { query: { queue: 'waiting_on_others', waiting_on: waiting, limit: 10 } } }));
        return { waiting, items: data.items, more: Boolean(data.next_cursor) };
      }),
    ).then(
      (loaded) => live && setGroups(loaded.filter((g) => g.items.length > 0)),
      () => live && setGroups('error'),
    );
    return () => {
      live = false;
    };
  }, [phone, started]);

  return (
    <div className="my-work__caughtup">
      <section aria-label="Nothing needs you" className="my-work__nothing">
        <Image src={AGENT_AVATAR.tola.src} alt="Tola, the PMO agent" width={96} height={96} className="my-work__mascot" />
        <div className="my-work__nothingtext">
          <h2>Nothing needs you right now</h2>
          <p>
            {started
              ? `${started} ${started === 1 ? 'thing' : 'things'} you started ${started === 1 ? 'is' : 'are'} moving. We’ll alert you on WhatsApp when one needs you.`
              : 'New work will appear here. We’ll alert you on WhatsApp when something needs you.'}
          </p>
          {Boolean(started) && (
            <div className="my-work__nothingactions">
              <button type="button" className="psl-btn psl-btn--secondary" onClick={onSeeStarted}>
                See what you started
              </button>
            </div>
          )}
        </div>
      </section>
      {!phone && Boolean(started) && groups && (
        <section aria-label="Where your work is" className="my-work__where">
          <div className="my-work__wherehead">
            <span>Where your work is</span>
            <Link href="/my-work?queue=waiting_on_others" className="psl-link">
              See all {started}
            </Link>
          </div>
          {groups === 'error' ? (
            <p className="my-work__wherefail">We couldn&rsquo;t load where your work is. Your work is safe; nothing was changed.</p>
          ) : (
            groups.map((group) => (
              <div key={group.waiting} className="my-work__group">
                <div className="my-work__grouphead">
                  {group.waiting === 'agent' && <AgentAvatar agent={group.items.find((i) => i.agent)?.agent} />}
                  <span>{groupTitle(group)}</span>
                  <span className="psl-badge">
                    {group.items.length}
                    {group.more ? '+' : ''}
                  </span>
                </div>
                {group.items.slice(0, SHOWN).map((item) => (
                  <Link key={item.id} href={`/work/${item.id}`} className="my-work__groupitem">
                    <strong>{item.title}</strong>
                    <span className="psl-mono">{item.reference}</span>
                    <span className="my-work__groupnote">{item.waiting_on}</span>
                  </Link>
                ))}
              </div>
            ))
          )}
        </section>
      )}
    </div>
  );
}
