import Link from 'next/link';

import { formatDayTime, MiniStationBar, type ShowMoreProps, Table, Tag, type Column, type StationStatus } from '@/components';
import { lineTitle, ownerText, stateTag, workHref, type WorkLine, type WorkListRow } from '@/features/work-list';
import { SampleLabel } from '@/shell/SampleLabel';

import { KINDS, miniSegments, startAge, stationText, type Station } from './model';

/** What a row needs from its list: the titles for line keys and the list's own clock. */
export type RowContext = { lines: WorkLine[]; asOf: string };

/** `action_kind` null draws no tag. */
function KindTag({ kind }: { kind: WorkListRow['action_kind'] }) {
  if (!kind) return null;
  const tag = KINDS[kind];
  return (
    <Tag tone={tag.tone} className="my-work__kind">
      {tag.words}
    </Tag>
  );
}

function StateTag({ row }: { row: WorkListRow }) {
  const { text, tone } = stateTag(row.state);
  return <Tag tone={tone}>{text}</Tag>;
}

const STATUS: Record<string, StationStatus> = { d: 'done', p: 'person', a: 'agent', w: 'waiting', s: 'stopped', v: 'verified', '': 'todo' };

/** CMP-03: one segment per station, with the station's words beside it. A row without a station gets no bar. */
function Stations({ row, station, className }: { row: WorkListRow; station: Station; className: string }) {
  return <MiniStationBar className={className} stations={miniSegments(station, row.state).map((cls) => STATUS[cls])} text={stationText(station, row.state)} />;
}

/** The phone card draws the bar alone (the state tag beside it carries the words), so it is not the MiniStationBar, which always writes its words. */
function CardBar({ row, station }: { row: WorkListRow; station: Station }) {
  return (
    <span className="psl-mini__bar my-work__cardbar" aria-hidden="true">
      {miniSegments(station, row.state).map((cls, i) => (
        <i key={i} className={cls || undefined} />
      ))}
    </span>
  );
}

/** "Line title · REFERENCE"; the reference is left out when the row has none. */
function Meta({ row, lines }: { row: WorkListRow; lines: WorkLine[] }) {
  return (
    <span className="my-work__meta">
      {lineTitle(lines, row.line)}
      {row.reference && (
        <>
          {' · '}
          <span className="psl-mono">{row.reference}</span>
        </>
      )}{' '}
      <SampleLabel show={row.sample} />
    </span>
  );
}

/** The state's own words with the server's `status_label` beneath when it says more. */
const Status = ({ row }: { row: WorkListRow }) => (row.status_label && row.status_label !== stateTag(row.state).text ? <span className="my-work__status">{row.status_label}</span> : null);

const COLUMNS = ({ lines, asOf }: RowContext): Column<WorkListRow>[] => [
  {
    key: 'work',
    header: 'WORK',
    cell: (row) => (
      <>
        <KindTag kind={row.action_kind} />
        <Link href={workHref(row.id)} className="my-work__title" data-work-link="">
          {row.title}
        </Link>
        <Meta row={row} lines={lines} />
      </>
    ),
  },
  {
    key: 'where',
    header: 'WHERE ON ITS LINE',
    cell: (row) => (row.station ? <Stations row={row} station={row.station} className="my-work__station" /> : <span className="my-work__nostation">{row.status_label}</span>),
  },
  {
    key: 'state',
    header: 'STATE',
    cell: (row) => (
      <>
        <StateTag row={row} />
        <Status row={row} />
        <span className="my-work__waiting">{ownerText(row.owner)}</span>
      </>
    ),
  },
  {
    key: 'started',
    header: 'STARTED',
    cell: (row) => (
      <>
        <time dateTime={row.started_at} title={formatDayTime(row.started_at)}>
          {startAge(row, asOf)}
        </time>
        <span className="my-work__updatedat">
          Updated <time dateTime={row.updated_at}>{formatDayTime(row.updated_at)}</time>
        </span>
      </>
    ),
    mono: true,
  },
];

/** Desktop (SCR-01-desktop): Work, Where on its line, State, Started. */
export function WorkTable({ rows, context, paging }: { rows: WorkListRow[]; context: RowContext; paging: ShowMoreProps }) {
  return <Table caption="Your work" columns={COLUMNS(context)} rows={rows} rowKey={(row) => String(row.id)} empty="Nothing to show." className="my-work__tablewrap" paging={paging} />;
}

/** Phone (SCR-01-mobile): each card is one link to the work item. */
export function WorkCards({ rows, context }: { rows: WorkListRow[]; context: RowContext }) {
  return (
    <ul className="my-work__cards">
      {rows.map((row) => (
        <li key={row.id}>
          <Link href={workHref(row.id)} className="my-work__card" data-work-link="">
            <span className="my-work__cardtop">
              <span className="my-work__cardwork">
                <KindTag kind={row.action_kind} />
                <span className="my-work__cardtitle">{row.title}</span>
              </span>
              <span className="my-work__age">{startAge(row, context.asOf)}</span>
            </span>
            {row.station && <CardBar row={row} station={row.station} />}
            <span className="my-work__cardstate">
              <StateTag row={row} />
              <span className="my-work__cardnote">{ownerText(row.owner)}</span>
            </span>
            <SampleLabel show={row.sample} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Phone, Waiting on others (SCR-01-mobile-my-work): the title, the state and who has it. */
export function StartedCards({ rows }: { rows: WorkListRow[] }) {
  return (
    // A list built from divs, as on the board: the title links and the tag reads beside it.
    <div role="list" className="my-work__cards">
      {rows.map((row) => (
        <div role="listitem" key={row.id} className="my-work__started">
          <Link href={workHref(row.id)} className="my-work__cardtitle" data-work-link="">
            {row.title}
          </Link>
          <StateTag row={row} />
          <span className="my-work__cardnote">{ownerText(row.owner)}</span>
          <SampleLabel show={row.sample} />
        </div>
      ))}
    </div>
  );
}
