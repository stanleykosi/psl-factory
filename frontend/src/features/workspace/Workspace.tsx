'use client';

// PROPOSAL (D-LINE-WORKSPACE, contract mock only): the line workspace on the work item's Overview, drawn from
// E-WORK-ITEM `workspace` alone: the header, the sections in returned order and the steps exactly as returned.
// Nothing here reads /me or decides who may act; the backend composes every section and step. Steps write through
// E-WORK-STEP (useWorkspaceStep); a decision step links to the decision page; a reconcile goes to the existing
// ReconcilePanel, which the page shows from the re-read item.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

import { Button, Callout } from '@/components';
import type { WorkItem } from '@/features/work-item/labels';

import { agentName, type Item, type Section, type Step, type Workspace as WorkspaceData } from './labels';
import { WorkspaceLinks } from './Links';
import { itemsDefaultChecked, itemValues, workspaceLinks } from './proposals';
import { SectionView, type ItemControls } from './Sections';
import { StepForm } from './StepForm';
import { Consequence, StepControl, StepRow } from './Steps';
import type { WorkspacePage } from './usePageReload';
import { STEP_TEXT, useWorkspaceStep, type Attempt, type StepBody, type SubmitResult } from './useWorkspaceStep';

import './workspace.css';

/**
 * The header: the page's frame draws the crumbs, status and subtitle (D-73, as the line boards place them) and keeps
 * the one h1, so the workspace title is an h2 only when it differs.
 */
function AgentNote({ note }: { note: NonNullable<WorkspaceData['agent_note']> }) {
  return (
    <Callout kind="info" announce={false} icon={false} className="ws-agentnote">
      <span className="ws-stack">
        <strong>{agentName(note.agent)}</strong>
        {note.lines.map((line, i) => (
          <span key={i}>{line}</span>
        ))}
      </span>
    </Callout>
  );
}

/** While the agent works on a checklist the boards put the agent note beside that panel, in the main column. */
const noteBeside = (item: WorkItem) => item.agent.status === 'working' && (item.workspace?.sections.some((s) => s.kind === 'checklist') ?? false);

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

const scope = (step: Step) => step.applies_to ?? 'workspace';
const needsForm = (step: Step) => (step.fields?.length ?? 0) > 0 || step.confirm !== undefined;
const itemName = (section: Section, item: Item) => item.text ?? item.label ?? item.cells?.find((c) => c.text)?.text ?? item.id;

function WorkspaceSteps({ id, item, workspace, page }: { id: string; item: WorkItem; workspace: WorkspaceData; page: WorkspacePage }) {
  const steps = workspace.steps ?? [];
  const byKey = new Map(steps.map((s) => [s.key, s]));
  const flow = useWorkspaceStep({ id, revision: workspace.revision, page, awaitingReconcile: Boolean(item.reconcile) || item.state === 'effect_uncertain' });
  const [open, setOpen] = useState<Open | null>(null);
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
  const workspaceSteps = steps.filter((s) => scope(s) === 'workspace' || cross.has(s.key));
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

  const control = (step: Step, token: string, itemIds?: string[], extra?: { none?: boolean; describedBy?: string; items?: Open['items'] }) => (
    <StepControl
      key={token}
      workId={id}
      step={step}
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

  const form = (token: string, row?: Item): ReactNode => {
    if (open?.token !== token) return null;
    const failed = flow.notice?.kind === 'failed' && flow.notice.attempt === token && !flow.notice.sends;
    return (
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
      return own.length > 0 ? own.map((s) => control(s, `item:${section.key}:${it.id}:${s.key}`, [it.id])) : null;
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
  const said = new Set(workspaceSteps.map((s) => s.consequence));
  const nextLines = (workspace.next ?? []).filter((line) => line.trim() !== '' && !said.has(line));
  const hasNext = (workspace.next ?? []).length > 0;
  const showPanel = workspaceSteps.length > 0 || nextLines.length > 0;
  const side = workspace.sections.filter(inSide(item));
  const main = workspace.sections.filter((section) => !inSide(item)(section));
  const notice = flow.notice;
  return (
    <>
      <div ref={notices} className="ws-notices">
        {/* A finished or queued step is told politely; an uncertain send and a changed record answer the press, so each
            is an alert, as on base (a warning Callout has no live role of its own). */}
        <div role="status" aria-live="polite" className="ws-live">
          {(notice?.kind === 'done' || notice?.kind === 'queued') && (
            <Callout kind="success" announce={false}>
              {notice.kind === 'done' && notice.label && <strong>{notice.label} </strong>}
              <span>{notice.text}</span>
            </Callout>
          )}
        </div>
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
      <div className="ws-cols">
        <div className="ws-main">
          {noteBeside(item) && workspace.agent_note && workspace.agent_note.lines.length > 0 && <AgentNote note={workspace.agent_note} />}
          {main.map((section) => (
            <SectionView key={section.key} section={section} level={titled ? 3 : 2} controls={sectionControls} />
          ))}
          <WorkspaceLinks links={workspaceLinks(workspace)} page={page} />
        </div>
        {(side.length > 0 || showPanel) && (
          <aside className="ws-side" aria-label={hasNext && side.length === 0 ? undefined : 'Review and decide'} aria-labelledby={hasNext && side.length === 0 ? `${decideId}-head` : undefined}>
            {side.map((section) => (
              <SectionView key={section.key} section={section} level={titled ? 3 : 2} controls={sectionControls} />
            ))}
            {showPanel && (
              <section ref={decideRef} className={`psl-panel ${hasNext ? 'ws-decide--next' : 'psl-panel--decide'} ws-decide${workspaceSteps.length === 0 ? ' ws-decide--info' : ''}${flow.allLocked && hasReconcile ? ' ws-decide--flow' : ''}`} aria-labelledby={`${decideId}-head`} data-form-open={open?.token.startsWith('ws:') || undefined}>
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
                </div>
              </section>
            )}
            {workspaceSteps.map((s) => form(`ws:${s.key}`))}
          </aside>
        )}
      </div>
    </>
  );
}

export function Workspace({ id, item, page }: { id: string; item: WorkItem; page?: WorkspacePage }) {
  const workspace = item.workspace;
  if (!workspace) return null;
  const titled = workspace.title !== undefined && workspace.title !== item.title;
  // Without a revision no write control is drawn: the revision is never guessed.
  const writable = page !== undefined && typeof workspace.revision === 'number';
  return (
    <div className="ws" data-line={workspace.line_key}>
      <WorkspaceHeader workspace={workspace} itemTitle={item.title} beside={noteBeside(item)} />
      {writable ? (
        <WorkspaceSteps id={id} item={item} workspace={workspace} page={page} />
      ) : (
        <div className="ws-cols">
          <div className="ws-main">
            {noteBeside(item) && workspace.agent_note && workspace.agent_note.lines.length > 0 && <AgentNote note={workspace.agent_note} />}
            {workspace.sections
              .filter((section) => !inSide(item)(section))
              .map((section) => (
                <SectionView key={section.key} section={section} level={titled ? 3 : 2} />
              ))}
            <WorkspaceLinks links={workspaceLinks(workspace)} />
          </div>
          {workspace.sections.some(inSide(item)) && (
            <aside className="ws-side" aria-label="Review and decide">
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
