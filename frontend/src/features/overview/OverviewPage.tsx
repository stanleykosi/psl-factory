'use client';

import { useState, type ComponentType, type KeyboardEvent } from 'react';

import { AgentAvatar, Button, Callout, EmptyState, ErrorState, formatDayTime, Link, Loading, PageTitle, Segmented, Tag, useIsPhone, VisuallyHidden, When } from '@/components';

import { StationStrip } from '@/features/floor/StationStrip';
import { useStationWork } from '@/features/floor/stationWork';
import { webglAvailable, type FloorProps } from '@/features/floor/support';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import { LINE_IDENTITY, tagTone } from './lines';
import type { Overview as OverviewData, OverviewLine, OverviewStation } from './types';
import { useMedia } from './useMedia';
import { useOverview } from './useOverview';
import './overview.css';

const REDUCED_QUERY = '(prefers-reduced-motion: reduce)';

type View = 'flat' | '3d';
const VIEWS: { value: View; label: string }[] = [
  { value: 'flat', label: 'Flat' },
  { value: '3d', label: '3D floor' },
];

const TOTALS: { key: keyof OverviewData['totals']; label: string }[] = [
  { key: 'in_progress', label: 'IN PROGRESS' },
  { key: 'need_a_person', label: 'NEED A PERSON' },
  { key: 'stopped', label: 'STOPPED' },
  { key: 'verified_this_month', label: 'VERIFIED THIS MONTH' },
];

/** /overview: the factory floor, for anyone whose /me lists Overview. */
export function OverviewPage() {
  const me = useMe();
  if (!me.destinations.includes('overview')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return <FactoryFloor />;
}

const stationKind = (s: OverviewStation) => (s.needs_person ? 'person' : s.count > 0 ? 'work' : 'empty');
const stationText = (s: OverviewStation) =>
  `${s.name}: ${s.count} ${s.count === 1 ? 'item' : 'items'}${s.needs_person ? ', needs a person' : ''}`;

function LineName({ line, phone }: { line: string; phone: boolean }) {
  const identity = LINE_IDENTITY[line];
  return (
    <span className="overview__who">
      {identity && <AgentAvatar agent={identity.agent} size={phone ? 20 : 32} />}
      <span className="overview__id">
        <span className="overview__name">{line}</span>
        {identity && <span className="overview__sub">{identity.subtitle}</span>}
      </span>
    </span>
  );
}

// Rows are ARIA list items rather than <li>, as on the board, so a row's name, subtitle and tag read as its own text.
// D-165: in the flat view a station's square is a button. Click, tap or Enter opens that station's work under its line
// (the 3D floor's strip, D-162), with each piece of work a link; the same press, the ×, or Esc closes it. Pointing only
// highlights, so the rows never jump while the pointer crosses the squares. The copy behind the 3D floor stays plain text.
function LineRows({ lines, phone, interactive = false }: { lines: readonly OverviewLine[]; phone: boolean; interactive?: boolean }) {
  const [open, setOpen] = useState<{ line: string; name: string } | null>(null);
  const openLine = open ? lines.find((l) => l.line === open.line) : undefined;
  const found = openLine?.stations.find((s) => s.name === open?.name);
  if (open && !found) setOpen(null);
  const { state, retry, showAll } = useStationWork(open && found ? { line: open.line, station: open.name, count: found.count, needsPerson: found.needs_person } : null);
  const stripId = (i: number) => `overview-station-${i}`;
  const close = (event: KeyboardEvent) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    setOpen(null);
  };
  return (
    <div role="list" className="overview__rows">
      {lines.map((l, i) => (
        <div role="listitem" key={`${i}-${l.line}`} className="overview__row">
          <LineName line={l.line} phone={phone} />
          <ol className="overview__track" aria-label={`${l.line} stations`}>
            {l.stations.map((s, j) => {
              const isOpen = open?.line === l.line && open.name === s.name;
              return (
                <li key={`${j}-${s.name}`} className={`overview__station overview__station--${stationKind(s)}`}>
                  {interactive ? (
                    <Button
                      kind="bare"
                      className={`overview__sq overview__sq--button${isOpen ? ' is-open' : ''}`}
                      aria-label={stationText(s)}
                      aria-expanded={isOpen}
                      aria-controls={isOpen ? stripId(i) : undefined}
                      onClick={() => setOpen(isOpen ? null : { line: l.line, name: s.name })}
                      onKeyDown={close}
                    >
                      {s.count > 0 ? s.count : null}
                    </Button>
                  ) : (
                    <>
                      <span className="overview__sq" aria-hidden="true">
                        {s.count > 0 ? s.count : null}
                      </span>
                      <VisuallyHidden>{stationText(s)}</VisuallyHidden>
                    </>
                  )}
                </li>
              );
            })}
          </ol>
          <span className="overview__tag">
            <Tag tone={tagTone(l)}>{l.note}</Tag>
          </span>
          {interactive && open?.line === l.line && found && state && (
            // Esc inside the list closes it; the list itself is not a control.
            // eslint-disable-next-line jsx-a11y/no-static-element-interactions
            <div id={stripId(i)} className="overview__open" onKeyDown={close}>
              <StationStrip
                line={l.line}
                station={found.name}
                count={found.count}
                state={state}
                pinned
                pinLabel="Open"
                closeLabel="Close station"
                onUnpin={() => setOpen(null)}
                onRetry={retry}
                onShowAll={() => void showAll()}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** SCR-06: E-OVERVIEW's totals and lines exactly as returned, flat or as the 3D floor. */
function FactoryFloor() {
  const { state, retry } = useOverview();
  const phone = useIsPhone();
  const reduced = useMedia(REDUCED_QUERY);
  const [webgl] = useState(() => webglAvailable());
  const [failed, setFailed] = useState(false);
  const [view, setView] = useState<View>('flat');
  const [Floor, setFloor] = useState<ComponentType<FloorProps> | null>(null);

  const can3d = webgl && !reduced && !phone && !failed;
  // Reduced motion, a narrow window or a failure while 3D is shown switches to Flat at once.
  if (view === '3d' && !can3d) setView('flat');

  const fail = () => setFailed(true);
  const choose = (next: View) => {
    setView(next);
    if (next === '3d' && !Floor) {
      import('@/features/floor/Floor3D').then((m) => setFloor(() => m.default), fail);
    }
  };
  const title = <PageTitle>Factory floor</PageTitle>;

  if (state.status === 'loading') {
    return (
      <div className="overview">
        {title}
        <LoadingState />
      </div>
    );
  }
  if (state.status === 'signed_out') {
    return (
      <div className="overview">
        {title}
        <SignedOutState pathname="/overview" />
      </div>
    );
  }
  if (state.status === 'not_open') {
    return (
      <div className="overview">
        {title}
        <EmptyState title="The factory floor isn’t open to your role.">{state.error.message}</EmptyState>
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="overview">
        {title}
        <ErrorState title="We couldn’t load the factory floor." retryLabel="Try again" onRetry={() => void retry()}>
          Your work is safe; nothing was changed. {state.lastAsOf && `Last loaded ${formatDayTime(state.lastAsOf)} WAT. `}Reference {state.error.code} for support.
        </ErrorState>
      </div>
    );
  }

  const { data } = state;
  const hasLines = data.lines.length > 0;
  const show3d = hasLines && view === '3d' && can3d;
  const hint = phone ? null : reduced ? 'Motion is turned down on this device, so the floor is shown flat.' : !webgl ? 'This device can’t show the 3D floor, so it’s shown flat.' : null;

  const eyebrow = (
    <p className="overview__eyebrow">
      FACTORY FLOOR · UPDATED <When value={data.as_of} show="daytime" /> WAT
    </p>
  );
  const viewSwitch = hasLines && can3d && <Segmented label="View" options={VIEWS} value={view} onChange={choose} />;

  return (
    <div className="overview">
      {phone ? (
        <>
          {title}
          <p className="overview__summary">
            <strong>{data.totals.in_progress}</strong> in progress · <strong className="overview__need">{data.totals.need_a_person}</strong> need a person
          </p>
        </>
      ) : (
        <>
          {eyebrow}
          <div className="overview__head">
            {title}
            {viewSwitch}
          </div>
          {hint && <p className="psl-hint overview__hint">{hint}</p>}
          <dl className="overview__totals">
            {TOTALS.map((t) => (
              <div key={t.key} className="overview__total">
                <dt>{t.label}</dt>
                <dd>{data.totals[t.key]}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      {failed && (
        <Callout kind="warning">We couldn&rsquo;t show the 3D floor, so it&rsquo;s shown flat.</Callout>
      )}

      {hasLines ? (
        <section aria-label="Lines" className="overview__lines">
          {show3d ? (
            <>
              {Floor ? (
                <Floor lines={data.lines} onFailure={fail} />
              ) : (
                <Loading className="overview__floorwait">Loading the 3D floor…</Loading>
              )}
              <div className="cmp-sr">
                <LineRows lines={data.lines} phone={phone} />
              </div>
            </>
          ) : (
            <LineRows lines={data.lines} phone={phone} interactive />
          )}
        </section>
      ) : (
        <EmptyState title="No lines to show yet.">Lines appear here when work you can see starts.</EmptyState>
      )}

      {/* The phone board has no coverage line; the time still shows, under the lines. */}
      {phone && eyebrow}

      <section className="overview-exceptions" aria-labelledby="overview-exceptions-title">
        <div className="overview-exceptions__head">
          <h2 id="overview-exceptions-title">All exceptions · everyone&rsquo;s</h2>
          <Link href="/exceptions" prefetch={false}>
            See all exceptions
          </Link>
        </div>
        <p>Your own exceptions also appear in My work · Needs me, marked Fix.</p>
      </section>

      {hasLines && !phone && (
        <p className="psl-hint overview__legend">
          Each square is a station; dark squares hold work, orange ones need a person. Press a square to see its work. The 3D floor shows the same lines with work moving
          between stations. With reduced motion, this flat view is shown instead. The number in a square is how many items are there.
        </p>
      )}
    </div>
  );
}
