'use client';

// SCR-43 Delivery tab: the project's six delivery lines from GET /projects/{case_id}/delivery-overview, read only. Each row shows
// what the API sends (title, reference, state, last update, link to the work item); nothing is counted or worked out here.
import Link from 'next/link';

import { formatDateTime, formatDayMonth, Panel, Skeleton, Tag } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { SignedOutState } from '@/shell/FrameStates';

import { deliveryRows, stateWords, type DeliveryOverview, type HoldReason } from './deliveryModel';
import { ProjectNoAccess } from './ProjectStates';
import { useDeliveryOverview } from './useDeliveryOverview';

import './delivery.css';

const SKELETON_ROWS = ['01', '02', '03', '04', '05', '06'];

export function DeliveryTab({ caseId }: { caseId: string }) {
  const { state, retry } = useDeliveryOverview(caseId);
  if (state.status === 'loading') {
    return (
      <Panel head="Delivery lines" headingLevel={2} aria-busy="true" bodyClassName="projects__journeybody">
        <ol className="delivery__list" aria-label="Loading the delivery lines">
          {SKELETON_ROWS.map((n) => (
            <li key={n} className="delivery__row">
              <Skeleton widths={[40]} />
            </li>
          ))}
        </ol>
      </Panel>
    );
  }
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={`/projects/${encodeURIComponent(caseId)}/delivery`} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <ProjectNoAccess />;
    return (
      <Panel head="Delivery can’t be shown right now" headingLevel={2}>
        <WorkErrorCard message="We couldn’t load the delivery lines. Nothing was changed." error={error} onRetry={() => void retry()} />
      </Panel>
    );
  }
  return <DeliveryRows overview={state.overview} reasons={state.reasons} />;
}

function DeliveryRows({ overview, reasons }: { overview: DeliveryOverview; reasons: HoldReason[] }) {
  return (
    <Panel head="Delivery lines" headingLevel={2} bodyClassName="projects__journeybody">
      <ol className="delivery__list">
        {deliveryRows(overview).map(({ number, line, reference, updatedAt, href }) => {
          const { text, tone } = stateWords(line);
          const closure = line.key === 'delivery-closure/v1';
          return (
            <li key={line.key} className="delivery__row">
              <span className="delivery__num psl-mono" aria-hidden="true">
                {number}
              </span>
              <span className="delivery__title">{line.title}</span>
              <span className="delivery__ref psl-mono">{reference}</span>
              <Tag tone={tone}>{text}</Tag>
              <span className="delivery__date">{updatedAt && `Updated ${formatDayMonth(updatedAt)}`}</span>
              <span className="delivery__open">
                {href && (
                  <Link href={href} aria-label={`Open ${line.title}`}>
                    Open
                  </Link>
                )}
              </span>
              {closure && reasons.length > 0 && (
                <div className="delivery__reasons">
                  <p className="projects__plain">Closure waits on:</p>
                  <ul>
                    {reasons.map((r) => (
                      <li key={r.title}>
                        {r.title}
                        {r.finding && <span className="delivery__finding"> {r.finding}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="delivery__rule">Hypercare, archive and handover run side by side after go-live. Closure needs all of them, a saved retrospective and Finance&#39;s confirmation.</p>
      <p className="projects__note delivery__asof">Checked {formatDateTime(overview.as_of)}</p>
    </Panel>
  );
}
