'use client';

// PROPOSAL (D-LINE-WORKSPACE, contract mock only): the line workspace on the work item's Overview, drawn from
// E-WORK-ITEM `workspace` alone: the header, the sections in returned order and the steps exactly as returned.
// Nothing here reads /me or decides who may act; the backend composes every section and step. Steps write through
// E-WORK-STEP (useWorkspaceStep); a decision step links to the decision page; a reconcile goes to the existing
// ReconcilePanel, which the page shows from the re-read item.
import { useRef, useState, type ReactNode } from 'react';

import type { WorkItem } from '@/features/work-item/labels';
import { WarningIcon } from '@/shell/icons';

import { agentName, tagClass, type Item, type Section, type Step, type Workspace as WorkspaceData } from './labels';
import { SectionView, type ItemControls } from './Sections';
import { StepForm } from './StepForm';
import { Consequence, StepControl, StepRow } from './Steps';
import type { WorkspacePage } from './usePageReload';
import { STEP_TEXT, useWorkspaceStep, type Attempt, type StepBody, type SubmitResult } from './useWorkspaceStep';

import './workspace.css';

/** The header: the work item keeps the page's one h1, so the workspace title is an h2 only when it differs. */
function WorkspaceHeader({ workspace, itemTitle }: { workspace: WorkspaceData; itemTitle: string }) {
  const { title, subtitle, status, byline, version, context, agent_note: note } = workspace;
  const crumbs = context?.crumbs ?? [];
  const showTitle = title !== undefined && title !== itemTitle;
  if (!showTitle && !subtitle && !status && !byline && !version && crumbs.length === 0 && !note) return null;
  return (
    <header className="ws-header">
      {crumbs.length > 0 && (
        <nav aria-label="Where this sits">
          <ol className="psl-crumb ws-crumbs">
            {crumbs.map((c, i) => (
              <li key={`${c.value}-${i}`} aria-current={i === crumbs.length - 1 ? 'location' : undefined}>
                {c.label}
              </li>
            ))}
          </ol>
        </nav>
      )}
      {(showTitle || status) && (
        <div className="ws-titleline">
          {showTitle && <h2 className="ws-title">{title}</h2>}
          {status && <span className={`${tagClass(status.tone)} ws-status`}>{status.label}</span>}
        </div>
      )}
      {subtitle && <p className="ws-subtitle">{subtitle}</p>}
      {(byline || version) && (
        <p className="ws-byline">
          {byline && <span>{byline}</span>}
          {version && <span className="psl-mono ws-version">{version.label}</span>}
        </p>
      )}
      {note && note.lines.length > 0 && (
        <div className="psl-callout psl-callout--info ws-agentnote">
          <span className="ws-stack">
            <strong>{agentName(note.agent)}</strong>
            {note.lines.map((line, i) => (
              <span key={i}>{line}</span>
            ))}
          </span>
        </div>
      )}
    </header>
  );
}

type Open = { token: string; step: Step; itemIds?: string[] };

const scope = (step: Step) => step.applies_to ?? 'workspace';
const needsForm = (step: Step) => (step.fields?.length ?? 0) > 0 || step.confirm !== undefined;
const itemName = (section: Section, item: Item) => item.text ?? item.label ?? item.cells?.find((c) => c.text)?.text ?? item.id;

function WorkspaceSteps({ id, item, workspace, page }: { id: string; item: WorkItem; workspace: WorkspaceData; page: WorkspacePage }) {
  const steps = workspace.steps ?? [];
  const byKey = new Map(steps.map((s) => [s.key, s]));
  const flow = useWorkspaceStep({ id, revision: workspace.revision, page });
  const [open, setOpen] = useState<Open | null>(null);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const controls = useRef(new Map<string, HTMLButtonElement | null>());
  // The attempt a manual Try again repeats (same key), after a network or server failure on a step that doesn't send.
  const last = useRef<Attempt | null>(null);
  const titled = workspace.title !== undefined && workspace.title !== item.title;
  const hasReconcile = Boolean(item.reconcile) && (item.allowed_actions ?? []).includes('reconcile');

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

  const press = (step: Step, token: string, itemIds?: string[]) => {
    if (off(step)) return;
    if (needsForm(step)) {
      flow.renew(token);
      setOpen({ token, step, itemIds });
      return;
    }
    void run({ token, step, itemIds });
  };

  const control = (step: Step, token: string, itemIds?: string[], extra?: { none?: boolean; describedBy?: string }) => (
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
      onPress={() => press(step, token, itemIds)}
    />
  );

  const form = (token: string): ReactNode => {
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
        consequence={<Consequence step={open.step} />}
        onSubmit={(request) => run({ token, step: open.step, itemIds: open.itemIds }, request)}
        onClose={() => close(token)}
        onAccessError={page.onAccessLost}
      />
    );
  };

  const workspaceSteps = steps.filter((s) => scope(s) === 'workspace');
  const itemsSteps = steps.filter((s) => scope(s) === 'items');
  const isItemsTarget = (item: Item) => itemsSteps.some((s) => item.steps?.includes(s.key));

  const sectionControls: ItemControls = {
    item: (section, it) => {
      const own = (it.steps ?? []).map((k) => byKey.get(k)).filter((s): s is Step => s !== undefined && scope(s) === 'item');
      return own.length > 0 ? own.map((s) => control(s, `item:${section.key}:${it.id}:${s.key}`)) : null;
    },
    after: (section, it) => {
      const own = (it.steps ?? []).map((k) => byKey.get(k)).filter((s): s is Step => s !== undefined && scope(s) === 'item');
      return own.map((s) => form(`item:${section.key}:${it.id}:${s.key}`));
    },
  };
  if (itemsSteps.length > 0) {
    sectionControls.select = (section, it) => {
      if (!section.items.some(isItemsTarget)) return undefined;
      if (!isItemsTarget(it)) return <span />;
      const checked = selected[section.key]?.includes(it.id) ?? false;
      return (
        // the label is the 44px target around the box
        <label className="ws-checkwrap">
          <input
            type="checkbox"
            className="ws-check"
            aria-label={`Select ${itemName(section, it)}`}
            checked={checked}
            onChange={(event) =>
              setSelected((current) => {
                const now = new Set(current[section.key] ?? []);
                if (event.target.checked) now.add(it.id);
                else now.delete(it.id);
                return { ...current, [section.key]: section.items.filter((i) => now.has(i.id)).map((i) => i.id) };
              })
            }
          />
        </label>
      );
    };
    sectionControls.foot = (section) => {
      const usable = itemsSteps.filter((s) => section.items.some((it) => it.steps?.includes(s.key)));
      if (usable.length === 0) return null;
      const chosen = selected[section.key] ?? [];
      return (
        <div className="ws-bulk">
          <span className="ws-count psl-mono" aria-live="polite">
            {chosen.length} selected
          </span>
          <StepRow steps={usable}>
            {(s, describedBy) => {
              const ids = section.items.filter((it) => chosen.includes(it.id) && it.steps?.includes(s.key)).map((it) => it.id);
              return control(s, `items:${section.key}:${s.key}`, ids, { none: ids.length === 0, describedBy });
            }}
          </StepRow>
          {usable.map((s) => form(`items:${section.key}:${s.key}`))}
        </div>
      );
    };
  }

  const notice = flow.notice;
  return (
    <>
      <div role="status" aria-live="polite" className="ws-live">
        {(notice?.kind === 'done' || notice?.kind === 'queued') && <p className="psl-callout psl-callout--success">{notice.text}</p>}
      </div>
      {notice?.kind === 'uncertain' && (
        <div className="psl-callout psl-callout--warning ws-notice" role="alert">
          <WarningIcon />
          <span className="ws-stack">
            {notice.message && <span>{notice.message}</span>}
            {!hasReconcile && <span>{STEP_TEXT.uncertainNoReconcile}</span>}
          </span>
          {!hasReconcile && (
            <button type="button" className="psl-btn psl-btn--secondary" onClick={() => void page.reload()}>
              Reload
            </button>
          )}
        </div>
      )}
      {notice?.kind === 'stale' && (
        <div className="psl-callout psl-callout--warning ws-notice" role="alert">
          <WarningIcon />
          <span>{STEP_TEXT.stale(notice.revision)}</span>
        </div>
      )}
      {(notice?.kind === 'forbidden' || notice?.kind === 'problem' || notice?.kind === 'failed') && (
        <div className="psl-callout psl-callout--problem ws-notice" role="alert">
          <WarningIcon />
          <span>{notice.kind === 'forbidden' ? STEP_TEXT.forbidden : notice.kind === 'problem' ? notice.text : STEP_TEXT.failed}</span>
          {notice.kind === 'failed' && !notice.sends && !open && (
            <button
              type="button"
              className="psl-btn psl-btn--secondary"
              onClick={() => {
                if (last.current?.token === notice.attempt) void run(last.current);
              }}
            >
              Try again
            </button>
          )}
        </div>
      )}
      {page.refreshFailed && (
        <p className="ws-reload">
          <button type="button" className="psl-btn psl-btn--secondary" onClick={() => void page.reload()}>
            Reload this item
          </button>
        </p>
      )}
      <StepRow steps={workspaceSteps}>{(s, describedBy) => control(s, `ws:${s.key}`, undefined, { describedBy })}</StepRow>
      {workspaceSteps.map((s) => form(`ws:${s.key}`))}
      {workspace.sections.map((section) => (
        <SectionView key={section.key} section={section} level={titled ? 3 : 2} controls={sectionControls} />
      ))}
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
      <WorkspaceHeader workspace={workspace} itemTitle={item.title} />
      {writable ? (
        <WorkspaceSteps id={id} item={item} workspace={workspace} page={page} />
      ) : (
        workspace.sections.map((section) => <SectionView key={section.key} section={section} level={titled ? 3 : 2} />)
      )}
    </div>
  );
}
