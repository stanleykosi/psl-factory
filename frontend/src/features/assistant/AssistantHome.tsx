'use client';

// /assistant: the chosen agent's home. The agent comes from `?agent=` only if E-ME lists it, else the first listed.
// Typing and pressing Send makes the conversation (E-CONVERSATION-NEW), sends the message (E-MESSAGE) and opens the thread.
/* eslint-disable @next/next/no-img-element -- fixed mascot assets from public/agents */
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { AGENTS, EmptyState, useIsPhone } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';

import { useAssistant } from './AssistantContext';
import { TalkTo } from './Chrome';
import { ComposerBar } from './ComposerBar';
import { HOME_ABILITY, hello, NO_AGENTS } from './labels';
import { SidePanel } from './SidePanel';
import type { AgentName } from './types';
import { useSend } from './useSend';

function HomeComposer({ agent }: { agent: AgentName }) {
  const router = useRouter();
  const pathname = usePathname() ?? '/assistant';
  const { list } = useAssistant();
  const send = useSend({
    agent,
    listChanged: list.refresh,
    onSent: (id) => router.replace(`/assistant/${encodeURIComponent(id)}`),
  });
  return <ComposerBar agent={agent} send={send} pathname={pathname} />;
}

/** Phone bar: "← Home" and "N earlier", which opens the conversation list (the boards draw both in the bar). */
function PhoneHome({ home, count, more, onOpen }: { home: string; count: number; more: boolean; onOpen: () => void }) {
  usePhoneBack({ label: 'Home', href: home, note: count > 0 ? `${count}${more ? '+' : ''} earlier` : undefined, onNote: onOpen });
  return null;
}

function Home() {
  const { me, agents, list, showList } = useAssistant();
  const router = useRouter();
  const params = useSearchParams();
  const phone = useIsPhone();
  const requested = params?.get('agent') as AgentName | null;
  const agent = requested && agents.includes(requested) ? requested : agents[0];

  if (!agent) {
    return (
      <div className="as__center">
        <h1 className="cmp-sr">Assistant</h1>
        <EmptyState title={NO_AGENTS} level={2}>
          Ask a Lead or Admin to check your access.
        </EmptyState>
      </div>
    );
  }
  const who = AGENTS[agent];
  return (
    <>
      <div className="as__center">
        <PhoneHome
          home={visibleDestinations(me.destinations)[0]?.href ?? '/my-work'}
          count={list.state.status === 'ready' ? list.state.items.length : 0}
          more={list.state.status === 'ready' && Boolean(list.state.next)}
          onOpen={showList}
        />
        <TalkTo agents={agents} selected={agent} onPick={(next) => router.replace(`/assistant?agent=${next}`, { scroll: false })} />
        <section className="as__home" aria-label="Start a request">
          <img className="as__idle" src={`/agents/${agent}-idle.png`} alt={`${who.name}, the ${who.role}, standing and ready`} />
          <h1 className="as__hello">{hello(agent, me.name.split(' ')[0])}</h1>
          <p className="as__can">{HOME_ABILITY[agent]}</p>
          {phone && <p className="as__note">Agents use only records you can see. They draft, read and explain; they cannot approve, send, pay or change a record.</p>}
        </section>
        <HomeComposer key={agent} agent={agent} />
      </div>
      {!phone && <SidePanel agent={agent} pose="idle" status={`${who.name} is ready.`} project={undefined} access={undefined} />}
    </>
  );
}

export function AssistantHome() {
  return (
    <Suspense fallback={null}>
      <Home />
    </Suspense>
  );
}
