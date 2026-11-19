'use client';

// SCR-02 Overview: the six facts, the station track, the agent at work, the current human task and the
// next step. Read-only except the links to an action: "Open the decision", or the response page through
// ResponseEntryLink; the only write here is ReconcilePanel's E-WORK-ACTION, shown with the reconcile grant.
// With a PROPOSAL `presentation` block (board fixtures only) the page follows the state's board: its section
// order per viewport (LAYOUTS), the state card and the board's detail words. Without it, the F-03 layout.
import Link from 'next/link';
import { Fragment, useId, useState, type ReactNode } from 'react';

import { AgentAvatar, agentKey, buttonClass, Callout, Disclosure, DisclosureLink, FactsStrip as SharedFactsStrip, formatClock, Panel, PersonAvatar, SampleLabel, Tag, useIsPhone, type FactValue } from '@/components';
import { AmountValue, DecisionRows } from '@/features/decide/DecisionContent';

import { asResponseItem, ReconcilePanel, ResponseEntryLink, responseOf, type ResponseWorkItem } from '@/features/response';
import { INTERNAL_RECONCILE_LINE } from '@/features/response/labels';
import { AGENT_BESIDE_LINES, forecastLine, STATION_LINES } from '@/features/workspace/labels';
import type { WorkspacePage } from '@/features/workspace/usePageReload';
import { drawsAgentCard, Workspace } from '@/features/workspace/Workspace';
import { RfpOutcomeLink } from '@/features/rfp';

import {
  AGENT_TAGS,
  agentPose,
  currentStationIndex,
  FACTS,
  nextStepKind,
  STATIONS,
  STEP_WORDS,
  stepKind,
  type FactName,
  type WorkItem,
  type WorkState,
} from './labels';
import { isAppPath, presentationOf, viewFor, type PanelLink, type PanelTone, type WorkItemPresentation } from './presentation';

type FactsProps = { facts: WorkItem['facts']; details?: Partial<Record<FactName, string>>; tones?: Partial<Record<FactName, 'waiting' | 'signal'>>; paidNote?: boolean };

/** The shared FactsStrip with the work item's facts, the board's detail words and tints. */
export function FactsStrip({ facts, details, tones, paidNote = true }: FactsProps) {
  const values: Partial<Record<FactName, FactValue>> = {};
  for (const { name } of FACTS) {
    const fact = facts.find((f) => f.name === name);
    // INV-UNKNOWN: a fact the payload does not carry reads Unknown, never blank, zero or "No", whatever the detail says.
    if (fact) values[name] = { status: fact.status, at: fact.at, text: details?.[name], tone: tones?.[name] };
  }
  return <SharedFactsStrip facts={values} label="Facts" className="work-facts" paidNote={paidNote ? 'Paid is a separate Finance fact and is not part of this line.' : null} paidNoteClassName="work-note" />;
}

type TrackProps = { stations: WorkItem['stations']; state?: WorkState; details?: (string | null)[]; list?: boolean; quiet?: boolean; shown?: number };

export function StationTrack({ stations, state, details, list, quiet, shown }: TrackProps) {
  const current = currentStationIndex(stations);
  return (
    // A row of boxes from 1080px (bp-desktop), a vertical list below (and on the boards that draw a list);
    // the region stays focusable for keyboard scrolling.
    <section
      className={`${list ? 'work-track work-track--list' : 'work-track'}${shown === 0 ? ' cmp-sr' : ''}`}
      aria-label="Stations"
      tabIndex={quiet || shown === 0 ? undefined : 0}
    >
      <div className="psl-track" role="list" aria-label="Stations in order">
        {stations.map((station, i) => {
          const { text, modifier } = STATIONS[station.status];
          const detail = details?.[i];
          // the station whose effect is uncertain is a solid amber block in the row (design owner, 14 Nov 2026)
          const uncertain = i === current && state === 'effect_uncertain' ? ' work-station--uncertain' : '';
          // the phone boards draw only the first stations; the rest stay in the list for screen readers
          const cut = shown !== undefined && i >= shown ? ' cmp-sr' : shown !== undefined && i === shown - 1 ? ' work-station--last' : '';
          return (
            <div key={i} role="listitem" className={`psl-station psl-station--${modifier}${uncertain}${cut}`} aria-current={i === current ? 'step' : undefined}>
              <b>{String(i + 1).padStart(2, '0')}</b>
              <strong>{station.name}</strong>
              {detail ? (
                <>
                  <span className="cmp-sr">{text}: </span>
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
                <span className="cmp-sr">{STEP_WORDS[kind]}: </span>
                {step.text}
              </span>
              {step.source && (
                <span className="psl-step__ref psl-mono">
                  <span className="cmp-sr">Read: </span>
                  {step.source}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** `foot`: CMP-09's footer row inside the card (the income schedule line puts the started time and Ask Chidi there, F-33). */
export function AgentCard({ agent, foot }: { agent: WorkItem['agent']; foot?: ReactNode }) {
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
        <Mascot agent={agent} className="work-mascot work-mascot--32" />
        <span>
          <strong>{name}</strong>
          <small>Cannot approve, send or pay.</small>
          {agent.status === 'working' && now >= 0 && (
            <small>
              step {now + 1} of {steps.length}
            </small>
          )}
        </span>
        <Tag tone={tag.tone} pulse={agent.status === 'working'}>
          {tag.text}
        </Tag>
      </div>
      {steps.length > 0 && <AgentSteps steps={steps} />}
      {foot && <div className="psl-agent__foot">{foot}</div>}
    </section>
  );
}

function Mascot({ agent, role, className, pose }: { agent: WorkItem['agent']; role?: string; className: string; pose?: 'waiting' | 'working' }) {
  const src = pose ? agentPose(agent.name, pose) : undefined;
  const name = agent.name ?? 'Agent';
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element -- a fixed small asset from public/agents, as on My work
    return <img className={className} src={src} alt={role ? `${name}, ${role}` : name} />;
  }
  const key = agentKey(agent.name);
  return key ? <AgentAvatar agent={key} size={className.includes('32') ? 32 : 40} className={className} /> : <PersonAvatar name={name} className={className} />;
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
        {/* only the default board draws the limits line; the others keep it for screen readers */}
        <small className={view?.limits ? undefined : 'cmp-sr'}>{view?.limits ?? CANNOT}</small>
      </div>
      {steps.length > 0 && (
        <ol className="work-agentsec__steps">
          {steps.map((step, i) => (
            <li key={i}>
              <span className="psl-mono">{String(i + 1).padStart(2, '0')}</span>
              <span>
                <span className="cmp-sr">{STEP_WORDS[stepKind(step.status)]}: </span>
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
  // `plain`: the board draws the note alone, so the name and role stay for screen readers only.
  const plain = view?.plain;
  return (
    <section className="work-agentbox" aria-label="Agent at work">
      <div className="work-agentbox__row">
        <Mascot agent={agent} role={view?.role} className="work-mascot" />
        <div className="work-agentbox__text">
          <span className={plain ? 'cmp-sr' : undefined}>
            <AgentName agent={agent} role={view?.role} />
            <br />
          </span>
          {text}
          {/* the phone boards draw no limits line; it stays for screen readers */}
          {text && ' '}
          <small className="cmp-sr">{CANNOT}</small>
          {steps.length > 0 && (
            <>
              {' '}
              <DisclosureLink open={open} onToggle={() => setOpen((v) => !v)} controls={stepsId} openLabel="Hide his steps">
                See his steps
              </DisclosureLink>
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
      <Mascot agent={agent} role={view?.role} className="work-banner__img" pose="waiting" />
      <div>
        {phone ? (
          <p>
            {/* the phone board sets the first sentence in bold */}
            <strong>{view?.summary?.split(/(?<=\.)\s/)[0]}</strong> {view?.summary?.split(/(?<=\.)\s/).slice(1).join(' ')}
          </p>
        ) : (
          <>
            {view?.headline && <strong>{view.headline}</strong>}
            {view?.message?.map((text, i) => (
              <p key={i}>{text}</p>
            ))}
          </>
        )}
        {/* the boards draw no limits line here; it stays for screen readers */}
        <small className="cmp-sr">
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
        <Mascot agent={agent} role={view?.role} className="work-agentpanel__img" pose="working" />
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
              <small className="cmp-sr">{CANNOT}</small>
            </span>
            {tag && (
              <Tag tone={tag.tone} pulse={agent.status === 'working'}>
                {tag.text}
              </Tag>
            )}
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
  dark: buttonClass('dark', 'lg'),
  signal: buttonClass('start', 'lg'),
  waiting: buttonClass('primary', 'lg'),
  verified: buttonClass('confirm', 'lg'),
};

function PanelLinks({ links, tone }: { links: PanelLink[]; tone: PanelTone }) {
  return links
    .filter((l) => isAppPath(l.href))
    .map((l) => (
      <Link key={l.href + l.label} className={l.primary ? TONE_BUTTON[tone] : buttonClass('secondary', 'lg')} href={l.href}>
        {l.label}
      </Link>
    ));
}

/** The board's state card (right column): heading in the state's colour, the record's words, then navigation. */
function StatePanel({ panel, children }: { panel: NonNullable<WorkItemPresentation['panel']>; children?: ReactNode }) {
  const headId = useId();
  const tone = panel.tone ?? 'dark';
  return (
    <aside className={`work-statepanel work-statepanel--${tone}${panel.large_title ? ' work-statepanel--large' : ''}`} aria-labelledby={headId}>
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
        {panel.note && panel.note_first && <p className="work-statepanel__note">{panel.note}</p>}
        {panel.links && <PanelLinks links={panel.links} tone={tone} />}
        {children}
        {panel.note && !panel.note_first && <p className="work-statepanel__note">{panel.note}</p>}
      </div>
    </aside>
  );
}

/** The phone boards' shorter state note: a callout, or a plain line. */
function PanelSummary({ summary }: { summary: NonNullable<NonNullable<WorkItemPresentation['panel']>['summary']> }) {
  if (!summary.kind) return <p className="work-summary">{summary.text}</p>;
  return (
    <Callout kind={summary.kind} announce={false}>
      {summary.text}
    </Callout>
  );
}

/** The phone boards' bottom bar: the state card's way onward. */
function PhoneBar({ panel }: { panel: NonNullable<WorkItemPresentation['panel']> }) {
  const links = (panel.links ?? []).filter((l) => isAppPath(l.href));
  if (links.length === 0 && !panel.bar_slot) return null;
  return (
    <div className={links.length === 0 ? 'work-phonebar work-phonebar--slot' : 'work-phonebar'}>
      <PanelLinks links={links} tone={panel.tone ?? 'dark'} />
      {panel.bar_note && <p className="work-phonebar__note">{panel.bar_note}</p>}
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
  return (
    <>
      <section className="work-invoicecard" aria-label="Invoice">
        <span className="work-invoicecard__ref">
          {item.reference} · {preview.version} · <SampleLabel kind="test" />
        </span>
        {item.amount && (
          <span className="work-invoicecard__amount">
            <AmountValue amount={item.amount} />
          </span>
        )}
        <span>{preview.basis}</span>
        <Disclosure look="link" summary="Preview the invoice" openSummary="Hide the invoice">
          <InvoicePreview preview={preview} />
        </Disclosure>
      </section>
    </>
  );
}

export function TaskPanels({ id, tasks }: { id: string; tasks: ResponseWorkItem['tasks'] }) {
  return tasks.map((task) => (
    <Panel key={task.id} kind={task.you_can_act ? 'decide' : 'default'} head={task.title}>
      <p className="work-plain">Only a {task.required_role} can decide.</p>
      {task.you_can_act && <p className="work-plain">You are {task.required_role}.</p>}
      {task.decision && <DecisionRows decision={task.decision} />}
      {task.you_can_act &&
        (responseOf(task) ? (
          <ResponseEntryLink id={id} task={task} />
        ) : (
          <Link className={buttonClass()} href={`/work/${encodeURIComponent(id)}/decide?task=${encodeURIComponent(task.id)}`}>
            Open the decision
          </Link>
        ))}
    </Panel>
  ));
}

const EXCEPTION_STATES = new Set<WorkItem['state']>([
  'effect_uncertain',
  'awaiting_reconciliation',
  'owner_needed',
  'setup_needed',
  'followup_needed',
]);

/** Where a person finds every uncertain or stuck item; offered on the exception states. */
export const hasExceptionsLink = (item: WorkItem) => EXCEPTION_STATES.has(item.state);

/** `quiet`: the text only; the board page draws the exceptions link itself, visibly, where its board does. */
export function NextStep({ item, quiet }: { item: WorkItem; quiet?: boolean }) {
  return (
    <Callout kind={nextStepKind(item.state)} announce={false} icon={false} className="work-next">
      <strong>Next step.</strong> {item.next_step}
      {!quiet && hasExceptionsLink(item) && (
        <>
          {' '}
          <Link href="/exceptions" className="cmp-target">
            See all exceptions
          </Link>
        </>
      )}
    </Callout>
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
  processing: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['agent-panel'] }, phone: { main: ['agent-panel', 'track'], aside: [] } },
  waiting: { track: 'list', tag: 'end', top: ['banner'], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['banner', 'track'], aside: ['bar'] } },
  verified: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'summary'], aside: ['bar'] } },
  issue: { track: 'list', tag: 'end', top: [], desktop: { main: ['preview'], aside: ['panel'] }, phone: { main: ['preview', 'summary'], aside: ['bar'] } },
  cancelled: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['summary', 'track'], aside: ['bar'] } },
  owner_needed: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['agent-box', 'track'], aside: ['bar'] } },
  setup_needed: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['summary', 'track'], aside: ['bar'] } },
  effect_uncertain: { track: 'row', tag: 'inline', top: ['track'], desktop: { main: ['agent-section'], aside: ['panel'] }, phone: { main: ['track', 'agent-box'], aside: ['bar'] } },
  awaiting_reconciliation: { track: 'list', tag: 'end', top: [], desktop: { main: ['track'], aside: ['panel'] }, phone: { main: ['summary'], aside: ['bar'] } },
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

export function WorkItemOverview({ id, item, workspace }: { id: string; item: WorkItem; workspace?: WorkspacePage }) {
  const phone = useIsPhone();
  const view = viewFor(presentationOf(item), phone);
  const layout = boardLayout(item);
  const { agent } = item;
  const panel = view?.panel;
  // the exception boards draw "See all exceptions" as a secondary button in the item's own panel on desktop (F-09's panel and the phone bar keep it below)
  const inPanel = !phone && hasExceptionsLink(item) && panel !== undefined && item.state !== 'awaiting_reconciliation';

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
    const drawn = [...top, ...order.main, ...order.aside];
    // Contract data is never dropped: what the board does not draw stays in the page for screen readers only.
    const quiet: Block[] = [];
    if (!drawn.includes('track')) quiet.push('track');
    if (agent.status !== 'none' && !drawn.some((b) => AGENT_BLOCKS.has(b))) quiet.push('agent-section');
    const block = (b: Block): ReactNode => {
      switch (b) {
        case 'track':
          return <StationTrack key={b} stations={item.stations} state={item.state} details={view.stations} list={phone || layout.track === 'list'} quiet={quiet.includes('track')} shown={view.stations_shown} />;
        case 'agent-section':
          return agent.status === 'none' ? null : <AgentSection key={b} agent={agent} view={view.agent} />;
        case 'agent-box':
          return agent.status === 'none' ? null : <AgentBox key={b} agent={agent} view={view.agent} text={view.agent?.summary} />;
        case 'agent-panel':
          return agent.status === 'none' ? null : <AgentPanel key={b} agent={agent} view={view.agent} panel={panel} />;
        case 'banner':
          return agent.status === 'none' ? null : <AgentBanner key={b} agent={agent} view={view.agent} phone={phone} />;
        case 'panel':
          // the effect-uncertain desktop board draws "See all exceptions" as a button between the facts and the small print
          return panel ? (
            <StatePanel key={b} panel={panel}>
              {inPanel && (
                <Link className={`${buttonClass("secondary", "lg")} work-exceptions`} href="/exceptions">
                  See all exceptions
                </Link>
              )}
            </StatePanel>
          ) : null;
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
        <FactsStrip facts={item.facts} details={view.facts} tones={view.fact_tones} paidNote={layout === LAYOUTS.task && !phone} />
        {top.map(block)}
      </>
    );
    main = (
      <>
        {order.main.map(block)}
        {quiet.length > 0 && <div className="cmp-sr">{quiet.map(block)}</div>}
      </>
    );
    aside = order.aside.map(block);
    // The boards draw no next-step block; the text stays for screen readers. The processing desktop board draws
    // its line as small print, and the exception states keep "See all exceptions" visible (never inside hidden text).
    const nextDrawn = !phone && item.state === 'processing';
        after = (
      <>
        {nextDrawn ? (
          <p className="work-note">
            <span className="cmp-sr">Next step. </span>
            {item.next_step}
          </p>
        ) : (
          <div className="cmp-sr">
            <NextStep item={item} quiet />
          </div>
        )}
        {hasExceptionsLink(item) && !inPanel && (
          <Link className={`${buttonClass("secondary", "lg")} work-exceptions`} href="/exceptions">
            See all exceptions
          </Link>
        )}
      </>
    );
  }

  // D-73: the line boards draw the workspace straight under the title. The facts, stations, agent card and next step
  // stay in the page for screen readers only (the contract data is never dropped), the way the state boards do.
  if (item.workspace) {
    // F-33, F-35: the income schedule boards draw the station row (desktop), and they and the leadership report boards draw the
    // working agent's card, in the workspace itself
    const lineKey = item.workspace.line_key;
    before = (
      <div className="cmp-sr">
        <FactsStrip facts={item.facts} paidNote={false} />
        {!(STATION_LINES.has(lineKey) && !phone) && <StationTrack stations={item.stations} state={item.state} />}
      </div>
    );
    main = (
      <div className="cmp-sr">
        {!drawsAgentCard(lineKey, agent.status) && <AgentCard agent={item.agent} />}
        <NextStep item={item} quiet />
      </div>
    );
    // F-30: the issue follow-up boards draw no exceptions button above the workspace; F-42, F-43, F-45: nor do the fixed asset,
    // cash forecast and ledger source boards, whose holds are a status, a reason and a Next sentence with no button (the button also sat on the phone station bar)
    after = hasExceptionsLink(item) && !['issue_followup', 'fixed_assets', 'ledger_sources', INTERNAL_RECONCILE_LINE].includes(item.workspace.line_key) ? (
      <Link className={`${buttonClass("secondary", "lg")} work-exceptions`} href="/exceptions">
        See all exceptions
      </Link>
    ) : null;
  }

  // A task the workspace's own steps already link to is decided from that link: no second card for it (F-23).
  const linked = new Set((item.workspace?.steps ?? []).map((step) => step.task_id).filter(Boolean));
  // F-33, F-35, F-42: on the lines that decide in place a decided task has nothing left to open; the workspace shows what it became.
  // F-39: the escalation boards draw no task card for a decision that is decided or has no step on the page. F-38: nor do the submission boards.
  const settled = (task: WorkItem['tasks'][number]) =>
    (AGENT_BESIDE_LINES.has(item.workspace?.line_key ?? '') && task.cannot_act_reason === 'already_decided') ||
    ((item.workspace?.line_key === 'escalation' || item.workspace?.line_key === 'rfp_submission') && (task.cannot_act_reason === 'already_decided' || !linked.has(task.id)));
  // F-37: on the RFP requirements page the team-input task is reached from the Team input tab and each team's Record; the board draws no second panel for it
  const rfpPage = !phone && item.workspace?.line_key === 'rfp_response' && item.rfp !== undefined;
  const shownTasks = asResponseItem(item).tasks.filter((task) => !linked.has(task.id) && !settled(task) && !(rfpPage && (task.response as { variant?: string } | undefined)?.variant === 'team_input'));

  return (
    <div className={layout ? `work-overview work-board work-state--${item.state}${layout === LAYOUTS.issue ? ' work-board--issue' : ''} work-board--${phone ? 'phone' : `desktop work-board--${layout.track}`}` : `work-overview${item.workspace ? ' work-overview--line' : ''}`}>
      {before}
      {/* F-32: a release item's workspace draws no main column (only screen-reader text), so its task panel takes the full width instead of floating right beside a blank column */}
      <div className={item.workspace?.line_key === 'delivery_release' && shownTasks.length > 0 ? 'work-columns work-columns--lone' : 'work-columns'}>
        <div className="work-column">{main}</div>
        <div className="work-column work-aside">
          {/* F-43: the cash forecast's workspace draws it, in the board's place at each width */}
          {!(item.workspace && forecastLine(item.workspace.line_key)) && <ReconcilePanel id={id} item={asResponseItem(item)} />}
          {aside}
          {shownTasks.length > 0 && <TaskPanels id={id} tasks={shownTasks} />}
          <RfpOutcomeLink id={id} item={item} />
          {view?.task_note && shownTasks.length > 0 && <p className="work-note">{view.task_note}</p>}
        </div>
      </div>
      {after}
      {item.workspace && <Workspace id={id} item={item} page={workspace} />}
    </div>
  );
}
