import Link from 'next/link';

import { SampleLabel } from '@/shell/SampleLabel';

import { formatAge, KINDS, miniSegments, stateTag, stationText, type WorkItem } from './model';

function KindTag({ kind }: { kind: WorkItem['kind'] }) {
  const tag = KINDS[kind];
  return <span className={`psl-tag psl-tag--${tag.family} my-work__kind`}>{tag.words}</span>;
}

function StateTag({ state, words }: { state: string; words?: string }) {
  const tag = stateTag(state);
  return <span className={`psl-tag psl-tag--${tag.family}`}>{words ?? tag.words}</span>;
}

/** CMP-18: an agent's round avatar on its own tint, beside the work it drafted or is doing. */
export function AgentAvatar({ agent }: { agent?: WorkItem['agent'] }) {
  if (!agent) return null;
  return <span className={`psl-avatar psl-avatar--20 psl-avatar--${agent}`} aria-hidden="true" />;
}

function Segments({ item, className }: { item: WorkItem; className: string }) {
  return (
    <span className={`psl-mini__bar ${className}`} aria-hidden="true">
      {miniSegments(item.station, item.state).map((cls, i) => (
        <i key={i} className={cls || undefined} />
      ))}
    </span>
  );
}

/** Desktop (SCR-01-desktop): Work, Where on its line, State, Age. */
export function WorkTable({ items }: { items: WorkItem[] }) {
  return (
    <div className="psl-tablewrap my-work__tablewrap">
      <table className="psl-table my-work__table">
        <thead>
          <tr>
            <th scope="col">WORK</th>
            <th scope="col">WHERE ON ITS LINE</th>
            <th scope="col">STATE</th>
            <th scope="col">AGE</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <KindTag kind={item.kind} />
                <Link href={`/work/${item.id}`} className="my-work__title" data-work-link="">
                  {item.title}
                </Link>
                <span className="my-work__meta">
                  {item.line} · <span className="psl-mono">{item.reference}</span> <SampleLabel show={item.sample} />
                </span>
              </td>
              <td className="psl-mini__text my-work__station">
                <Segments item={item} className="my-work__bar" />
                {stationText(item.station, item.state)}
              </td>
              <td>
                <StateTag state={item.state} />
                <span className="my-work__waiting">
                  <AgentAvatar agent={item.agent} />
                  {item.waiting_on}
                </span>
              </td>
              <td className="my-work__age">{formatAge(item.age_seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Phone (SCR-01-mobile): each card is one link to the work item. */
export function WorkCards({ items }: { items: WorkItem[] }) {
  return (
    <ul className="my-work__cards">
      {items.map((item) => (
        <li key={item.id}>
          <Link href={`/work/${item.id}`} className="my-work__card" data-work-link="">
            <span className="my-work__cardtop">
              <span className="my-work__cardwork">
                <KindTag kind={item.kind} />
                <span className="my-work__cardtitle">{item.title}</span>
              </span>
              <span className="my-work__age">{formatAge(item.age_seconds)}</span>
            </span>
            <Segments item={item} className="my-work__cardbar" />
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
