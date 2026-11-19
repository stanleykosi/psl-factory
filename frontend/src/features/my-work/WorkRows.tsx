import Link from 'next/link';

import { AgentAvatar as Avatar, MiniStationBar, Table, Tag, type Column, type StationStatus } from '@/components';
import { SampleLabel } from '@/shell/SampleLabel';

import { formatAge, KINDS, miniSegments, stateTag, stationText, type WorkItem } from './model';

function KindTag({ kind }: { kind: WorkItem['kind'] }) {
  const tag = KINDS[kind];
  return (
    <Tag tone={tag.family} className="my-work__kind">
      {tag.words}
    </Tag>
  );
}

function StateTag({ state, words }: { state: string; words?: string }) {
  const tag = stateTag(state);
  return <Tag tone={tag.family}>{words ?? tag.words}</Tag>;
}

/** CMP-18: the agent's mascot on its own tint, beside the work it drafted or is doing. The name is beside it in words. */
export function AgentAvatar({ agent }: { agent?: WorkItem['agent'] }) {
  return agent ? <Avatar agent={agent} size={20} /> : null;
}

const STATUS: Record<string, StationStatus> = { d: 'done', p: 'person', a: 'agent', w: 'waiting', s: 'stopped', v: 'verified', '': 'todo' };

/** CMP-03: one segment per station, with the station's words beside it. */
function Stations({ item, className }: { item: WorkItem; className: string }) {
  return <MiniStationBar className={className} stations={miniSegments(item.station, item.state).map((cls) => STATUS[cls])} text={stationText(item.station, item.state)} />;
}

/** The phone card draws the bar alone (the state tag beside it carries the words), so it is not the MiniStationBar, which always writes its words. */
function CardBar({ item }: { item: WorkItem }) {
  return (
    <span className="psl-mini__bar my-work__cardbar" aria-hidden="true">
      {miniSegments(item.station, item.state).map((cls, i) => (
        <i key={i} className={cls || undefined} />
      ))}
    </span>
  );
}

const COLUMNS = (hrefFor: HrefFor): Column<WorkItem>[] => [
  {
    key: 'work',
    header: 'WORK',
    cell: (item) => (
      <>
        <KindTag kind={item.kind} />
        <Link href={hrefFor(item)} className="my-work__title" data-work-link="">
          {item.title}
        </Link>
        <span className="my-work__meta">
          {item.line} · <span className="psl-mono">{item.reference}</span> <SampleLabel show={item.sample} />
        </span>
      </>
    ),
  },
  { key: 'where', header: 'WHERE ON ITS LINE', cell: (item) => <Stations item={item} className="my-work__station" /> },
  {
    key: 'state',
    header: 'STATE',
    cell: (item) => (
      <>
        <StateTag state={item.state} />
        <span className="my-work__waiting">
          <AgentAvatar agent={item.agent} />
          {item.waiting_on}
        </span>
      </>
    ),
  },
  { key: 'age', header: 'AGE', cell: (item) => formatAge(item.age_seconds), mono: true },
];

/** Where a row's link goes: the work item, or (F-36) on the Unassigned tab the panel over the list. */
export type HrefFor = (item: WorkItem) => string;
const toItem: HrefFor = (item) => `/work/${item.id}`;

/** Desktop (SCR-01-desktop): Work, Where on its line, State, Age. */
export function WorkTable({ items, hrefFor = toItem }: { items: WorkItem[]; hrefFor?: HrefFor }) {
  return <Table caption="Your work" columns={COLUMNS(hrefFor)} rows={items} rowKey={(item) => item.id} empty="Nothing to show." className="my-work__tablewrap" />;
}

/** Phone (SCR-01-mobile): each card is one link to the work item. */
export function WorkCards({ items, hrefFor = toItem }: { items: WorkItem[]; hrefFor?: HrefFor }) {
  return (
    <ul className="my-work__cards">
      {items.map((item) => (
        <li key={item.id}>
          <Link href={hrefFor(item)} className="my-work__card" data-work-link="">
            <span className="my-work__cardtop">
              <span className="my-work__cardwork">
                <KindTag kind={item.kind} />
                <span className="my-work__cardtitle">{item.title}</span>
              </span>
              <span className="my-work__age">{formatAge(item.age_seconds)}</span>
            </span>
            <CardBar item={item} />
            <span className="my-work__cardstate">
              <StateTag state={item.state} />
              <span className="my-work__cardnote">{item.waiting_on}</span>
            </span>
            <SampleLabel show={item.sample} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Words for a started item on a phone: who it waits on, else its state. */
const waitingWords = (item: WorkItem) => (item.state === 'waiting' ? `Waiting on ${item.waiting_on}` : undefined);

/** Phone, Waiting on others (SCR-01-mobile-my-work): the title and what it is waiting on. */
export function StartedCards({ items }: { items: WorkItem[] }) {
  return (
    // A list built from divs, as on the board: the title links and the tag reads beside it.
    <div role="list" className="my-work__cards">
      {items.map((item) => (
        <div role="listitem" key={item.id} className="my-work__started">
          <Link href={`/work/${item.id}`} className="my-work__cardtitle" data-work-link="">
            {item.title}
          </Link>
          <StateTag state={item.state} words={waitingWords(item)} />
          <SampleLabel show={item.sample} />
        </div>
      ))}
    </div>
  );
}
