'use client';

import { useState, type ComponentType, type KeyboardEvent } from 'react';

import { AgentAvatar, Button, Callout, EmptyState, ErrorState, formatDayTime, Link, Loading, PageTitle, Segmented, Tag, useIsPhone, VisuallyHidden, When } from '@/components';

import { StationStrip } from '@/features/floor/StationStrip';
import { webglAvailable, type FloorProps, type SceneLine } from '@/features/floor/support';
import { useMe } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import { LINE_IDENTITY } from './lines';
import { coverageText, figure, floorsOf, monthLabel, totalsOf, workLink, type Floor, type Station } from './model';
import type { WorkCounts } from './types';
import { useMedia } from './useMedia';
import { useOverview } from './useOverview';
import './overview.css';

const REDUCED_QUERY = '(prefers-reduced-motion: reduce)';

type View = 'flat' | '3d';
const VIEWS: { value: View; label: string }[] = [
  { value: 'flat', label: 'Flat' },
  { value: '3d', label: '3D floor' },
];

const TOTALS = [
  { key: 'inProgress', label: 'IN PROGRESS' },
  { key: 'needPerson', label: 'NEED A PERSON' },
  { key: 'stopped', label: 'STOPPED' },
  { key: 'verifiedThisMonth', label: 'VERIFIED THIS MONTH' },
] as const;

// No read supplies a line's status, so the tag stays neutral rather than guessing one (D-182 Q3, D-187 Q8).
const NO_TAG = 'Not available yet';
const UNAVAILABLE = 'Totals are not available yet.';

/** /overview: the factory floor, for anyone whose /me lists Overview. */
export function OverviewPage() {
  const me = useMe();
  if (!hasDestination(me, 'overview')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return <FactoryFloor />;
}

const stationKind = (s: Station) => (s.needs_person > 0 ? 'person' : s.count > 0 ? 'work' : 'empty');
const stationText = (s: Station) => `${s.name}: ${s.count} ${s.count === 1 ? 'item' : 'items'}${s.needs_person > 0 ? ', needs a person' : ''}`;

function FloorName({ name, phone }: { name: string; phone: boolean }) {
  const identity = LINE_IDENTITY[name];
  return (
    <span className="overview__who">
      {identity && <AgentAvatar agent={identity.agent} size={phone ? 20 : 32} />}
      <span className="overview__id">
        <span className="overview__name">{name}</span>
        <span className="overview__sub">{identity ? identity.subtitle : 'Not on a floor yet'}</span>
      </span>
    </span>
  );
}

// Rows are ARIA list items rather than <li>, as on the board, so a row's name, subtitle and tag read as its own text.
// D-165: in the flat view a station's square is a button. Click, tap or Enter opens that station under its line (the 3D floor's
// strip, D-162) with its count and a link into the line's queue; the same press, the ×, or Esc closes it. Pointing only
// highlights, so the rows never jump while the pointer crosses the squares. The copy behind the 3D floor stays plain text.
function FloorRows({ floors, phone, interactive = false }: { floors: readonly Floor[]; phone: boolean; interactive?: boolean }) {
  const [open, setOpen] = useState<{ line: string; station: string } | null>(null);
  const openLine = open ? floors.flatMap((f) => f.lines).find((l) => l.key === open.line) : undefined;
  const found = openLine?.stations?.find((s) => s.key === open?.station);
  if (open && !found) setOpen(null);
  const close = (event: KeyboardEvent) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    setOpen(null);
  };
  return (
    <div role="list" className="overview__rows">
      {floors.map((f) => (
        <div role="listitem" key={f.name} className="overview__floor-block">
          <div className="overview__row overview__row--floor">
            <FloorName name={f.name} phone={phone} />
            <span className="overview__open-total">
              <strong>{f.total}</strong> open work
            </span>
          </div>
          <div role="list" className="overview__lines-of">
            {f.lines.map((l) => (
              <div role="listitem" key={l.key} className="overview__row">
                <span className="overview__id">
                  <span className="overview__name">{l.title}</span>
                  <span className="overview__count">{l.total} open work</span>
                </span>
                {l.stations ? (
                  <ol className="overview__track" aria-label={`${l.title} stations`}>
                    {l.stations.map((s) => {
                      const isOpen = open?.line === l.key && open.station === s.key;
                      return (
                        <li key={s.key} className={`overview__station overview__station--${stationKind(s)}`}>
                          {interactive ? (
                            <Button
                              kind="bare"
                              className={`overview__sq overview__sq--button${isOpen ? ' is-open' : ''}`}
                              aria-label={stationText(s)}
                              aria-expanded={isOpen}
                              aria-controls={isOpen ? `overview-station-${l.key}` : undefined}
                              onClick={() => setOpen(isOpen ? null : { line: l.key, station: s.key })}
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
                ) : (
                  <span className="overview__unknown">Not available yet</span>
                )}
                <span className="overview__tag">
                  <Tag tone="neutral">{NO_TAG}</Tag>
                  <Link href={workLink(l.key)} prefetch={false}>
                    Open work
                    <VisuallyHidden> · {l.title}</VisuallyHidden>
                  </Link>
                </span>
                {interactive && open?.line === l.key && found && (
                  // Esc inside the list closes it; the list itself is not a control.
                  // eslint-disable-next-line jsx-a11y/no-static-element-interactions
                  <div id={`overview-station-${l.key}`} className="overview__open" onKeyDown={close}>
                    <StationStrip title={l.title} lineKey={l.key} station={found} pinned pinLabel="Open" closeLabel="Close station" onUnpin={() => setOpen(null)} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const sceneLines = (floors: readonly Floor[]): SceneLine[] => floors.flatMap((f) => f.lines.map((l) => ({ key: l.key, title: l.title, note: NO_TAG, stations: l.stations ?? [] })));

function Totals({ counts }: { counts: WorkCounts | null }) {
  if (!counts) return <p className="psl-hint overview__unavailable">{UNAVAILABLE}</p>;
  const totals = totalsOf(counts);
  return (
    <>
      <dl className="overview__totals">
        {TOTALS.map((t) => (
          <div key={t.key} className="overview__total">
            <dt>{t.label}</dt>
            <dd>{figure(totals[t.key], counts.limited)}</dd>
            {t.key === 'verifiedThisMonth' && <small>{monthLabel(counts.verified_month)}</small>}
          </div>
        ))}
      </dl>
      <p className="psl-hint overview__coverage">{coverageText(counts)}</p>
    </>
  );
}

/** SCR-06: the lines GET /overview lists, with the figures GET /work/counts observed, flat or as the 3D floor. */
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
        <EmptyState title="The factory floor isn’t open to you.">{state.error.message}</EmptyState>
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

  const { data, counts } = state;
  const floors = floorsOf(data, counts);
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
          {eyebrow}
          {title}
          {hasLines &&
            (counts ? (
              <>
                <p className="overview__summary">
                  <strong>{figure(totalsOf(counts).inProgress, counts.limited)}</strong> in progress ·{' '}
                  <strong className="overview__need">{figure(totalsOf(counts).needPerson, counts.limited)}</strong> need a person
                </p>
                <p className="psl-hint overview__coverage">{coverageText(counts)}</p>
              </>
            ) : (
              <p className="psl-hint overview__unavailable">{UNAVAILABLE}</p>
            ))}
        </>
      ) : (
        <>
          {eyebrow}
          <div className="overview__head">
            {title}
            {viewSwitch}
          </div>
          {hint && <p className="psl-hint overview__hint">{hint}</p>}
          {hasLines && <Totals counts={counts} />}
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
                <Floor lines={sceneLines(floors)} onFailure={fail} />
              ) : (
                <Loading className="overview__floorwait">Loading the 3D floor…</Loading>
              )}
              <div className="cmp-sr">
                <FloorRows floors={floors} phone={phone} />
              </div>
            </>
          ) : (
            <FloorRows floors={floors} phone={phone} interactive />
          )}
        </section>
      ) : (
        <EmptyState title="No lines to show yet.">Lines appear here when work you can see starts.</EmptyState>
      )}

      <section className="overview-exceptions" aria-labelledby="overview-exceptions-title">
        <div className="overview-exceptions__head">
          <h2 id="overview-exceptions-title">All exceptions · everyone&rsquo;s</h2>
          <Link href="/exceptions" prefetch={false}>
            See all exceptions
          </Link>
        </div>
        <p>Your own exceptions also appear in My work · Needs me, marked Fix.</p>
      </section>

      {hasLines && (
        <p className="psl-hint overview__legend">
          Open work is work you can see that isn’t verified or cancelled. Station figures come from your most recent items and can be lower than the total.
          {!phone &&
            ' Each square is a station; dark squares hold work, orange ones need a person. Press a square to see it. The 3D floor shows the same lines with work moving between stations. With reduced motion, this flat view is shown instead. The number in a square is how many items are there.'}
        </p>
      )}
    </div>
  );
}
