'use client';

// SCR-36 Month-end checklist, desktop and phone boards. Data comes only from E-MONTH-END (plus the D-MONTH-END-VIEW
// proposal fields); the backend decides access, counts, labels, tones and restriction (INV-ACCESS, INV-RESTRICTED).
import NextLink from 'next/link';
import { useRouter } from 'next/navigation';
import type { MouseEvent } from 'react';

import { AgentAvatar, buttonClass, EmptyState, Link, PageTitle, Table, Tag, Unknown } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import {
  AGENT_NAMES,
  asOfLine,
  cashView,
  countText,
  doneText,
  nextAction,
  periodNames,
  taskEnd,
  taskTag,
  UNKNOWN,
} from './model';
import { MonthEndNoAccess } from './MonthEndStates';
import type { MonthEnd, MonthEndTask } from './proposal';
import { useMonthEnd } from './useMonthEnd';

import './month-end.css';

/** Phone page back link (D-08): browser back when there is history, else the href (PMO-0-4). */
function BackLink() {
  const router = useRouter();
  const back = (event: MouseEvent<HTMLAnchorElement>) => {
    if (window.history.length > 1) {
      event.preventDefault();
      router.back();
    }
  };
  // A plain <a>: the href is the fallback for a fresh tab; the click goes back in history.
  return (
    <a className="monthend-back" href="/my-work" onClick={back}>
      ← Finance
    </a>
  );
}

/** The count strip: task counts and cash, each in a neutral box. Colour is on the number, never a fill (green is for verified outputs). */
function Strip({ body }: { body: MonthEnd }) {
  const cash = cashView(body);
  const cells = [
    { label: 'DONE', value: doneText(body.summary), tone: 'plain' },
    { label: 'WAITING', value: countText(body.summary?.waiting), tone: 'waiting' },
    { label: 'IN PROGRESS', value: countText(body.summary?.in_progress), tone: 'progress' },
  ];
  return (
    <section aria-label="Month-end counts" className="monthend-strip">
      {cells.map((cell) => (
        <div key={cell.label} className="monthend-cell">
          <span className="monthend-cell__label">{cell.label}</span>
          <span className={`monthend-cell__value monthend-cell__value--${cell.tone}`}>{cell.value}</span>
        </div>
      ))}
      <div className="monthend-cell">
        <span className="monthend-cell__label">CASH RECEIVED</span>
        <span className={`monthend-cell__value monthend-cell__value--${cash.unknown ? 'waiting' : 'plain'}`} aria-describedby="monthend-cash-full">
          {cash.text === UNKNOWN ? <Unknown /> : cash.text}
        </span>
        <span id="monthend-cash-full" hidden>
          {cash.description}
        </span>
      </div>
    </section>
  );
}

function TaskEnd({ task, titleId }: { task: MonthEndTask; titleId: string }) {
  const end = taskEnd(task);
  // the SCR-36 board writes a restricted row's end as plain muted text, with no lock (D-93); it never links
  if (end.kind === 'restricted') return <span className="monthend-restricted">{end.text}</span>;
  // the name stays "Open" as drawn; the row's task title is its description, so each link is told apart
  if (end.kind === 'link')
    return (
      <Link href={end.href} aria-describedby={titleId}>
        Open
      </Link>
    );
  return null;
}

function TaskTable({ tasks }: { tasks: MonthEndTask[] }) {
  return (
    <section className="monthend-tasks">
      <Table
        caption="Month-end tasks"
        columns={[
          {
            key: 'task',
            header: 'TASK',
            cell: (task) => (
              <>
                <strong id={`monthend-task-${tasks.indexOf(task)}`}>{task.title ?? task.line}</strong>
                {task.detail && (
                  <>
                    <br />
                    <span className="monthend-detail">{task.detail}</span>
                  </>
                )}
              </>
            ),
          },
          { key: 'where', header: 'WHERE IT IS', cell: (task) => task.where },
          {
            key: 'state',
            header: 'STATE',
            cell: (task) => {
              const tag = taskTag(task);
              return <Tag tone={tag.tone}>{tag.text}</Tag>;
            },
          },
          { key: 'open', header: '', cell: (task) => <TaskEnd task={task} titleId={`monthend-task-${tasks.indexOf(task)}`} /> },
        ]}
        rows={tasks}
        rowKey={(task) => String(tasks.indexOf(task))}
        empty="No month-end tasks."
      />
    </section>
  );
}

function TaskCards({ tasks }: { tasks: MonthEndTask[] }) {
  return (
    <div className="monthend-cards">
      {tasks.map((task, i) => {
        const tag = taskTag(task);
        return (
          <div key={i} className="monthend-card">
            <span className="monthend-card__top">
              <strong>{task.title ?? task.line}</strong>
              <Tag tone={tag.tone}>{tag.text}</Tag>
            </span>
            <span className="monthend-card__where">{task.where}</span>
          </div>
        );
      })}
    </div>
  );
}

function AgentNote({ note }: { note: NonNullable<MonthEnd['agent_note']> }) {
  const agent = AGENT_NAMES[note.agent];
  return (
    <div className="monthend-note">
      <AgentAvatar agent={note.agent} />
      <span className="monthend-note__text">
        <strong>{agent.name}</strong> · {agent.role}
        <br />
        {note.text}
      </span>
    </div>
  );
}

function Board({ body }: { body: MonthEnd }) {
  const names = periodNames(body.period);
  const asOf = asOfLine(body);
  const action = nextAction(body);
  const done = doneText(body.summary);
  const empty = body.tasks.length === 0;
  return (
    <div className="monthend">
      <BackLink />
      <p className="monthend-eyebrow">FINANCE / MONTH-END</p>
      <div className="monthend-head">
        <PageTitle size={34} phoneSize={22} titleClassName="monthend-title">
          Month-end · <span className="monthend-wide">{names?.long ?? body.period}</span>
          <span className="monthend-narrow">{names?.short ?? body.period}</span>
        </PageTitle>
        {asOf && <span className="monthend-asof">{asOf}</span>}
      </div>
      <span className="monthend-summary">
        <strong>{done}</strong> done · {countText(body.summary?.waiting)} waiting
      </span>
      <Strip body={body} />
      <div className="monthend-row">
        {empty ? (
          <EmptyState className="monthend-empty" title={`No month-end tasks you can see for ${names?.long ?? body.period}.`}>
            Tasks appear here when month-end work you can see starts.
          </EmptyState>
        ) : (
          <TaskTable tasks={body.tasks} />
        )}
        {(body.agent_note || action) && (
          <aside className="monthend-aside">
            {body.agent_note && <AgentNote note={body.agent_note} />}
            {action && (
              <NextLink className={`${buttonClass('primary', 'lg')} monthend-action`} href={action.href}>
                {action.label}
              </NextLink>
            )}
          </aside>
        )}
      </div>
      {!empty && <TaskCards tasks={body.tasks} />}
      {action && (
        <div className="monthend-bar">
          <NextLink className={`${buttonClass('primary', 'lg')} monthend-action`} href={action.href}>
            {action.label}
          </NextLink>
        </div>
      )}
    </div>
  );
}

export function MonthEndView({ period }: { period: string }) {
  const { state, retry } = useMonthEnd(period);

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={`/finance/month-end?period=${period}`} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <MonthEndNoAccess />;
    return (
      <WorkErrorCard
        message="We couldn’t load the month-end checklist. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }
  return <Board body={state.body} />;
}
