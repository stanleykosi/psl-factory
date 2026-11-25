'use client';

// SCR-36 Month-end checklist, desktop and phone boards. Data comes only from the live GET /month-end; the backend decides
// access, counts, labels, states and which rows exist (INV-ACCESS). The page shows what is returned and adds nothing up.
import { useRouter } from 'next/navigation';
import type { MouseEvent } from 'react';

import { Button, EmptyState, formatDayTime, PageTitle, Table, Tag, Unknown } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { asOfLine, cashView, countText, periodNames, taskHref, taskTag, UNKNOWN } from './model';
import { MonthEndNoAccess } from './MonthEndStates';
import type { MonthEnd, MonthEndWork } from './types';
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
    { label: 'DONE', value: countText(body.counts?.done), tone: 'plain' },
    { label: 'WAITING', value: countText(body.counts?.waiting), tone: 'waiting' },
    { label: 'IN PROGRESS', value: countText(body.counts?.in_progress), tone: 'progress' },
    { label: 'STOPPED', value: countText(body.counts?.stopped), tone: 'plain' },
  ];
  return (
    <section aria-label="Month-end counts" className="monthend-strip">
      {cells.map((cell) => (
        <div key={cell.label} className="monthend-cell">
          <span className="monthend-cell__label">{cell.label}</span>
          <span className={`monthend-cell__value monthend-cell__value--${cell.tone}`}>{cell.value === UNKNOWN ? <Unknown /> : cell.value}</span>
        </div>
      ))}
      <div className="monthend-cell">
        <span className="monthend-cell__label">CASH RECEIVED</span>
        <span className={`monthend-cell__value monthend-cell__value--${cash.cellUnknown ? 'waiting' : 'plain'}`}>
          {cash.cell === UNKNOWN ? <Unknown /> : cash.cell}
        </span>
      </div>
    </section>
  );
}

/** One line per cash row when the cell reads "By project"; an unavailable workspace reads Unknown, never 0. */
function CashLines({ body }: { body: MonthEnd }) {
  const cash = cashView(body);
  if (cash.lines.length === 0 && !cash.more) return null;
  return (
    <ul className="monthend-cash" aria-label="Cash received by project">
      {cash.lines.map((line) => (
        <li key={line.key}>
          <span>{line.workspace}</span>
          <strong>{line.unknown ? <Unknown /> : line.text}</strong>
          {line.basis && <span className="monthend-cash__basis">{line.basis}</span>}
        </li>
      ))}
      {cash.more && <li className="monthend-cash__more">More projects are not shown here</li>}
    </ul>
  );
}

/** The title links to the returned url only when it is a path on this site. */
function TaskTitle({ task, id }: { task: MonthEndWork; id: string }) {
  const href = taskHref(task.url);
  return href ? (
    <a id={id} className="monthend-tasklink" href={href}>
      {task.title}
    </a>
  ) : (
    <strong id={id}>{task.title}</strong>
  );
}

function TaskTable({ tasks }: { tasks: MonthEndWork[] }) {
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
                <TaskTitle task={task} id={`monthend-task-${tasks.indexOf(task)}`} />
                <br />
                <span className="monthend-detail">{task.workspace}</span>
              </>
            ),
          },
          {
            key: 'state',
            header: 'STATE',
            cell: (task) => {
              const tag = taskTag(task);
              return <Tag tone={tag.tone}>{tag.text}</Tag>;
            },
          },
          { key: 'at', header: 'UPDATED', cell: (task) => formatDayTime(task.at) },
        ]}
        rows={tasks}
        rowKey={(task) => String(tasks.indexOf(task))}
        empty="No month-end tasks."
      />
    </section>
  );
}

function TaskCards({ tasks }: { tasks: MonthEndWork[] }) {
  return (
    <div className="monthend-cards">
      {tasks.map((task, i) => {
        const tag = taskTag(task);
        return (
          <div key={i} className="monthend-card">
            <span className="monthend-card__top">
              <TaskTitle task={task} id={`monthend-card-${i}`} />
              <Tag tone={tag.tone}>{tag.text}</Tag>
            </span>
            <span className="monthend-card__where">
              {task.workspace} · {formatDayTime(task.at)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Board({ body, more, onMore }: { body: MonthEnd; more: 'idle' | 'loading' | 'error'; onMore: () => void }) {
  const names = periodNames(body.month);
  const asOf = asOfLine(body.as_of);
  const empty = body.work.length === 0;
  return (
    <div className="monthend">
      <BackLink />
      <p className="monthend-eyebrow">FINANCE / MONTH-END</p>
      <div className="monthend-head">
        <PageTitle size={34} phoneSize={22} titleClassName="monthend-title">
          Month-end · <span className="monthend-wide">{names?.long ?? body.month}</span>
          <span className="monthend-narrow">{names?.short ?? body.month}</span>
        </PageTitle>
        {asOf && <span className="monthend-asof">{asOf}</span>}
      </div>
      <span className="monthend-summary">
        <strong>{countText(body.counts?.done)}</strong> done · {countText(body.counts?.waiting)} waiting
      </span>
      <Strip body={body} />
      <CashLines body={body} />
      <div className="monthend-row">
        {empty ? (
          <EmptyState className="monthend-empty" title="Nothing to close this month">
            Tasks appear here when month-end work you can see starts.
          </EmptyState>
        ) : (
          <TaskTable tasks={body.work} />
        )}
      </div>
      {!empty && <TaskCards tasks={body.work} />}
      {body.next_page !== null && (
        <div className="monthend-more">
          {more === 'error' && <p role="alert">We couldn’t load more tasks. The ones above are still here.</p>}
          <Button kind="secondary" disabled={more === 'loading'} onClick={onMore}>
            {more === 'error' ? 'Try again' : 'Show more'}
          </Button>
        </div>
      )}
    </div>
  );
}

export function MonthEndView({ period }: { period: string }) {
  const { state, more, retry, showMore } = useMonthEnd(period);

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
  return <Board body={state.body} more={more} onMore={() => void showMore()} />;
}
