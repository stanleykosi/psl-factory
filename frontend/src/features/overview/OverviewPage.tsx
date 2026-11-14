'use client';

import Link from 'next/link';
import { useRef, useState, type ComponentType, type KeyboardEvent } from 'react';

import { webglAvailable, type FloorProps } from '@/features/floor/support';
import { formatWat } from '@/features/work-item/labels';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';

import type { Overview as OverviewData, OverviewLine, OverviewStation } from './types';
import { useMedia } from './useMedia';
import { useOverview } from './useOverview';
import './overview.css';

const PHONE_QUERY = '(max-width: 719.98px)';
const REDUCED_QUERY = '(prefers-reduced-motion: reduce)';

type View = 'flat' | '3d';
const VIEWS: { key: View; label: string }[] = [
  { key: 'flat', label: 'Flat' },
  { key: '3d', label: '3D floor' },
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

function LineRows({ lines }: { lines: readonly OverviewLine[] }) {
  return (
    <ul className="overview__rows">
      {lines.map((l, i) => (
        <li key={`${i}-${l.line}`} className="overview__row">
          <span className="overview__name">{l.line}</span>
          <ol className="overview__track" aria-label={`${l.line} stations`}>
            {l.stations.map((s, j) => (
              <li key={`${j}-${s.name}`} className={`overview__station overview__station--${stationKind(s)}`}>
                <span className="overview__sq" aria-hidden="true">
                  {s.count > 0 ? s.count : null}
                </span>
                <span className="overview__sr">{stationText(s)}</span>
              </li>
            ))}
          </ol>
          <span className="overview__tag">
            <span className={`psl-tag ${l.stations.some((s) => s.needs_person) ? 'psl-tag--person' : 'psl-tag--neutral'}`}>{l.note}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** SCR-06: E-OVERVIEW's totals and lines exactly as returned, flat or as the 3D floor. */
function FactoryFloor() {
  const { state, retry } = useOverview();
  const phone = useMedia(PHONE_QUERY);
  const reduced = useMedia(REDUCED_QUERY);
  const [webgl] = useState(() => webglAvailable());
  const [failed, setFailed] = useState(false);
  const [view, setView] = useState<View>('flat');
  const [Floor, setFloor] = useState<ComponentType<FloorProps> | null>(null);
  const options = useRef<(HTMLButtonElement | null)[]>([]);

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
  const onViewKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = (index + step + VIEWS.length) % VIEWS.length;
    choose(VIEWS[next].key);
    options.current[next]?.focus();
  };

  const title = <h1 className="shell-title">Factory floor</h1>;

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
        <div className="psl-empty">
          <h3>The factory floor isn&rsquo;t open to your role.</h3>
          <p>{state.error.message}</p>
        </div>
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="overview">
        {title}
        <div className="shell-errorcard" role="alert">
          <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
          <span>We couldn&rsquo;t load the factory floor. Your work is safe; nothing was changed.</span>
          <span className="shell-reference">
            {state.lastAsOf && `Last loaded ${formatWat(state.lastAsOf)} WAT. `}Reference {state.error.code} for support.
          </span>
          <div className="shell-errorcard__action">
            <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={() => void retry()}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { data } = state;
  const hasLines = data.lines.length > 0;
  const show3d = hasLines && view === '3d' && can3d;
  const hint = phone ? null : reduced ? 'Motion is turned down on this device, so the floor is shown flat.' : !webgl ? 'This device can’t show the 3D floor, so it’s shown flat.' : null;

  const eyebrow = (
    <p className="overview__eyebrow">
      FACTORY FLOOR · UPDATED <time dateTime={data.as_of}>{formatWat(data.as_of)}</time> WAT
    </p>
  );
  const viewSwitch = hasLines && can3d && (
    <div className="psl-seg" role="radiogroup" aria-label="View">
      {VIEWS.map((v, i) => (
        <button
          key={v.key}
          ref={(el) => {
            options.current[i] = el;
          }}
          type="button"
          role="radio"
          aria-checked={v.key === view}
          tabIndex={v.key === view ? 0 : -1}
          className="psl-seg__opt"
          onClick={() => choose(v.key)}
          onKeyDown={(event) => onViewKey(event, i)}
        >
          {v.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="overview">
      {phone ? (
        <>
          {title}
          {eyebrow}
        </>
      ) : (
        <>
          {eyebrow}
          <div className="overview__head">
            {title}
            {viewSwitch}
          </div>
          {hint && <p className="psl-hint overview__hint">{hint}</p>}
        </>
      )}

      <dl className="overview__totals">
        {TOTALS.map((t) => (
          <div key={t.key} className="overview__total">
            <dt>{t.label}</dt>
            <dd>{data.totals[t.key]}</dd>
          </div>
        ))}
      </dl>

      {failed && (
        <div className="psl-callout psl-callout--warning">
          <WarningIcon />
          <span>We couldn&rsquo;t show the 3D floor, so it&rsquo;s shown flat.</span>
        </div>
      )}

      {hasLines ? (
        <>
          <section aria-label="Lines" className="overview__lines">
            {show3d ? (
              <>
                {Floor ? (
                  <Floor lines={data.lines} onFailure={fail} />
                ) : (
                  <span className="psl-loading overview__floorwait" role="status">
                    <span className="psl-busy" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                    Loading the 3D floor…
                  </span>
                )}
                <div className="overview__sr">
                  <LineRows lines={data.lines} />
                </div>
              </>
            ) : (
              <LineRows lines={data.lines} />
            )}
          </section>
          <p className="psl-hint">
            Each square is a station; dark squares hold work, orange ones need a person. The number in a square is how many items are there.
          </p>
        </>
      ) : (
        <div className="psl-empty">
          <h3>No lines to show yet.</h3>
          <p>Lines appear here when work you can see starts.</p>
        </div>
      )}

      <section className="overview-exceptions" aria-labelledby="overview-exceptions-title">
        <h2 id="overview-exceptions-title">All exceptions · everyone&rsquo;s</h2>
        <Link href="/exceptions" className="psl-link">
          See all exceptions
        </Link>
        <p>Your own exceptions also appear in My work · Needs me, marked Fix.</p>
      </section>
    </div>
  );
}
