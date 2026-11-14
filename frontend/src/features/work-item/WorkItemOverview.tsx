'use client';

// SCR-02 Overview: the six facts, the station track, the agent at work, the current human task and the
// next step. Read-only; the only link that leads to an action is "Open the decision" when you_can_act.
// With a PROPOSAL `presentation` block (board fixtures only) the page follows the state's board: its section
// order per viewport (LAYOUTS), the state card and the board's detail words. Without it, the F-03 layout.
import Link from 'next/link';
import { Fragment, useId, useState, type ReactNode } from 'react';

import { AmountValue, DecisionRows } from '@/features/decide/DecisionContent';
import { formatClock } from '@/features/decide/format';
import { WarningIcon } from '@/shell/icons';

import { InfoIcon } from './InfoIcon';

import {
  AGENT_TAGS,
  agentImage,
  avatarClass,
  currentStationIndex,
  FACTS,
  formatWat,
  nextStepKind,
  STATIONS,
  STEP_WORDS,
  stepKind,
  type Fact,
  type FactName,
  type WorkItem,
  type WorkState,
} from './labels';
import { isAppPath, presentationOf, type PanelLink, type PanelTone, type WorkItemPresentation } from './presentation';
import { useIsPhone } from './usePhone';

const FACT_WORDS: Record<Fact['status'], string> = { earned: 'Earned', current: 'In progress', not_yet: 'Not yet', unknown: 'Unknown' };

function FactValue({ fact, detail }: { fact: Fact | undefined; detail?: string }) {
  // INV-UNKNOWN: a fact the payload does not carry reads Unknown, never blank, zero or "No", whatever the detail says.
  const status = fact?.status ?? 'unknown';
  if (detail && status !== 'unknown') {
    // The board's detail is shown; the contract word stays in the accessible text, beside it.
    return (
      <>
        <span className="work-sr">{FACT_WORDS[status]}: </span>
        <strong>{detail}</strong>
      </>
    );
  }
  if (status === 'earned') {
    return (
      <>
        <strong>Earned</strong>
        {fact?.at && <time dateTime={fact.at}>{formatWat(fact.at)}</time>}
      </>
    );
  }
  if (status === 'current') return <strong>In progress</strong>;
  if (status === 'not_yet') {
    return (
      <>
        <strong>—</strong>
        <span className="work-sr">Not yet</span>
      </>
    );
  }
  return <strong>Unknown</strong>;
}

function factClass(fact: Fact | undefined): string {
  const status = fact?.status ?? 'unknown';
  if (status === 'earned') return fact?.name === 'verified' ? 'psl-fact psl-fact--verified' : 'psl-fact psl-fact--earned';
  if (status === 'current') return 'psl-fact psl-fact--current';
  if (status === 'unknown') return 'psl-fact psl-fact--unknown';
  return 'psl-fact';
}

type FactsProps = { facts: WorkItem['facts']; details?: Partial<Record<FactName, string>>; paidNote?: boolean };

export function FactsStrip({ facts, details, paidNote = true }: FactsProps) {
  return (
    <div className="work-facts">
      {/* div list: the boards draw the facts as boxes; the list roles keep them one list for screen readers */}
      <div className="psl-facts" role="list" aria-label="Facts">
        {FACTS.map(({ name, label, more }) => {
          const fact = facts.find((f) => f.name === name);
          return (
            <div key={name} role="listitem" className={factClass(fact)}>
              <b>{label}</b>
              {more && <span className="work-sr">{more}</span>}
              <FactValue fact={fact} detail={details?.[name]} />
            </div>
          );
        })}
      </div>
      {paidNote && <p className="work-note">Paid is a separate Finance fact and is not part of this line.</p>}
    </div>
  );
}

type TrackProps = { stations: WorkItem['stations']; state?: WorkState; details?: (string | null)[]; list?: boolean };

export function StationTrack({ stations, state, details, list }: TrackProps) {
  const current = currentStationIndex(stations);
  return (
    // A row of boxes from 1080px (bp-desktop), a vertical list below (and on the boards that draw a list);
    // the region stays focusable for keyboard scrolling.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <section className={list ? 'work-track work-track--list' : 'work-track'} aria-label="Stations" tabIndex={0}>
      <div className="psl-track" role="list">
        {stations.map((station, i) => {
          const { text, modifier } = STATIONS[station.status];
          const detail = details?.[i];
          // the station whose effect is uncertain is a solid amber block in the row (design owner, 14 Nov 2026)
          const uncertain = i === current && state === 'effect_uncertain' ? ' work-station--uncertain' : '';
          return (
            <div key={i} role="listitem" className={`psl-station psl-station--${modifier}${uncertain}`} aria-current={i === current ? 'step' : undefined}>
              <b>{String(i + 1).padStart(2, '0')}</b>
              <strong>{station.name}</strong>
              {detail ? (
                <>
                  <span className="work-sr">{text}: </span>
                  <span>{detail}</span>
                </>
              ) : (
                <span>{text}</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AgentSteps({ steps }: { steps: NonNullable<WorkItem['agent']['steps']> }) {
  return (
    <ol className="psl-steps">
      {steps.map((step, i) => {
        const kind = stepKind(step.status);
        return (
          <li key={i} className={`psl-step psl-step--${kind}`}>
            <span className={kind === 'now' ? 'psl-step__box psl-now' : 'psl-step__box'} aria-hidden="true">
              {kind === 'next' ? i + 1 : kind === 'done' ? '✓' : null}
            </span>
            <span className="psl-step__text">
              <span>
                <span className="work-sr">{STEP_WORDS[kind]}: </span>
                {step.text}
              </span>
              {step.source && <span className="psl-step__ref psl-mono">Read: {step.source}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function AgentCard({ agent }: { agent: WorkItem['agent'] }) {
  if (agent.status === 'none') {
    return (
      <section className="work-agent work-agent--none" aria-label="Agent at work">
        <p>No agent work on this item.</p>
      </section>
    );
  }
  const name = agent.name ?? 'Agent';
  const steps = agent.steps ?? [];
  const tag = AGENT_TAGS[agent.status];
  const now = steps.findIndex((s) => stepKind(s.status) !== 'done');
  return (
    <section className="psl-agent work-agent" aria-label="Agent at work">
      <div className="psl-agent__head">
        <span className={avatarClass(agent.name)} aria-hidden="true">
          {name.charAt(0).toUpperCase()}
        </span>
        <span>
          <strong>{name}</strong>
          <small>Cannot approve, send or pay.</small>
          {agent.status === 'working' && now >= 0 && (
            <small>
              step {now + 1} of {steps.length}
            </small>
          )}
        </span>
        <span className={`psl-tag psl-tag--${tag.tone}`}>{tag.text}</span>
      </div>
      {steps.length > 0 && <AgentSteps steps={steps} />}
    </section>
  );
}

function Mascot({ agent, role, className }: { agent: WorkItem['agent']; role?: string; className: string }) {
  const src = agentImage(agent.name);
  const name = agent.name ?? 'Agent';
  if (!src) {
    return (
      <span className={`${avatarClass(agent.name)} ${className}`} aria-hidden="true">
        {name.charAt(0).toUpperCase()}
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element -- a fixed 192px asset, as on My work
  return <img className={className} src={src} alt={role ? `${name}, ${role}` : name} />;
}

/** "Chidi · Finance agent": the name, then the role from the presentation block when it has one. */
function AgentName({ agent, role }: { agent: WorkItem['agent']; role?: string }) {
  return (
    <>
      <strong>{agent.name ?? 'Agent'}</strong>
      {role && <span className="work-agentrole"> · {role}</span>}
    </>
  );
}

const CANNOT = 'Cannot approve, send or pay.';

/** The agent section of the default, verified, owner-needed and effect-uncertain boards. */
function AgentSection({ agent, view }: { agent: WorkItem['agent']; view: WorkItemPresentation['agent'] }) {
  const steps = agent.steps ?? [];
  return (
    <section className="work-agentsec" aria-label="Agent at work">
      <div className="work-agentsec__head">
        <h2>
          <Mascot agent={agent} role={view?.role} className="work-mascot" />
          <span>
            <AgentName agent={agent} role={view?.role} />
          </span>
        </h2>
        <small>{CANNOT}</small>
      </div>
      {steps.length > 0 && (
        <ol className="work-agentsec__steps">
          {steps.map((step, i) => (
            <li key={i}>
              <span className="psl-mono">{String(i + 1).padStart(2, '0')}</span>
              <span>
                <span className="work-sr">{STEP_WORDS[stepKind(step.status)]}: </span>
                <span className="work-agentsec__text">{step.text}</span>
                {step.source && <span className="work-agentsec__src">Read: {step.source}</span>}
              </span>
              {step.at ? <time className="psl-mono" dateTime={step.at}>{formatClock(step.at)}</time> : <span />}
            </li>
          ))}
        </ol>
      )}
      {view?.message && (
        <div className="work-agentsec__msg">
          {view.message.map((text, i) => (
            <p key={i}>{text}</p>
          ))}
        </div>
      )}
    </section>
  );
}

/** The phone boards' agent note: mascot, name and role, one line; "See his steps" shows the steps in place. */
function AgentBox({ agent, view, text }: { agent: WorkItem['agent']; view: WorkItemPresentation['agent']; text?: string }) {
  const [open, setOpen] = useState(false);
  const stepsId = useId();
  const steps = agent.steps ?? [];
  return (
    <section className="work-agentbox" aria-label="Agent at work">
      <div className="work-agentbox__row">
        <Mascot agent={agent} role={view?.role} className="work-mascot" />
        <div className="work-agentbox__text">
          <AgentName agent={agent} role={view?.role} />
          <br />
          {text}
          {!text && <small>{CANNOT}</small>}
          {text && (
            <>
              {' '}
              <small>{CANNOT}</small>
            </>
          )}
          {steps.length > 0 && (
            <>
              {' '}
              <button type="button" className="work-disclosure" aria-expanded={open} aria-controls={stepsId} onClick={() => setOpen((v) => !v)}>
                {open ? 'Hide his steps' : 'See his steps'}
              </button>
            </>
          )}
        </div>
      </div>
      {steps.length > 0 && (
        <div id={stepsId} hidden={!open}>
          <AgentSteps steps={steps} />
        </div>
      )}
    </section>
  );
}

/** The waiting board's banner: the agent's large mascot beside what it is waiting for. */
function AgentBanner({ agent, view, phone }: { agent: WorkItem['agent']; view: WorkItemPresentation['agent']; phone: boolean }) {
  return (
    <section className="work-banner" aria-label="Agent at work">
      <Mascot agent={agent} role={view?.role} className="work-banner__img" />
      <div>
        {phone ? (
          <p>{view?.summary}</p>
        ) : (
          <>
            {view?.headline && <strong>{view.headline}</strong>}
            {view?.message?.map((text, i) => (
              <p key={i}>{text}</p>
            ))}
          </>
        )}
        <small>
          {agent.name ?? 'Agent'}
          {view?.role && ` · ${view.role}`} · {CANNOT}
        </small>
      </div>
    </section>
  );
}

/** The processing board's working agent: large mascot over the agent card titled with what it is doing. */
function AgentPanel({ agent, view, panel }: { agent: WorkItem['agent']; view: WorkItemPresentation['agent']; panel: WorkItemPresentation['panel'] }) {
  const steps = agent.steps ?? [];
  const tag = agent.status === 'none' ? null : AGENT_TAGS[agent.status];
  const now = steps.findIndex((s) => stepKind(s.status) !== 'done');
  const links = (panel?.links ?? []).filter((l) => isAppPath(l.href));
  return (
    <aside className="work-agentpanel" aria-label={panel?.title ?? 'Agent at work'}>
      <div className="work-agentpanel__art">
        <Mascot agent={agent} role={view?.role} className="work-agentpanel__img" />
      </div>
      <div className="work-agentpanel__card">
        <section className="psl-agent work-agent" aria-label="Agent at work">
          <div className="psl-agent__head">
            <Mascot agent={{ ...agent }} className="work-mascot work-mascot--32" />
            <span>
              {panel?.title && <strong>{panel.title}</strong>}
              <small>
                {agent.name ?? 'Agent'}
                {view?.role && ` · ${view.role}`}
                {agent.status === 'working' && now >= 0 && ` · step ${now + 1} of ${steps.length}`}
              </small>
              <small>{CANNOT}</small>
            </span>
            {tag && <span className={`psl-tag psl-tag--${tag.tone}`}>{tag.text}</span>}
          </div>
          {steps.length > 0 && <AgentSteps steps={steps} />}
          {(agent.started_at || panel?.note || links.length > 0) && (
            <div className="work-agentpanel__foot">
              <span>
                {agent.started_at && `Started ${formatClock(agent.started_at)}`}
                {agent.started_at && panel?.note && ' · '}
                {panel?.note}
              </span>
              {links.map((l) => (
                <Link key={l.href} href={l.href}>
                  {l.label}
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}

const TONE_BUTTON: Record<PanelTone, string> = {
  dark: 'psl-btn psl-btn--dark',
  signal: 'psl-btn psl-btn--start',
  waiting: 'psl-btn',
  verified: 'psl-btn psl-btn--confirm',
};

function PanelLinks({ links, tone }: { links: PanelLink[]; tone: PanelTone }) {
  return links
    .filter((l) => isAppPath(l.href))
    .map((l) => (
      <Link key={l.href + l.label} className={`${l.primary ? TONE_BUTTON[tone] : 'psl-btn psl-btn--secondary'} psl-btn--lg`} href={l.href}>
        {l.label}
      </Link>
    ));
}

/** The board's state card (right column): heading in the state's colour, the record's words, then navigation. */
function StatePanel({ panel, children }: { panel: NonNullable<WorkItemPresentation['panel']>; children?: ReactNode }) {
  const headId = useId();
  const tone = panel.tone ?? 'dark';
  return (
    <aside className={`work-statepanel work-statepanel--${tone}`} aria-labelledby={headId}>
      <h2 id={headId}>{panel.title}</h2>
      <div className="work-statepanel__body">
        {panel.lead && <p className="work-statepanel__lead">{panel.lead}</p>}
        {/* the recorded reason follows the first paragraph, as the cancelled board draws it */}
        {panel.body.map((text, i) => (
          <Fragment key={i}>
            <p>{text}</p>
            {i === 0 && panel.quote && (
              <p>
                <strong>Reason:</strong> &ldquo;{panel.quote}&rdquo;
              </p>
            )}
          </Fragment>
        ))}
        {panel.body.length === 0 && panel.quote && (
          <p>
            <strong>Reason:</strong> &ldquo;{panel.quote}&rdquo;
          </p>
        )}
        {panel.rows && (
          <dl>
            {panel.rows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {children}
        {panel.links && <PanelLinks links={panel.links} tone={tone} />}
        {panel.note && <p className="work-statepanel__note">{panel.note}</p>}
      </div>
    </aside>
  );
}

/** The phone boards' shorter state note: a callout, or a plain line. */
function PanelSummary({ summary }: { summary: NonNullable<NonNullable<WorkItemPresentation['panel']>['summary']> }) {
  if (!summary.kind) return <p className="work-summary">{summary.text}</p>;
  return (
    <div className={`psl-callout psl-callout--${summary.kind}`}>
      {summary.kind === 'info' ? <InfoIcon /> : <WarningIcon />}
      <span>{summary.text}</span>
    </div>
  );
}

/** The phone boards' bottom bar: the state card's way onward. */
function PhoneBar({ panel }: { panel: NonNullable<WorkItemPresentation['panel']> }) {
  const links = (panel.links ?? []).filter((l) => isAppPath(l.href));
  if (links.length === 0) return null;
  return (
    <div className="work-phonebar">
      <PanelLinks links={links} tone={panel.tone ?? 'dark'} />
    </div>
  );
}

function InvoicePreview({ preview }: { preview: NonNullable<WorkItemPresentation['preview']> }) {
  return (
    <article className="work-invoice" aria-label="Invoice preview">
      <div className="work-invoice__top">
        <span className="work-invoice__brand">{preview.brand}</span>
        <span className="work-invoice__test">{preview.template_label}</span>
      </div>
      <div className="work-invoice__parties">
        <div>
          <span>BILL TO</span>
          <br />
          <strong>{preview.bill_to.name}</strong>
          <br />
          {preview.bill_to.email}
        </div>
        <div>
          <span>INVOICE</span>
          <br />
          <strong className="psl-mono">{preview.number}</strong>
          <br />
          {preview.issue_note}
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th scope="col">DESCRIPTION</th>
            <th scope="col">AMOUNT</th>
          </tr>
        </thead>
        <tbody>
          {preview.lines.map((line, i) => (
            <tr key={i}>
              <td>
                {line.description}
                {line.detail && (
                  <>
                    <br />
                    <span className="work-invoice__detail">{line.detail}</span>
                  </>
                )}
              </td>
              <td className="psl-mono">{line.amount}</td>
            </tr>
          ))}
          <tr>
            <td>Tax</td>
            <td className="work-invoice__tax">{preview.tax}</td>
          </tr>
        </tbody>
      </table>
      <p className="work-invoice__foot">{preview.footer}</p>
    </article>
  );
}

/** The issue phone board: the invoice in brief; "Preview the invoice" shows the full preview in place. */
function PreviewSummary({ item, preview }: { item: WorkItem; preview: NonNullable<WorkItemPresentation['preview']> }) {
  const [open, setOpen] = useState(false);
  const previewId = useId();
  return (
    <>
      <section className="work-invoicecard" aria-label="Invoice">
        <span className="work-invoicecard__ref">
          {item.reference} · {preview.version} · <span className="work-invoicecard__test">TEST TEMPLATE</span>
        </span>
        {item.amount && (
          <span className="work-invoicecard__amount">
            <AmountValue amount={item.amount} />
          </span>
        )}
        <span>{preview.basis}</span>
        <button type="button" className="work-disclosure" aria-expanded={open} aria-controls={previewId} onClick={() => setOpen((v) => !v)}>
          {open ? 'Hide the invoice' : 'Preview the invoice'}
        </button>
      </section>
      <div id={previewId} hidden={!open}>
        <InvoicePreview preview={preview} />
      </div>
    </>
  );
}

export function TaskPanels({ id, tasks }: { id: string; tasks: WorkItem['tasks'] }) {
  return tasks.map((task) => (
    <section key={task.id} className={task.you_can_act ? 'psl-panel psl-panel--decide' : 'psl-panel'} aria-label="Current human task">
      <h2 className={task.you_can_act ? 'psl-panel__head psl-panel__head--decide' : 'psl-panel__head'}>{task.title}</h2>
      <div className="psl-panel__body">
        <p className="work-plain">Only a {task.required_role} can decide.</p>
        {task.you_can_act && <p className="work-plain">You are {task.required_role}.</p>}
        {task.decision && <DecisionRows decision={task.decision} />}
        {task.you_can_act && (
          <Link className="psl-btn" href={`/work/${encodeURIComponent(id)}/decide?task=${encodeURIComponent(task.id)}`}>
            Open the decision
          </Link>
        )}
      </div>
    </section>
  ));
}

export function NextStep({ item }: { item: WorkItem }) {
  return (
    <p className={`psl-callout psl-callout--${nextStepKind(item.state)} work-next`}>
      <span>
        <strong>Next step.</strong> {item.next_step}
      </span>
    </p>
  );
}

/** One board section. `track` is the station track; the agent appears as the board draws it. */
type Block = 'track' | 'agent-section' | 'agent-box' | 'agent-panel' | 'banner' | 'panel' | 'panel-agent' | 'summary' | 'preview' | 'bar';
type Order = { main: Block[]; aside: Block[] };
type Layout = {
  /** desktop station track: a row of boxes, or the list the state boards draw */
  track: 'row' | 'list';
  /** desktop: the state tag beside the title, or at the far end of the title line */
  tag: 'inline' | 'end';
  /** desktop sections between the facts and the two columns */
  top: Block[];
  desktop: Order;
  phone: Order;
};

/**
 * The section order of each SCR-02 state board, desktop and phone (phone boards order sections differently,
 * e.g. processing puts the agent before the stations). Keyed by contract state; the default board (a
 * decision for you, `task`) and the issue board (an approved invoice with its preview, `issue`) are keyed by
 * what the record carries. Tasks always close the right column, after F-09's slot.
 */
const LAYOUTS: Record<WorkState | 'task' | 'issue', Layout> = {
  task: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: [] }, phone: { main: ['track', 'agent-box'], aside: [] } },
  ready: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel-agent'] }, phone: { main: ['track', 'agent-box'], aside: ['bar'] } },
  processing: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['agent-panel'] }, phone: { main: ['agent-panel', 'track'], aside: ['bar'] } },
  waiting: { track: 'list', tag: 'end', top: ['banner'], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['banner', 'track'], aside: ['bar'] } },
  verified: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'summary'], aside: ['bar'] } },
  issue: { track: 'list', tag: 'end', top: [], desktop: { main: ['preview', 'track'], aside: ['panel'] }, phone: { main: ['preview', 'summary', 'track'], aside: ['bar'] } },
  cancelled: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['summary', 'track'], aside: ['bar'] } },
  owner_needed: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['agent-box', 'track'], aside: ['bar'] } },
  setup_needed: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['summary', 'track'], aside: ['bar'] } },
  effect_uncertain: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'agent-box'], aside: ['bar'] } },
  awaiting_reconciliation: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: [], aside: ['track', 'bar'] } },
  // no board yet: the default board's order
  action_needed: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'agent-box'], aside: ['bar'] } },
  followup_needed: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'agent-box'], aside: ['bar'] } },
};

const AGENT_BLOCKS = new Set<Block>(['agent-section', 'agent-box', 'agent-panel', 'banner', 'panel-agent']);

/** The board layout for an item with a presentation block; undefined keeps the F-03 layout. */
export function boardLayout(item: WorkItem): Layout | undefined {
  const view = presentationOf(item);
  if (!view) return undefined;
  if (view.preview) return LAYOUTS.issue;
  if (item.tasks.length > 0 && !view.panel) return LAYOUTS.task;
  return LAYOUTS[item.state];
}

export function WorkItemOverview({ id, item }: { id: string; item: WorkItem }) {
  const phone = useIsPhone();
  const view = presentationOf(item);
  const layout = boardLayout(item);
  const { agent } = item;
  const panel = view?.panel;

  // Without a presentation block: the F-03 layout.
  let before: ReactNode = (
    <>
      <FactsStrip facts={item.facts} />
      <StationTrack stations={item.stations} state={item.state} />
    </>
  );
  let main: ReactNode = (
    <>
      <AgentCard agent={item.agent} />
      <NextStep item={item} />
    </>
  );
  let aside: ReactNode = null;
  let after: ReactNode = null;

  if (view && layout) {
    const order = phone ? layout.phone : layout.desktop;
    const top = phone ? [] : layout.top;
    const mainBlocks = [...order.main];
    // Contract data is never dropped: an agent the board does not draw gets the default card.
    if (agent.status !== 'none' && ![...top, ...order.main, ...order.aside].some((b) => AGENT_BLOCKS.has(b))) {
      mainBlocks.push(phone ? 'agent-box' : 'agent-section');
    }
    const block = (b: Block): ReactNode => {
      switch (b) {
        case 'track':
          return <StationTrack key={b} stations={item.stations} state={item.state} details={view.stations} list={phone || layout.track === 'list'} />;
        case 'agent-section':
          return agent.status === 'none' ? null : <AgentSection key={b} agent={agent} view={view.agent} />;
        case 'agent-box':
          return agent.status === 'none' ? null : <AgentBox key={b} agent={agent} view={view.agent} text={view.agent?.summary} />;
        case 'agent-panel':
          return agent.status === 'none' ? null : <AgentPanel key={b} agent={agent} view={view.agent} panel={panel} />;
        case 'banner':
          return agent.status === 'none' ? null : <AgentBanner key={b} agent={agent} view={view.agent} phone={phone} />;
        case 'panel':
          return panel ? <StatePanel key={b} panel={panel} /> : null;
        case 'panel-agent':
          return panel ? (
            <StatePanel key={b} panel={panel}>
              {agent.status !== 'none' && <AgentBox agent={agent} view={view.agent} text={view.agent?.message?.[0]} />}
            </StatePanel>
          ) : null;
        case 'summary':
          return panel?.summary ? <PanelSummary key={b} summary={panel.summary} /> : null;
        case 'preview':
          if (!view.preview) return null;
          return phone ? <PreviewSummary key={b} item={item} preview={view.preview} /> : <InvoicePreview key={b} preview={view.preview} />;
        case 'bar':
          return panel ? <PhoneBar key={b} panel={panel} /> : null;
      }
    };
    before = (
      <>
        {/* the default board carries the Paid note; the state boards say it in their own card where it matters */}
        <FactsStrip facts={item.facts} details={view.facts} paidNote={layout === LAYOUTS.task && !phone} />
        {top.map(block)}
      </>
    );
    main = mainBlocks.map(block);
    aside = order.aside.map(block);
    after = <NextStep item={item} />;
  }

  return (
    <div className={layout ? `work-overview work-board work-board--${phone ? 'phone' : `desktop work-board--${layout.track}`}` : 'work-overview'}>
      {before}
      <div className="work-columns">
        <div className="work-column">{main}</div>
        <div className="work-column work-aside">
          {/* F-09: ReconcilePanel mounts here */}
          {aside}
          {item.tasks.length > 0 && <TaskPanels id={id} tasks={item.tasks} />}
          {view?.task_note && item.tasks.length > 0 && <p className="work-note">{view.task_note}</p>}
        </div>
      </div>
      {after}
    </div>
  );
}
