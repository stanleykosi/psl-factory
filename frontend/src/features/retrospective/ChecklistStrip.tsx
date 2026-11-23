// The closure checklist strip: the six checks of the board in the order returned, and the exact version the checklist used.
import { Callout, formatDate, Panel, Tag, type TagTone } from '@/components';

import { STATUS_WORDS, stripChecks, type Check, type ClosureChecklist, type MeetingDetail } from './model';
import type { Load, Used } from './useRetrospective';

const TONE: Record<Check['status'], TagTone> = { current: 'person', recorded: 'done', closed: 'done', held: 'waiting', unknown: 'neutral', unavailable: 'neutral' };

function UsedVersion({ check, used }: { check: Check; used: Used }) {
  const id = check.references[0];
  if (id === undefined) return check.finding ? <p className="retro__used">{check.finding}</p> : null;
  if (used.status === 'failed') return <p className="retro__used">The checklist used version id {used.versionId}</p>;
  if (used.status !== 'ok') return <p className="retro__used">Reading the version the checklist used…</p>;
  const { detail } = used as { detail: MeetingDetail };
  return (
    <>
      <p className="retro__used">
        The checklist used version {detail.version} (saved {formatDate(detail.occurred_at)})
      </p>
      {!detail.current && <p className="retro__used">A newer version has been saved. The checklist has not picked it up yet.</p>}
    </>
  );
}

export function ChecklistStrip({ checklist, used }: { checklist: Load<ClosureChecklist> | { status: 'none' }; used: Used }) {
  if (checklist.status === 'none') return null;
  return (
    <Panel head="Closure checklist" headingLevel={2} bodyClassName="retro__stack">
      {checklist.status === 'loading' && <p className="retro__muted">Loading the checklist…</p>}
      {checklist.status === 'error' && <Callout kind="warning">The closure checklist is unavailable.</Callout>}
      {checklist.status === 'ready' && (
        <ul className="retro__strip">
          {stripChecks(checklist.data.checks).map((check) => (
            <li key={check.key}>
              <span className={check.key === 'retrospective' ? 'retro__check is-this' : 'retro__check'}>
                <span>
                  {check.title}
                  {check.key === 'retrospective' && ' · this screen'}
                </span>
                <Tag tone={TONE[check.status]}>{STATUS_WORDS[check.status]}</Tag>
              </span>
              {check.key === 'retrospective' && <UsedVersion check={check} used={used} />}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
