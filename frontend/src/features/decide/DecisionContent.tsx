// SCR-03 decision content: the header, the version rows, the approval chain, the phone station line and the
// agent note. Only values from tasks[].decision and E-WORK-ITEM are shown; absent fields are left out.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useRef, type ReactNode } from 'react';

import type { TaskDecision, WorkItem } from '@/api/types';
import { agentImage, avatarClass, formatWat } from '@/features/work-item/labels';
import { showSampleLabel } from '@/shell/sample';
import { SampleLabel } from '@/shell/SampleLabel';

import { AGENT_NAMES, formatAmount, personStationIndex, STEP_STATUS, type Amount } from './format';
import type { DecidePresentation } from './presentation';

export function When({ at }: { at: string }) {
  return <time dateTime={at}>{formatWat(at)}</time>;
}

type HeaderProps = {
  item: WorkItem;
  title: string;
  /** The board's visible trail ("DECISIONS / 1 OF 3 / FINANCE REVIEW · INV-0412"); the Breadcrumb nav stays for screen readers. */
  trail?: ReactNode;
  /** The phone boards' line above the title ("FINANCE REVIEW · INV-0412"); phones show it instead of the trail. */
  phoneEyebrow?: string;
  /** The done view's banner line ("YOU APPROVED · 10:47"). */
  eyebrow?: ReactNode;
  sub?: string;
  /** A state tag at the end of the title line (the own board). */
  tag?: ReactNode;
  banner?: 'success' | 'neutral';
  /** The stale phone board draws no title: the header stays for screen readers only below 720px. */
  quietOnPhone?: boolean;
  /** Move focus to the title on arrival (the done view, after a decision). */
  focusHeading?: boolean;
};

/** The common header: the trail, the title (in a banner on the done view), the state tag and the sub-line. */
export function DecideHeader({ item, title, trail, phoneEyebrow, eyebrow, sub, tag, banner, quietOnPhone, focusHeading }: HeaderProps) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focusHeading) ref.current?.focus();
  }, [focusHeading]);
  const heading = (
    <h1 ref={ref} tabIndex={focusHeading ? -1 : undefined} className="shell-title">
      {title}
    </h1>
  );
  const sample = item.sample && showSampleLabel();
  return (
    <header className={`decide-header${quietOnPhone ? ' decide-header--quiet' : ''}`}>
      <nav aria-label="Breadcrumb" className="decide-sr">
        <p className="psl-crumb">
          <Link href="/my-work">My work</Link> / {item.line} / <span className="psl-mono">{item.reference}</span>
        </p>
      </nav>
      {trail && <p className="decide-trail">{trail}</p>}
      {phoneEyebrow && <p className="decide-phone-eyebrow">{phoneEyebrow}</p>}
      {banner ? (
        <div className={`decide-banner decide-banner--${banner}`}>
          {eyebrow && <p className="decide-eyebrow">{eyebrow}</p>}
          {heading}
        </div>
      ) : (
        <div className="decide-titleline">
          {heading}
          {(sub || sample) && (
            <p className="decide-sub">
              {sub && <span>{sub}</span>}
              {/* The shared frame label only (design engineer, 14 Nov 2026: no screen-level sample tags). */}
              {item.sample && <SampleLabel />}
            </p>
          )}
          {tag}
        </div>
      )}
    </header>
  );
}

/** The actionable trail: "Decisions / 1 of 3 / FINANCE REVIEW · INV-0412" (phones show the station part above the title). */
export function DecisionTrail({ item, queue }: { item: WorkItem; queue?: string }) {
  return (
    <>
      <Link href="/my-work">Decisions</Link> / {queue && `${queue} / `}
      {stationEyebrow(item)}
    </>
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
export function MiniLine({ item, requiredRole, waiting }: { item: WorkItem; requiredRole: string; waiting?: string }) {
  const index = personStationIndex(item.stations);
  if (index < 0) return null;
  return (
    <div className="psl-mini decide-mini">
      <span className="psl-mini__bar" aria-hidden="true">
        {item.stations.map((s, i) => (
          <i key={i} className={MINI_CLASS[s.status]} />
        ))}
      </span>
      <span className="psl-mini__text">
        Station {index + 1} of {item.stations.length} · {item.stations[index].name} · {waiting && `${waiting} · `}only a {requiredRole} can decide
      </span>
    </div>
  );
}

type AgentProps = { id: string; agent: WorkItem['agent']; view?: DecidePresentation['agent']; mode?: 'steps' | 'note' };

/**
 * The agent that prepared the item: who it is, what it did, that it cannot decide, and where its steps are. The
 * stale board draws the redraft note instead of the summary and the link. Phones show the shorter wording when the
 * board block carries one.
 */
export function AgentNote({ id, agent, view, mode = 'steps' }: AgentProps) {
  if (agent.status === 'none' || !agent.name) return null;
  const image = agentImage(agent.name);
  const desktop = mode === 'note' ? view?.note : view?.summary;
  const phone = mode === 'note' ? view?.phone_note : view?.phone_summary;
  return (
    <section className={`decide-agent${phone ? ' decide-agent--phone' : ''}`} aria-label="Agent">
      {image ? (
        <Image className="decide-agent__img" src={image} alt="" width={36} height={36} unoptimized />
      ) : (
        <span className={avatarClass(agent.name)} aria-hidden="true">
          {agent.name.charAt(0).toUpperCase()}
        </span>
      )}
      <span className="decide-agent__text">
        <span className="decide-agent__head">
          <span className="decide-agent__who">
            <strong>{agent.name}</strong>
            {view?.role && ` · ${view.role}`}
            {mode === 'steps' && ' · '}
          </span>
          {phone && <span className="decide-agent__short">{phone} </span>}
          {mode === 'steps' && <small>Cannot approve, send or pay.</small>}
        </span>
        {desktop && <span className="decide-agent__summary">{desktop} </span>}
        {mode === 'steps' && <Link href={`/work/${encodeURIComponent(id)}`}>{view?.link_label ?? `See ${agent.name}’s steps`}</Link>}
      </span>
    </section>
  );
}
