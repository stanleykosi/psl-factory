'use client';

// PROPOSAL (D-LINE-WORKSPACE, contract mock only): the line workspace on the work item's Overview, drawn from
// E-WORK-ITEM `workspace` alone: the header, the sections in returned order and the steps exactly as returned.
// Nothing here reads /me or decides who may act; the backend composes every section and step. Steps write through
// E-WORK-STEP (useWorkspaceStep); a decision step links to the decision page; a reconcile goes to the existing
// ReconcilePanel, which the page shows from the re-read item.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';

import Link from 'next/link';

import { Button, buttonClass, Callout, Drawer, formatClock, MiniStationBar, useIsPhone, type StationStatus } from '@/components';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';
import { currentStationIndex, STATIONS, type WorkItem } from '@/features/work-item/labels';
import { AgentCard, StationTrack } from '@/features/work-item/WorkItemOverview';

import { AssignForm } from './AssignForm';
import { agentName, WS_TEXT, type Item, type Section, type Step, type Workspace as WorkspaceData } from './labels';
import { InlineDecide, type DecidedNotice } from './InlineDecide';
import { WorkspaceLinks } from './Links';
import { assignDefault, itemsDefaultChecked, itemTeamKey, itemValues, startsLine, stepVerdict, warnLines, workspaceLinks, type WorkspaceLink } from './proposals';
import type { Recorded } from '@/features/response/contract';

import { RESPONSE_TEXT, ResponseDrawer, responseTaskFor } from './ResponseDrawer';
import { SectionView, type ItemControls } from './Sections';
import { StepForm } from './StepForm';
import { Consequence, StepControl, StepRow } from './Steps';
import { stepKind } from './StepForm';
import type { WorkspacePage } from './usePageReload';
import { ASSIGN_TEXT, useWorkspaceAssign } from './useWorkspaceAssign';
import { STEP_TEXT, useWorkspaceStep, type Attempt, type StepBody, type SubmitResult } from './useWorkspaceStep';

import './workspace.css';

/**
 * The header: the page's frame draws the crumbs, status and subtitle (D-73, as the line boards place them) and keeps
 * the one h1, so the workspace title is an h2 only when it differs.
 */
function AgentNote({ note }: { note: NonNullable<WorkspaceData['agent_note']> }) {
  const warn = warnLines(note);
  const lines = note.lines.map((line, i) => ({ line, i }));
  const plain = lines.filter(({ i }) => !warn.has(i));
  const amber = lines.filter(({ i }) => warn.has(i));
  return (
    <>
      {plain.length > 0 && (
        <Callout kind="info" announce={false} icon={false} className="ws-agentnote">
          <span className="ws-stack">
            <strong>{agentName(note.agent)}</strong>
            {plain.map(({ line, i }) => (
              <span key={i}>{line}</span>
            ))}
          </span>
        </Callout>
      )}
      {amber.length > 0 && (
        <Callout kind="warning" announce={false} className="ws-agentnote">
          <span className="ws-stack">
            {amber.map(({ line, i }) => (
              <span key={i}>{line}</span>
            ))}
          </span>
        </Callout>
      )}
    </>
  );
}

/** While the agent works on a checklist the boards put the agent note beside that panel, in the main column. */
const noteBeside = (item: WorkItem) => item.agent.status === 'working' && (item.workspace?.sections.some((s) => s.kind === 'checklist') ?? false);
/** F-30: the issue follow-up's board draws the agent note in the side column, under the panel; its facts as a strip under the title. */
const issueLine = (workspace: WorkspaceData) => workspace.line_key === 'issue_followup';

function WorkspaceHeader({ workspace, itemTitle, beside }: { workspace: WorkspaceData; itemTitle: string; beside: boolean }) {
  const { title, byline, version } = workspace;
  const note = beside ? undefined : workspace.agent_note;
  const showTitle = title !== undefined && title !== itemTitle;
  if (!showTitle && !byline && !version && !note) return null;
  return (
    <header className="ws-header">
      {showTitle && (
        <div className="ws-titleline">
          <h2 className="ws-title">{title}</h2>
        </div>
      )}
      {(byline || version) && (
        <p className="ws-byline">
          {byline && <span>{byline}</span>}
          {version && <span className="psl-mono ws-version">{version.label}</span>}
        </p>
      )}
      {note && note.lines.length > 0 && <AgentNote note={note} />}
    </header>
  );
}

/** Suggestions sit in the side column; so does the checklist while the agent is working, as the boards draw the assembling panel (D-81). */
const inSide = (item: WorkItem) => (section: Section) =>
  section.kind === 'suggestions' || (section.kind === 'checklist' && item.agent.status === 'working');

/** `items` is set for an `items` step: its ids are the ones ticked when the form is submitted (all sections, or that one), so the set sent is the set on screen. */
type Open = { token: string; step: Step; itemIds?: string[]; items?: { section?: string } };

/** The Start work line key of an issue's follow-up (E-LINES); the only name this frame reads for F-30's read-only link and phone Drawer. */
const ISSUE_LINE = 'issue_followup';
/** F-31: the engagement's register form opens in the phone Drawer too (the SCR-41 phone register board is its own screen). */
const ENGAGEMENT_LINE = 'engagement';
const ISSUE_TEXT = { register: 'Open the issue register' } as const;
/** F-33: the income schedule boards draw the stations in the main column and the working agent's card beside it. */
const INCOME_LINE = 'income_schedules';
/** F-39: the escalation boards draw Tola's card beside the sections while she works and once she has drafted. */
const ESCALATION_LINE = 'escalation';

/** Whether the workspace draws the agent's card itself (WorkItemOverview then keeps its copy for screen readers only). */
export const drawsAgentCard = (lineKey: string, status: string) =>
  (lineKey === INCOME_LINE && status === 'working') || (lineKey === ESCALATION_LINE && (status === 'working' || status === 'done'));

/** The stations as the income schedule boards draw them: a row of boxes on desktop, the small bar and its words on a phone
 *  (where the page keeps the full track for screen readers, WorkItemOverview). */
function LineStations({ item, phone }: { item: WorkItem; phone: boolean }) {
  const { stations } = item;
  if (stations.length === 0) return null;
  if (!phone) {
    return (
      <div className="ws-stations">
        <StationTrack stations={stations} state={item.state} quiet />
      </div>
    );
  }
  const current = currentStationIndex(stations);
  const at = current >= 0 ? current : stations.findLastIndex((s) => s.status !== 'not_started');
  const shown = stations[Math.max(at, 0)];
  return <MiniStationBar className="ws-ministations" stations={stations.map((s) => STATIONS[s.status].modifier as StationStatus)} text={`Station ${Math.max(at, 0) + 1} of ${stations.length} · ${shown.name}`} />;
}

/** The working agent's card beside the sections (WorkItemOverview then draws no copy of its own), with the card's own footer
 *  row: when it started and the workspace's assistant link ("Ask Chidi"), as CMP-09 draws them. */
function LineAgent({ agent, ask }: { agent: WorkItem['agent']; ask?: WorkspaceLink }) {
  const foot =
    agent.started_at || ask ? (
      <>
        <span>{agent.started_at && <>Started <time dateTime={agent.started_at}>{formatClock(agent.started_at)}</time></>}</span>
        {ask && (
          <Link className="psl-link ws-asklink" href="/assistant">
            {ask.label}
          </Link>
        )}
      </>
    ) : undefined;
  return (
    <div className="ws-lineagent">
      <AgentCard agent={agent} foot={foot} />
    </div>
  );
}

/** On the income line the working agent's card carries the assistant link; the other links stay where they are. */
const splitAsk = (links: WorkspaceLink[], inCard: boolean) => {
  const ask = inCard ? links.find((l) => l.kind === 'assistant') : undefined;
  return { ask, rest: ask ? links.filter((l) => l !== ask) : links };
};

/** The lead banner's tone follows the data (never the words): the issue follow-up reads the status tone (F-30); the income
 *  schedule line reads a stopped station too, as a returned or rejected schedule has (F-33). Every other line is unchanged. */
const bannerTone = (workspace: WorkspaceData, item: WorkItem): 'warning' | 'success' | 'problem' =>
  workspace.line_key === INCOME_LINE
    ? workspace.status?.tone === 'verified'
      ? 'success'
      : workspace.status?.tone === 'stopped' || workspace.status?.tone === 'uncertain' || item.stations.some((s) => s.status === 'stopped')
        ? 'problem'
        : 'warning'
    : workspace.line_key !== ISSUE_LINE ? (workspace.status?.tone === 'verified' ? 'success' : 'warning') : workspace.status?.tone === 'verified' ? 'success' : workspace.status?.tone === 'stopped' || workspace.status?.tone === 'uncertain' ? 'problem' : 'warning';

const scope = (step: Step) => step.applies_to ?? 'workspace';
const needsForm = (step: Step) => (step.fields?.length ?? 0) > 0 || step.confirm !== undefined;
const itemName = (section: Section, item: Item) => item.text ?? item.label ?? item.cells?.find((c) => c.text)?.text ?? item.id;

function WorkspaceSteps({ id, item, workspace, page }: { id: string; item: WorkItem; workspace: WorkspaceData; page: WorkspacePage }) {
  const steps = workspace.steps ?? [];
  const byKey = new Map(steps.map((s) => [s.key, s]));
  const flow = useWorkspaceStep({ id, revision: workspace.revision, page, awaitingReconcile: Boolean(item.reconcile) || item.state === 'effect_uncertain' });
  const [open, setOpen] = useState<Open | null>(null);
  // F-30: "Raise an escalation" opens Start work on the step's line, filled for the person to check; it sends nothing itself.
  const [starting, setStarting] = useState<{ token: string; line_key: string; intake: Record<string, unknown> } | null>(null);
  const assign = item.assign;
  const assignFlow = useWorkspaceAssign({ id, revision: workspace.revision, page, role: assign?.role });
  const [assigning, setAssigning] = useState(false);
  const assignButton = useRef<HTMLButtonElement>(null);
  const phone = useIsPhone();
  // F-30 (D-103, D-107): on a phone the issue follow-up's forms open in the full-height Drawer.
  const inDrawer = phone && (workspace.line_key === ISSUE_LINE || workspace.line_key === ENGAGEMENT_LINE || workspace.line_key === INCOME_LINE);
  const incomeLine = workspace.line_key === INCOME_LINE;
  // F-31: a department's "Record input" opens F-18's team-input form in the Drawer; `recording` names the pressed row's button.
  const [recording, setRecording] = useState<{ token: string; taskId: string; teamKey?: string; heading: HTMLElement | null } | null>(null);
  const [recorded, setRecorded] = useState<string | null>(null);
  const [teamGone, setTeamGone] = useState<string | null>(null);
  // QA-2-5: the write answered 200 but the re-read failed: say it was sent, never that it is recorded
  const [sentNote, setSentNote] = useState(false);
  // The PM's own tick or untick of an `items` target, by section and item id. An item the PM has not touched follows the
  // step's `items_default` (PROPOSAL G-SCR28-1), so an item that arrives with a reload starts as the data says.
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  const controls = useRef(new Map<string, HTMLButtonElement | null>());
  // The attempt a manual Try again repeats (same key), after a network or server failure on a step that doesn't send.
  const last = useRef<Attempt | null>(null);
  const titled = workspace.title !== undefined && workspace.title !== item.title;
  const decideId = useId();
  // an uncertain item with no reconcile: nothing to confirm here, the notice says it is being checked
  const noReconcile = item.state === 'effect_uncertain' && !item.reconcile;
  const hasReconcile = Boolean(item.reconcile) && (item.allowed_actions ?? []).includes('reconcile');

  // On a phone the Decide panel is pinned to the bottom: the page keeps its height clear below it (see workspace.css).
  const decideRef = useRef<HTMLElement>(null);
  const itemsSteps = steps.filter((s) => scope(s) === 'items');
  // an `items` step whose targets sit in more than one section is one control in the workspace row, over the ticks in all of them
  const cross = new Set(itemsSteps.filter((s) => workspace.sections.filter((sec) => !sec.restricted && sec.items.some((it) => it.steps?.includes(s.key))).length > 1).map((s) => s.key));
  const allWorkspaceSteps = steps.filter((s) => scope(s) === 'workspace' || cross.has(s.key));
  // F-33: a decision step with a verdict the page offers is decided in place (InlineDecide), one panel per task; one
  // with a verdict it does not offer is not drawn; one with no verdict stays the link to the decision page.
  const workspaceSteps = allWorkspaceSteps.filter((s) => stepVerdict(s) === undefined);
  const decideTasks = new Map<string, Step[]>();
  for (const s of allWorkspaceSteps) {
    if (!stepVerdict(s) || !s.task_id) continue;
    decideTasks.set(s.task_id, [...(decideTasks.get(s.task_id) ?? []), s]);
  }
  const [decided, setDecided] = useState<DecidedNotice | null>(null);
  const onDecided = useCallback((notice: DecidedNotice) => setDecided(notice), []);
  // TECH-2-1: a decide starting clears the last step's notice and the last decision's, so its own outcome always shows
  const { setNotice } = flow;
  const onDeciding = useCallback(() => {
    setNotice(null);
    setDecided(null);
  }, [setNotice]);
  // The decision's notice belongs to the item as re-read after it: it goes when the item moves on or another step is sent.
  const decidedShown = decided !== null && decided.revision === workspace.revision && flow.pending === null && flow.notice === null ? decided : null;
  const hasDecide = workspaceSteps.length > 0;
  useEffect(() => {
    const bar = decideRef.current;
    if (!bar) return;
    const root = document.documentElement;
    const measure = () => root.style.setProperty('--ws-bar-h', `${bar.offsetHeight}px`);
    measure();
    const watch = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    watch?.observe(bar);
    return () => {
      watch?.disconnect();
      root.style.removeProperty('--ws-bar-h');
    };
  }, [hasDecide]);

  // A failure is told at the top of the page: bring it into view when the pressed control is somewhere else.
  const notices = useRef<HTMLDivElement>(null);
  const failure = flow.notice?.kind === 'failed' || flow.notice?.kind === 'problem' || flow.notice?.kind === 'uncertain' ? flow.notice : null;
  // the re-read after the press can lay the page out again (the reconcile panel appears), so it looks again once that lands
  useEffect(() => {
    if (failure) notices.current?.querySelector('.ws-notice')?.scrollIntoView?.({ block: 'nearest' });
  }, [failure, workspace.revision]);

  const off = (step: Step) => flow.pending !== null || flow.allLocked || flow.locked.has(step.key) || page.refreshFailed;

  const close = (token: string) => {
    setOpen(null);
    requestAnimationFrame(() => controls.current.get(token)?.focus());
  };

  const run = async (attempt: Attempt, request?: Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'>): Promise<SubmitResult> => {
    last.current = attempt;
    const result = await flow.submit(attempt, request);
    if (result.kind === 'done') setOpen(null);
    if (result.kind === 'invalid' && !open) flow.setNotice({ kind: 'problem', text: result.message ?? STEP_TEXT.failed });
    return result;
  };

  const press = (step: Step, token: string, itemIds?: string[], items?: Open['items']) => {
    if (off(step)) return;
    if (needsForm(step)) {
      flow.renew(token);
      setOpen({ token, step, itemIds, items });
      return;
    }
    void run({ token, step, itemIds });
  };

  const control = (step: Step, token: string, itemIds?: string[], extra?: { none?: boolean; describedBy?: string; items?: Open['items']; row?: Item }) => {
    const starts = step.disabled_reason || step.task_id ? undefined : startsLine(step);
    if (starts) {
      return (
        <Button
          key={token}
          kind={stepKind(step)}
          aria-haspopup="dialog"
          aria-describedby={extra?.describedBy}
          ref={(el) => {
            controls.current.set(token, el);
          }}
          onClick={() => setStarting({ token, ...starts })}
        >
          {step.label}
        </Button>
      );
    }
    // F-31: a step that names a team-input response task in this item opens the form in the Drawer (the task must be one this person can act on)
    const responseTask = step.task_id && !step.disabled_reason ? responseTaskFor(item, step.task_id) : undefined;
    if (responseTask) {
      if (!responseTask.open) return null;
      const taskId = step.task_id!;
      return (
        <Button
          key={token}
          kind={stepKind(step)}
          aria-haspopup="dialog"
          aria-disabled={off(step) || undefined}
          aria-describedby={extra?.describedBy}
          ref={(el) => {
            controls.current.set(token, el);
          }}
          onClick={(event) => {
            if (off(step)) return;
            setRecorded(null);
            setTeamGone(null);
            setSentNote(false);
            setRecording({ token, taskId, teamKey: extra?.row ? itemTeamKey(extra.row) : undefined, heading: event.currentTarget.closest('section')?.querySelector<HTMLElement>('h2, h3') ?? null });
          }}
        >
          {step.label}
        </Button>
      );
    }
    return (
    <StepControl
      key={token}
      workId={id}
      step={step}
      tasks={item.tasks}
      off={off(step)}
      pending={flow.pending === token}
      none={extra?.none}
      describedBy={extra?.describedBy}
      controlRef={(el) => {
        controls.current.set(token, el);
      }}
      onPress={() => press(step, token, itemIds, extra?.items)}
    />
    );
  };

  const form = (token: string, row?: Item): ReactNode => {
    if (open?.token !== token) return null;
    const failed = flow.notice?.kind === 'failed' && flow.notice.attempt === token && !flow.notice.sends;
    const shown = (
      <StepForm
        key={token}
        workId={id}
        lineKey={workspace.line_key}
        step={open.step}
        caseId={item.case_id}
        caseRevision={item.case_revision}
        pending={flow.pending === token}
        off={off(open.step)}
        submitLabel={failed ? 'Try again' : undefined}
        initial={row ? itemValues(row) : undefined}
        consequence={<Consequence step={open.step} />}
        summary={issueLine(workspace)}
        onSubmit={(request) => {
          const itemIds = open.items ? liveIds(open.step, open.items.section) : open.itemIds;
          // everything was unticked while the form was open: nothing to send
          if (open.items && itemIds?.length === 0) return Promise.resolve<SubmitResult>({ kind: 'kept' });
          return run({ token, step: open.step, itemIds }, request);
        }}
        onClose={() => close(token)}
        onAccessError={page.onAccessLost}
      />
    );
    return inDrawer ? (
      <Drawer title={open.step.label} onClose={() => close(token)}>
        {shown}
      </Drawer>
    ) : (
      shown
    );
  };

  const closeRecording = () => {
    const token = recording?.token;
    setRecording(null);
    requestAnimationFrame(() => (token ? controls.current.get(token) : null)?.focus());
  };
  // 200: the drawer is gone, the item is re-read (the row's new state comes only from that), and focus goes to the table's heading
  const afterRecorded = async (result: Recorded | undefined) => {
    const heading = recording?.heading;
    setRecording(null);
    // the notice waits for the re-read (TECH-1-1): nothing says "recorded" until the item itself has been read again
    const item = await page.reload();
    if (item) setRecorded(RESPONSE_TEXT.done(result?.summary, result?.at));
    else setSentNote(true);
    requestAnimationFrame(() => {
      if (!heading) return;
      heading.tabIndex = -1;
      heading.focus();
    });
  };

  // UX-1-1: the re-read no longer lists the chosen team; the page shows where things stand
  const afterTeamGone = (name: string) => {
    const heading = recording?.heading;
    setRecording(null);
    setTeamGone(name);
    void page.reload().then(() =>
      requestAnimationFrame(() => {
        if (!heading) return;
        heading.tabIndex = -1;
        heading.focus();
      }),
    );
  };

  const closeAssign = () => {
    setAssigning(false);
    requestAnimationFrame(() => assignButton.current?.focus());
  };
  const assignOff = assignFlow.pending || flow.pending !== null || flow.allLocked || page.refreshFailed;
  // F-31: with a default among the candidates the form is drawn open inside the side panel (the engagement's "Confirm PM")
  const preset = assign && assign.candidates.length > 0 ? assignDefault(assign) : undefined;
  const assignForm = (inPanel: boolean, labelledBy?: string) => {
    if (!assign || assign.candidates.length === 0 || (inPanel ? !preset : !assigning || preset)) return null;
    const form = (
      <AssignForm
        assign={assign}
        pending={assignFlow.pending}
        preset={preset}
        labelledBy={inPanel ? labelledBy : undefined}
        submitLabel={assignFlow.notice?.kind === 'unconfirmed' ? ASSIGN_TEXT.tryAgain : undefined}
        onSubmit={async (request) => {
          if (assignOff) return { kind: 'kept' };
          const result = await assignFlow.submit(request);
          if (result.kind === 'done') {
            setAssigning(false);
            // the page's own heading takes focus: the button that opened the form is gone with the owner
            requestAnimationFrame(() => {
              const heading = document.querySelector<HTMLElement>('h1');
              if (heading) {
                heading.tabIndex = -1;
                heading.focus();
              }
            });
          }
          return result;
        }}
        onClose={inPanel ? undefined : closeAssign}
      />
    );
    return inPanel ? form : inDrawer ? (
      <Drawer title={ASSIGN_TEXT.open} onClose={closeAssign}>
        {form}
      </Drawer>
    ) : (
      form
    );
  };

  const isItemsTarget = (item: Item) => itemsSteps.some((s) => item.steps?.includes(s.key));
  const choiceKey = (section: Section, it: Item) => `${section.key}:${it.id}`;
  // a section that is not drawn (restricted) adds nothing to the confirm set
  const ticked = (section: Section, it: Item) => !section.restricted && isItemsTarget(it) && !it.restricted && (choices[choiceKey(section, it)] ?? itemsSteps.some((s) => it.steps?.includes(s.key) && itemsDefaultChecked(s)));
  const tickedFor = (section: Section, step: Step) => section.items.filter((it) => it.steps?.includes(step.key) && ticked(section, it)).map((it) => it.id);

  const liveIds = (step: Step, section?: string) => workspace.sections.filter((sec) => section === undefined || sec.key === section).flatMap((sec) => tickedFor(sec, step));

  const sectionControls: ItemControls = {
    item: (section, it) => {
      const own = (it.steps ?? []).map((k) => byKey.get(k)).filter((s): s is Step => s !== undefined && scope(s) === 'item');
      // an item step names its item: the backend can't know which row "Remove" or "Edit" was pressed on otherwise
      return own.length > 0 ? own.map((s) => control(s, `item:${section.key}:${it.id}:${s.key}`, [it.id], { row: it })) : null;
    },
    after: (section, it) => {
      const own = (it.steps ?? []).map((k) => byKey.get(k)).filter((s): s is Step => s !== undefined && scope(s) === 'item');
      return own.map((s) => form(`item:${section.key}:${it.id}:${s.key}`, it));
    },
  };
  if (itemsSteps.length > 0) {
    sectionControls.select = (section, it) => {
      if (!section.items.some(isItemsTarget)) return undefined;
      if (!isItemsTarget(it)) return <span />;
      const checked = ticked(section, it);
      return (
        // the label is the 44px target around the box
        <label className="ws-checkwrap">
          <input
            type="checkbox"
            className="ws-check"
            aria-label={`Select ${itemName(section, it)}`}
            checked={checked}
            onChange={(event) => setChoices((current) => ({ ...current, [choiceKey(section, it)]: event.target.checked }))}
          />
        </label>
      );
    };
    sectionControls.foot = (section) => {
      const usable = itemsSteps.filter((s) => !cross.has(s.key) && section.items.some((it) => it.steps?.includes(s.key)));
      if (usable.length === 0) return null;
      const chosen = section.items.filter((it) => ticked(section, it)).map((it) => it.id);
      return (
        <div className="ws-bulk">
          <span className="ws-count psl-mono" aria-live="polite">
            {chosen.length} selected
          </span>
          <StepRow steps={usable}>
            {(s, describedBy) => {
              const ids = tickedFor(section, s);
              return control(s, `items:${section.key}:${s.key}`, ids, { none: ids.length === 0, describedBy, items: { section: section.key } });
            }}
          </StepRow>
          {usable.map((s) => form(`items:${section.key}:${s.key}`))}
        </div>
      );
    };
  }

  // Conflicts 4: when the backend returns `next` lines the panel is "Next" and carries them; lines a step already says are not repeated.
  const said = new Set(allWorkspaceSteps.map((s) => s.consequence));
  const nextLines = (workspace.next ?? []).filter((line) => line.trim() !== '' && !said.has(line));
  const hasNext = (workspace.next ?? []).length > 0;
  // F-30: a follow-up with nothing to press points at the register, where closing is done; the id is one the response carries.
  const registerCase = workspace.line_key === ISSUE_LINE && workspaceSteps.length === 0 && assign === undefined ? workspace.context?.project?.case_id : undefined;
  const readOnlyIssue = registerCase !== undefined;
  const showPanel = workspaceSteps.length > 0 || nextLines.length > 0 || assign !== undefined || readOnlyIssue;
  const strip = issueLine(workspace) ? workspace.sections.filter((section) => section.kind === 'facts') : [];
  const side = workspace.sections.filter(inSide(item));
  const main = workspace.sections.filter((section) => !inSide(item)(section) && !strip.includes(section));
  const sideNote = issueLine(workspace) && workspace.agent_note !== undefined && workspace.agent_note.lines.length > 0;
  const agentSide = drawsAgentCard(workspace.line_key, item.agent.status);
  const notice = flow.notice;
  return (
    <>
      <div ref={notices} className="ws-notices">
        {/* A finished or queued step is told politely; an uncertain send and a changed record answer the press, so each
            is an alert, as on base (a warning Callout has no live role of its own). */}
        <div role="status" aria-live="polite" className="ws-live">
          {recorded && (
            <Callout kind="success" announce={false}>
              <span>{recorded}</span>
            </Callout>
          )}
          {sentNote && (
            <Callout kind="warning" announce={false}>
              <span>{RESPONSE_TEXT.sentNoRefresh}</span>
            </Callout>
          )}
          {teamGone && (
            <Callout kind="warning" announce={false}>
              <span>{RESPONSE_TEXT.teamGone(teamGone)}</span>
            </Callout>
          )}
          {assignFlow.notice?.kind === 'done' && (
            <Callout kind="success" announce={false}>
              <span>{assignFlow.notice.text}</span>
            </Callout>
          )}
          {decidedShown?.settled && (
            <Callout kind="success" announce={false}>
              <span>{decidedShown.text}</span>
            </Callout>
          )}
          {(notice?.kind === 'done' || notice?.kind === 'queued') && (
            <Callout kind="success" announce={false}>
              {notice.kind === 'done' && notice.label && <strong>{notice.label} </strong>}
              <span>{notice.text}</span>
            </Callout>
          )}
        </div>
        {decidedShown && !decidedShown.settled && (
          <div role="alert">
            <Callout kind="warning" className="ws-notice">
              <span>{decidedShown.text}</span>
            </Callout>
          </div>
        )}
        {notice?.kind === 'uncertain' && (
          <div role="alert">
            <Callout kind="warning" className="ws-notice">
              <span className="ws-stack">
                {notice.message && <span>{notice.message}</span>}
                {!hasReconcile && <span>{STEP_TEXT.uncertainNoReconcile}</span>}
              </span>
              {!hasReconcile && (
                <Button kind="secondary" onClick={() => void page.reload()}>
                  Reload
                </Button>
              )}
            </Callout>
          </div>
        )}
        {/* an uncertain item the reload returned with no reconcile: nothing can be answered or sent, and the page says so */}
        {noReconcile && notice?.kind !== 'uncertain' && (
          <div role="alert">
            <Callout kind="warning" className="ws-notice">
              <span>{STEP_TEXT.uncertainNoReconcile}</span>
              <Button kind="secondary" onClick={() => void page.reload()}>
                Reload
              </Button>
            </Callout>
          </div>
        )}
        {assignFlow.notice?.kind === 'stale' && (
          <div role="alert">
            <Callout kind="warning" className="ws-notice">
              {ASSIGN_TEXT.stale(assignFlow.notice.revision)}
            </Callout>
          </div>
        )}
        {assignFlow.notice?.kind === 'unconfirmed' && (
          <Callout kind="problem" className="ws-notice">
            <span className="ws-stack">
              <strong>{assign?.role === 'PM' ? ASSIGN_TEXT.pmUnconfirmedHead : ASSIGN_TEXT.unconfirmedHead}</strong>
              <span>{assign?.role === 'PM' ? ASSIGN_TEXT.pmUnconfirmed : ASSIGN_TEXT.unconfirmed}</span>
            </span>
          </Callout>
        )}
        {notice?.kind === 'stale' && (
          <div role="alert">
            <Callout kind="warning" className="ws-notice">
              {STEP_TEXT.stale(notice.revision)}
            </Callout>
          </div>
        )}
        {(notice?.kind === 'forbidden' || notice?.kind === 'problem' || notice?.kind === 'failed') && (
          <Callout kind="problem" className="ws-notice">
            <span className="ws-stack">
              {notice.kind === 'failed' && <strong>{notice.label}</strong>}
              <span>{notice.kind === 'forbidden' ? STEP_TEXT.forbidden : notice.kind === 'problem' ? notice.text : STEP_TEXT.failed}</span>
            </span>
            {notice.kind === 'failed' && !notice.sends && !open && (
              <Button
                kind="secondary"
                onClick={() => {
                  if (last.current?.token === notice.attempt) void run(last.current);
                }}
              >
                Try again
              </Button>
            )}
          </Callout>
        )}
      </div>
      {page.refreshFailed && (
        <p className="ws-reload">
          <Button kind="secondary" onClick={() => void page.reload()}>
            Reload this item
          </Button>
        </p>
      )}
      {/* The line boards' shared layout, by section kind and step type (D-62): suggestions and the workspace
          steps sit in a side column with a coloured head; on a phone the steps pin to the bottom. */}
      {strip.map((section) => (
        <SectionView key={section.key} section={section} level={titled ? 3 : 2} strip />
      ))}
      <div className="ws-cols">
        <div className="ws-main">
          {incomeLine && <LineStations item={item} phone={phone} />}
          {noteBeside(item) && workspace.agent_note && workspace.agent_note.lines.length > 0 && <AgentNote note={workspace.agent_note} />}
          {workspace.sections.length === 0 && workspaceSteps.length === 0 && assign === undefined && <p className="ws-empty">{WS_TEXT.empty}</p>}
          {main.map((section) => (
            <SectionView key={section.key} section={section} level={titled ? 3 : 2} controls={sectionControls} banner={bannerTone(workspace, item)} />
          ))}
          <WorkspaceLinks links={splitAsk(workspaceLinks(workspace), agentSide).rest} page={page} />
        </div>
        {(side.length > 0 || showPanel || sideNote || decideTasks.size > 0 || agentSide) && (
          <aside className="ws-side" aria-label={hasNext && side.length === 0 ? undefined : 'Review and decide'} aria-labelledby={hasNext && side.length === 0 ? `${decideId}-head` : undefined}>
            {side.map((section) => (
              <SectionView key={section.key} section={section} level={titled ? 3 : 2} controls={sectionControls} />
            ))}
            {agentSide && <LineAgent agent={item.agent} ask={splitAsk(workspaceLinks(workspace), true).ask} />}
            {[...decideTasks].map(([taskId, taskSteps]) => (
              <InlineDecide key={taskId} id={id} taskId={taskId} steps={taskSteps} page={page} off={flow.pending !== null || flow.allLocked || page.refreshFailed} onDecided={onDecided} onDeciding={onDeciding} />
            ))}
            {showPanel && (
              <section ref={decideRef} className={`psl-panel ${hasNext ? 'ws-decide--next' : 'psl-panel--decide'} ws-decide${workspaceSteps.length === 0 && (preset || !(assign && assign.candidates.length > 0)) ? ' ws-decide--info' : ''}${flow.allLocked && hasReconcile ? ' ws-decide--flow' : ''}`} aria-labelledby={`${decideId}-head`} data-form-open={open?.token.startsWith('ws:') || undefined}>
                <h2 id={`${decideId}-head`} className={`psl-panel__head ${hasNext ? '' : 'psl-panel__head--decide '}ws-decide__head`}>
                  {hasNext ? STEP_TEXT.next : STEP_TEXT.decide}
                </h2>
                <div className="psl-panel__body ws-decide__body">
                  {nextLines.map((line, i) => (
                    <p key={i} className="ws-consequence">
                      {line}
                    </p>
                  ))}
                  <StepRow steps={workspaceSteps} hint={flow.allLocked && !noReconcile ? (item.reconcile && !hasReconcile ? STEP_TEXT.confirmFirstByOther : STEP_TEXT.confirmFirst) : undefined}>
                    {(s, describedBy) => {
                      if (!cross.has(s.key)) return control(s, `ws:${s.key}`, undefined, { describedBy });
                      const ids = workspace.sections.flatMap((section) => tickedFor(section, s));
                      return control(s, `ws:${s.key}`, ids, { none: ids.length === 0, describedBy, items: {} });
                    }}
                  </StepRow>
                  {assignForm(true, `${decideId}-head`)}
                  {assign && assign.candidates.length > 0 && !preset && (
                    <Button
                      ref={assignButton}
                      kind="primary"
                      aria-haspopup="dialog"
                      aria-disabled={assignOff || undefined}
                      onClick={() => {
                        if (!assignOff) setAssigning(true);
                      }}
                    >
                      {ASSIGN_TEXT.open}
                    </Button>
                  )}
                  {assign && assign.candidates.length === 0 && <p className="ws-consequence">{ASSIGN_TEXT.noCandidates}</p>}
                  {registerCase !== undefined && (
                    <Link className={buttonClass('secondary')} href={`/projects/${encodeURIComponent(registerCase)}/registers`}>
                      {ISSUE_TEXT.register}
                    </Link>
                  )}
                </div>
              </section>
            )}
            {workspaceSteps.map((s) => form(`ws:${s.key}`))}
            {assignForm(false)}
            {sideNote && <AgentNote note={workspace.agent_note!} />}
          </aside>
        )}
      </div>
      {recording && (
        <ResponseDrawer
          workId={id}
          taskId={recording.taskId}
          title={item.tasks.find((t) => t.id === recording.taskId)?.title ?? 'Record input'}
          teamKey={recording.teamKey}
          eyebrow={workspace.context?.project?.title}
          onTeamGone={afterTeamGone}
          onClose={closeRecording}
          onRecorded={(result) => void afterRecorded(result)}
          onAccessLost={page.onAccessLost}
        />
      )}
      {starting && (
        <StartWorkDrawer
          entry="default"
          prefill={{ line_key: starting.line_key, intake: starting.intake }}
          onClose={() => {
            const { token } = starting;
            setStarting(null);
            requestAnimationFrame(() => controls.current.get(token)?.focus());
          }}
        />
      )}
    </>
  );
}

export function Workspace({ id, item, page }: { id: string; item: WorkItem; page?: WorkspacePage }) {
  const workspace = item.workspace;
  const phone = useIsPhone();
  if (!workspace) return null;
  // the income line's stations and working agent are drawn here whichever branch draws the sections (WorkItemOverview draws no copy)
  const income = workspace.line_key === INCOME_LINE;
  const agentSide = drawsAgentCard(workspace.line_key, item.agent.status);
  const titled = workspace.title !== undefined && workspace.title !== item.title;
  // Without a revision no write control is drawn: the revision is never guessed.
  const writable = page !== undefined && typeof workspace.revision === 'number';
  return (
    <div className="ws" data-line={workspace.line_key}>
      <WorkspaceHeader workspace={workspace} itemTitle={item.title} beside={noteBeside(item) || issueLine(workspace)} />
      {writable ? (
        <WorkspaceSteps id={id} item={item} workspace={workspace} page={page} />
      ) : (
        <div className="ws-cols">
          <div className="ws-main">
            {income && <LineStations item={item} phone={phone} />}
            {noteBeside(item) && workspace.agent_note && workspace.agent_note.lines.length > 0 && <AgentNote note={workspace.agent_note} />}
            {workspace.sections
              .filter((section) => !inSide(item)(section))
              .map((section) => (
                <SectionView key={section.key} section={section} level={titled ? 3 : 2} />
              ))}
            <WorkspaceLinks links={splitAsk(workspaceLinks(workspace), agentSide).rest} />
          </div>
          {(workspace.sections.some(inSide(item)) || agentSide) && (
            <aside className="ws-side" aria-label="Review and decide">
              {agentSide && <LineAgent agent={item.agent} ask={splitAsk(workspaceLinks(workspace), true).ask} />}
              {workspace.sections
                .filter(inSide(item))
                .map((section) => (
                  <SectionView key={section.key} section={section} level={titled ? 3 : 2} />
                ))}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
