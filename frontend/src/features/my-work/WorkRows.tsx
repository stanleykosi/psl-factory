import Link from 'next/link';

import { SampleLabel } from '@/shell/SampleLabel';

import { formatAge, KINDS, miniSegments, stateTag, stationText, type WorkItem } from './model';

function KindTag({ kind }: { kind: WorkItem['kind'] }) {
  const tag = KINDS[kind];
  return <span className={`psl-tag psl-tag--${tag.family}`}>{tag.words}</span>;
}

function StateTag({ state }: { state: string }) {
  const tag = stateTag(state);
  return <span className={`psl-tag psl-tag--${tag.family}`}>{tag.words}</span>;
}

function MiniBar({ item, phone = false }: { item: WorkItem; phone?: boolean }) {
  return (
    <span className={phone ? 'psl-mini my-work__mini' : 'psl-mini'}>
      <span className={phone ? 'psl-mini__bar my-work__minibar' : 'psl-mini__bar'} aria-hidden="true">
        {miniSegments(item.station, item.state).map((cls, i) => (
          <i key={i} className={cls || undefined} />
        ))}
      </span>
      {!phone && <span className="psl-mini__text">{stationText(item.station, item.state)}</span>}
    </span>
  );
}

/** Desktop (SCR-01-desktop): Work, Where on its line, State, Age. */
export function WorkTable({ items }: { items: WorkItem[] }) {
  return (
    <div className="psl-tablewrap">
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
                <div className="my-work__work">
                  <KindTag kind={item.kind} />
                  <Link href={`/work/${item.id}`} className="my-work__title" data-work-link="">
                    {item.title}
                  </Link>
                </div>
                <div className="my-work__meta">
                  {item.line} · <span className="psl-mono">{item.reference}</span> <SampleLabel show={item.sample} />
                </div>
              </td>
              <td>
                <MiniBar item={item} />
              </td>
              <td>
                <StateTag state={item.state} />
                <div className="my-work__waiting">{item.waiting_on}</div>
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
    <ul className="psl-list my-work__cards">
      {items.map((item) => (
        <li key={item.id}>
          <Link href={`/work/${item.id}`} className="my-work__card" data-work-link="">
            <span className="my-work__cardtop">
              <span className="my-work__work">
                <KindTag kind={item.kind} />
                <span className="my-work__title">{item.title}</span>
              </span>
              <span className="my-work__age">{formatAge(item.age_seconds)}</span>
            </span>
            <MiniBar item={item} phone />
            <span className="my-work__cardstate">
              <StateTag state={item.state} />
              <span className="psl-mini__text">{stationText(item.station, item.state)}</span>
            </span>
            <span className="my-work__waiting">{item.waiting_on}</span>
            <SampleLabel show={item.sample} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
