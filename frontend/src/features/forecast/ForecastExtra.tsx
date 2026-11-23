'use client';

// F-103: the parts of the forecast page the section kinds cannot draw: the month control and its actuals, and the proof link.
// Read only. The month lives in the query (?month=YYYY-MM). The proof is a plain link to the private file; nothing reads it here.
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { Callout, Select } from '@/components';
import { SectionView } from '@/features/workspace/Sections';
import type { LineExtraProps } from '@/features/workspace/adapter';

import type { ForecastReadback } from './forecastAdapter';
import { CUT_LISTS, errorWords, isMonth, monthIsCut, monthKeys, monthSections, UNAVAILABLE } from './labels';
import { useForecastActuals } from './useForecastActuals';

function Proof({ workId, forecast }: { workId: number; forecast: NonNullable<ForecastReadback['forecast']> }) {
  const o = forecast.observation;
  if (!o) return null;
  return (
    <p className="ws-note">
      {o.has_proof ? (
        <a className="psl-link cmp-target" href={`/api/v1/work/${workId}/forecast/observations/${o.id}`}>
          Proof on file
        </a>
      ) : (
        'No proof on file'
      )}
    </p>
  );
}

function Actuals({ workId, forecast }: { workId: number; forecast: NonNullable<ForecastReadback['forecast']> }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const months = monthKeys(forecast);
  const asked = params.get('month');
  const month = isMonth(asked) && months.includes(asked) ? asked : null;
  const actuals = useForecastActuals(workId, month);
  if (forecast.audience === 'group' || months.length === 0) return null;
  const currency = forecast.result?.currency || null;
  const choose = (value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set('month', value);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };
  return (
    <>
      <section className="psl-panel ws-section" aria-label="Actuals for a month">
        <div className="psl-panel__body ws-section__body">
          <Select label="Show actuals for" options={months.map((m) => ({ value: m, label: m }))} value={month ?? undefined} onChange={choose} placeholder="Choose a month" />
        </div>
      </section>
      {actuals.status === 'loading' && <p className="ws-note">Loading actuals…</p>}
      {actuals.status === 'error' && <Callout kind="warning">{actuals.error.kind === 'not_found' ? UNAVAILABLE : (errorWords(actuals.error) ?? 'We couldn’t load the actuals for this month. Try again shortly.')}</Callout>}
      {actuals.status === 'ready' && (
        <>
          {monthSections(actuals.month, currency).map((section) => (
            <SectionView key={section.key} section={section} level={2} />
          ))}
          {monthIsCut(actuals.month) && <p className="ws-note">{CUT_LISTS}</p>}
        </>
      )}
    </>
  );
}

export function ForecastExtra({ readback, ctx }: LineExtraProps<ForecastReadback>) {
  const pathname = usePathname();
  if (readback.error) {
    return readback.error.signIn ? (
      <p>
        <Link className="psl-link cmp-target" href={`/sign-in?next=${encodeURIComponent(pathname)}`}>
          Sign in
        </Link>
      </p>
    ) : null;
  }
  return (
    <>
      <Proof workId={ctx.workId} forecast={readback.forecast} />
      <Actuals workId={ctx.workId} forecast={readback.forecast} />
    </>
  );
}
