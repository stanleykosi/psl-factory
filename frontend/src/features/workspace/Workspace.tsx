'use client';

// PROPOSAL (D-LINE-WORKSPACE, contract mock only): the line workspace on the work item's Overview, drawn from
// E-WORK-ITEM `workspace` alone. The header, the sections in returned order and (Part B) the steps exactly as
// returned. Nothing here reads /me or decides who may act; the backend composes every section and step.
import type { WorkItem } from '@/features/work-item/labels';

import { agentName, tagClass, type Workspace as WorkspaceData } from './labels';
import { SectionView, type ItemControls } from './Sections';

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

export function WorkspaceSections({ workspace, level, controls }: { workspace: WorkspaceData; level: 2 | 3; controls?: ItemControls }) {
  return (
    <>
      {workspace.sections.map((section) => (
        <SectionView key={section.key} section={section} level={level} controls={controls} />
      ))}
    </>
  );
}

export function Workspace({ item }: { id: string; item: WorkItem }) {
  const workspace = item.workspace;
  if (!workspace) return null;
  const titled = workspace.title !== undefined && workspace.title !== item.title;
  return (
    <div className="ws" data-line={workspace.line_key}>
      <WorkspaceHeader workspace={workspace} itemTitle={item.title} />
      <WorkspaceSections workspace={workspace} level={titled ? 3 : 2} />
    </div>
  );
}
