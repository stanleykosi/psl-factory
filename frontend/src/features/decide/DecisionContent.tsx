// SCR-03 decision content: the header, the version rows, the approval chain, the phone station line and the
// agent note. Only values from tasks[].decision and E-WORK-ITEM are shown; absent fields are left out.
import Link from 'next/link';
import type { ReactNode } from 'react';

import type { TaskDecision, WorkItem } from '@/api/types';
import { avatarClass, formatWat } from '@/features/work-item/labels';
import { SampleLabel } from '@/shell/SampleLabel';

import { AGENT_NAMES, formatAmount, personStationIndex, STEP_STATUS, type Amount } from './format';

export function When({ at }: { at: string }) {
  return <time dateTime={at}>{formatWat(at)}</time>;
}

type HeaderProps = { item: WorkItem; eyebrow?: ReactNode; title: string; sub?: string; banner?: 'success' | 'neutral' };

/** The common header: crumb, station eyebrow, title and sub-line. The done view sets the eyebrow and title in a banner. */
export function DecideHeader({ item, eyebrow, title, sub, banner }: HeaderProps) {
  const heading = (
    <>
      {eyebrow && <p className="decide-eyebrow">{eyebrow}</p>}
      <h1 className="shell-title">{title}</h1>
    </>
  );
  return (
    <header className="decide-header">
      <nav aria-label="Breadcrumb">
        <p className="psl-crumb">
          <Link href="/my-work">My work</Link> / {item.line} / <span className="psl-mono">{item.reference}</span>
        </p>
      </nav>
      {banner ? <div className={`decide-banner decide-banner--${banner}`}>{heading}</div> : heading}
      {(sub || item.sample) && (
        <p className="decide-sub">
          {sub && <span>{sub}</span>}
          {/* The shared frame label only (design engineer, 14 Nov 2026: no screen-level sample tags). */}
          {item.sample && <SampleLabel />}
        </p>
      )}
    </header>
  );
}

/** "FINANCE REVIEW · INV-0412": the station waiting for a person, then the reference. */
export function stationEyebrow(item: WorkItem): string {
  const station = item.stations[personStationIndex(item.stations)];
  return station ? `${station.name.toUpperCase()} · ${item.reference}` : item.reference;
}

export function AmountValue({ amount }: { amount: Amount }) {
  const text = formatAmount(amount);
  if (text === null) return <span className="psl-unknown">Unknown</span>;
  return <span className="psl-amount">{text}</span>;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="decide-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The decision rows; `only` limits them to amount and basis (the read-only view). */
export function DecisionRows({ decision, only }: { decision: TaskDecision; only?: 'amount-basis' }) {
  const { amount, basis, recipient, changes, version, prepared_by: by } = decision;
  const full = only === undefined;
  return (
    <dl className="decide-rows" aria-label="Decision">
      {amount && (
        <Row label="Amount">
          <AmountValue amount={amount} />
        </Row>
      )}
      {basis && <Row label="Basis">{basis}</Row>}
      {full && recipient && <Row label="To">{recipient}</Row>}
      {full && changes && (
        <Row label={`Changed since ${changes.previous_label}`}>
          <ul className="decide-list">
            {changes.items.map((change, i) => (
              <li key={i}>{change}</li>
            ))}
          </ul>
        </Row>
      )}
      {full && (
        <Row label="Version">
          {version.label}
          {version.drafted_at && (
            <>
              {' · drafted '}
              <When at={version.drafted_at} />
            </>
          )}
        </Row>
      )}
      {full && by && (
        <Row label="Prepared by">
          <span className="decide-by">
            {by.is_you ? 'You' : by.role ? `${by.name} (${by.role})` : by.name}
            {by.with_agent && (
              <>
                {' with '}
                <span className={`${avatarClass(by.with_agent)} psl-avatar--20`} aria-hidden="true">
                  {AGENT_NAMES[by.with_agent].charAt(0)}
                </span>
                {AGENT_NAMES[by.with_agent]}
              </>
            )}
          </span>
        </Row>
      )}
    </dl>
  );
}

export function ApprovalChain({ chain }: { chain: TaskDecision['chain'] }) {
  return (
    <section className="decide-chain" aria-labelledby="decide-chain-title">
      <h2 id="decide-chain-title" className="decide-h2">
        Approval chain
      </h2>
      <p className="decide-plain">
        {chain.your_step ? `Step ${chain.your_step} of ${chain.step_count}` : chain.step_count === 1 ? '1 step' : `${chain.step_count} steps`}
      </p>
      <ol className="decide-steps">
        {chain.steps.map((step) => (
          <li key={step.position} className={`decide-step decide-step--${step.status}`}>
            <span className="decide-step__pos">{step.position}</span>
            <span className="decide-step__who">
              <strong>{step.role}</strong> · {step.person ?? 'Not assigned yet'}
              {step.is_you && ' (you)'}
            </span>
            <span className="decide-step__status">
              {STEP_STATUS[step.status]}
              {step.decided_at && (
                <>
                  {' '}
                  <When at={step.decided_at} />
                </>
              )}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

const MINI_CLASS: Partial<Record<WorkItem['stations'][number]['status'], string>> = {
  done: 'd',
  current_person: 'p',
  current_agent: 'a',
  waiting: 'w',
  stopped: 's',
  verified: 'v',
};

/** CMP-03 on the phone: "Station 4 of 7 · Finance review · only a Finance Lead can decide". */
export function MiniLine({ item, requiredRole }: { item: WorkItem; requiredRole: string }) {
  const index = personStationIndex(item.stations);
  if (index < 0) return null;
  return (
    <p className="psl-mini decide-mini">
      <span className="psl-mini__bar" aria-hidden="true">
        {item.stations.map((s, i) => (
          <i key={i} className={MINI_CLASS[s.status]} />
        ))}
      </span>
      <span className="psl-mini__text">
        Station {index + 1} of {item.stations.length} · {item.stations[index].name} · only a {requiredRole} can decide
      </span>
    </p>
  );
}

/** The agent that prepared the item: who it is, that it cannot decide, and where its steps are. */
export function AgentNote({ id, agent }: { id: string; agent: WorkItem['agent'] }) {
  if (agent.status === 'none' || !agent.name) return null;
  return (
    <section className="psl-agent decide-agent" aria-label="Agent">
      <div className="psl-agent__head">
        <span className={avatarClass(agent.name)} aria-hidden="true">
          {agent.name.charAt(0).toUpperCase()}
        </span>
        <span className="decide-agent__text">
          <strong>{agent.name}</strong>
          <small>Cannot approve, send or pay.</small>
          <Link href={`/work/${encodeURIComponent(id)}`}>See {agent.name}&rsquo;s steps</Link>
        </span>
      </div>
    </section>
  );
}
