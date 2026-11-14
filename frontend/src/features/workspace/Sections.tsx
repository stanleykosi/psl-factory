'use client';

// PROPOSAL (D-LINE-WORKSPACE, contract mock only): one renderer per section kind. Everything drawn comes from the
// section as returned; an absent field draws nothing. INV-RESTRICTED: a restricted section or item draws its label
// and none of its rows, cites, detail or money. INV-UNKNOWN: an unknown or missing amount or date reads Unknown.
import Link from 'next/link';
import { useId, type ReactNode } from 'react';

import { isAppPath } from '@/features/work-item/presentation';
import { formatWat } from '@/features/work-item/labels';

import {
  agentName,
  asOfLine,
  dateText,
  moneyText,
  RECEIPT_WORDS,
  refPath,
  refText,
  SEVERITY_WORDS,
  STATUS_WORDS,
  tagClass,
  word,
  WS_TEXT,
  type Cell,
  type Column,
  type DateValue,
  type Item,
  type Money,
  type Ref,
  type Section,
} from './labels';

/** Per-item controls the step layer adds (Part B); the read-only renderer draws none. */
export type ItemControls = {
  /** The item's own step controls (applies_to `item`). */
  item?: (section: Section, item: Item) => ReactNode;
  /** The checkbox for an `items` step. */
  select?: (section: Section, item: Item) => ReactNode;
  /** The `items` step button under the section. */
  foot?: (section: Section) => ReactNode;
};

export function Unknown() {
  return <span className="psl-unknown">{WS_TEXT.unknown}</span>;
}

function MoneyValue({ money }: { money: Money }) {
  const text = moneyText(money);
  return text === null ? <Unknown /> : <span className="psl-amount">{text}</span>;
}

function DateText({ value }: { value: DateValue }) {
  const text = dateText(value);
  return text === null ? <Unknown /> : <span>{text}</span>;
}

/** A cited record: a link only for an app path, else its words. */
function RefView({ value }: { value: Ref }) {
  const text = refText(value);
  const href = refPath(value);
  if (!text) return null;
  return href && isAppPath(href) ? (
    <Link className="ws-ref" href={href}>
      {text}
    </Link>
  ) : (
    <span className="ws-ref">{text}</span>
  );
}

/** Cites as the boards draw them: the cite label ("2 RECORDS") stands for the list, which stays for screen readers. */
function Cites({ item }: { item: Item }) {
  const cites = (item.cites ?? []).filter((c) => refText(c));
  if (!item.cite_label && cites.length === 0) return null;
  if (item.cite_label) {
    return (
      <span className="ws-cites">
        <span className="ws-cite">{item.cite_label}</span>
        {cites.length > 0 && <span className="work-sr"> ({cites.map(refText).join(', ')})</span>}
      </span>
    );
  }
  return (
    <span className="ws-cites">
      {cites.map((c, i) => (
        <span key={i} className="ws-cite">
          <RefView value={c} />
        </span>
      ))}
    </span>
  );
}

const Detail = ({ text }: { text?: string }) => (text ? <span className="ws-detail">{text}</span> : null);

function Restricted({ label }: { label?: string }) {
  return <p className="ws-restricted">{label ?? WS_TEXT.restricted}</p>;
}

/** One row: what it is on the left, its state and cites on the right, as the boards' section lists. */
function Row({ item, controls, section, main, end }: { item: Item; controls?: ItemControls; section: Section; main: ReactNode; end?: ReactNode }) {
  if (item.restricted) {
    return (
      <li className="ws-row ws-row--restricted">
        <span className="ws-row__main">{WS_TEXT.restricted}</span>
      </li>
    );
  }
  const select = controls?.select?.(section, item);
  const steps = controls?.item?.(section, item);
  return (
    <li className="ws-row">
      {select}
      <span className="ws-row__main">{main}</span>
      {end && <span className="ws-row__end">{end}</span>}
      {steps && <span className="ws-row__steps">{steps}</span>}
    </li>
  );
}

const Lead = ({ item }: { item: Item }) =>
  item.label && item.text ? (
    <>
      <strong>{item.label}</strong> · {item.text}
    </>
  ) : (
    <>{item.text ?? item.label}</>
  );

function StatusWord({ value, kind }: { value: string; kind: 'status' | 'receipt' | 'severity' }) {
  const words: Record<string, string> = kind === 'status' ? STATUS_WORDS : kind === 'receipt' ? RECEIPT_WORDS : SEVERITY_WORDS;
  return <span className={`ws-word ws-word--${kind}-${value}`}>{word(words, value)}</span>;
}

function FactsList({ section }: { section: Section }) {
  return (
    <dl className="ws-facts">
      {section.items.map((item) => (
        <div key={item.id} className="ws-fact">
          {item.restricted ? (
            <dd>{WS_TEXT.restricted}</dd>
          ) : (
            <>
              <dt>{item.label ?? item.text}</dt>
              <dd>{item.money ? <MoneyValue money={item.money} /> : item.value !== undefined ? item.value : <Unknown />}</dd>
            </>
          )}
        </div>
      ))}
    </dl>
  );
}

function CellValue({ cell, column }: { cell: Cell | undefined; column: Column }) {
  if (!cell) return null;
  if (cell.restricted) return <>{WS_TEXT.restricted}</>;
  const kind = column.kind ?? 'text';
  let value: ReactNode = cell.text;
  if (kind === 'money') value = cell.money ? <MoneyValue money={cell.money} /> : <Unknown />;
  else if (kind === 'date') value = cell.date ? <DateText value={cell.date} /> : <Unknown />;
  else if (kind === 'tag' && cell.tag) value = <span className={tagClass(cell.tag.tone)}>{cell.tag.label}</span>;
  else if (kind === 'reference' && cell.link && !cell.text) return <RefView value={cell.link} />;
  return (
    <>
      {value}
      {cell.link && (kind !== 'reference' || cell.text) && (
        <>
          {' '}
          <span className="ws-cite">
            <RefView value={cell.link} />
          </span>
        </>
      )}
    </>
  );
}

function Table({ section, controls }: { section: Section; controls?: ItemControls }) {
  const columns = section.columns ?? [];
  const selectable = controls?.select !== undefined;
  const stepCol = controls?.item !== undefined && section.items.some((i) => controls.item?.(section, i));
  return (
    // The frame scrolls sideways on phones, so it takes focus for keyboard scrolling (WCAG 2.1.1).
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div className="psl-tablewrap ws-tablewrap" tabIndex={0} role="region" aria-label={section.title ? `Table: ${section.title}` : 'Table'}>
      <table className="psl-table ws-table">
        <thead>
          <tr>
            {selectable && (
              <th className="psl-check-cell">
                <span className="work-sr">Select</span>
              </th>
            )}
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.kind === 'money' || c.kind === 'integer' ? 'num' : undefined}>
                {c.label}
              </th>
            ))}
            {stepCol && (
              <th>
                <span className="work-sr">Steps</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {section.items.map((item) =>
            item.restricted ? (
              <tr key={item.id}>
                <td colSpan={columns.length + (selectable ? 1 : 0) + (stepCol ? 1 : 0)}>{WS_TEXT.restricted}</td>
              </tr>
            ) : (
              <tr key={item.id}>
                {selectable && <td className="psl-check-cell">{controls?.select?.(section, item)}</td>}
                {columns.map((c) => (
                  <td key={c.key} className={c.kind === 'money' || c.kind === 'integer' ? 'num' : c.kind === 'reference' ? 'psl-mono' : undefined}>
                    <CellValue cell={item.cells?.find((cell) => cell.column === c.key)} column={c} />
                  </td>
                ))}
                {stepCol && <td>{controls?.item?.(section, item)}</td>}
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}

function Owner({ item }: { item: Item }) {
  if (!item.owner && !item.held_by) return null;
  return (
    <span className="ws-detail">
      {item.owner && <>Owner: {item.owner.role ? `${item.owner.name} (${item.owner.role})` : item.owner.name}</>}
      {item.owner && item.held_by && ' · '}
      {item.held_by && <>Held by {item.held_by.is_you ? WS_TEXT.you : item.held_by.name}</>}
    </span>
  );
}

function Items({ section, controls }: { section: Section; controls?: ItemControls }) {
  const row = (item: Item, main: ReactNode, end?: ReactNode) => <Row key={item.id} item={item} section={section} controls={controls} main={main} end={end} />;
  return (
    <ul className={`ws-rows ws-rows--${section.kind}`}>
      {section.items.map((item) => {
        switch (section.kind) {
          case 'checklist':
            return row(
              item,
              <>
                <span className={`ws-mark ws-mark--${item.status ?? 'none'}`} aria-hidden="true" />
                <span className="ws-stack">
                  <span>
                    <Lead item={item} />
                    {item.detail && <> · {item.detail}</>}
                  </span>
                  <Owner item={item} />
                </span>
              </>,
              (item.status || item.due) && (
                <>
                  {item.status && <StatusWord value={item.status} kind="status" />}
                  {item.status && item.due && ' · '}
                  {item.due && (
                    <span className="ws-due">
                      <span className="work-sr">Due </span>
                      <DateText value={item.due} />
                    </span>
                  )}
                </>
              ),
            );
          case 'findings':
            return row(
              item,
              <span className="ws-stack">
                <span>
                  <Lead item={item} />
                </span>
                <Detail text={item.detail} />
              </span>,
              <>
                {item.severity && <StatusWord value={item.severity} kind="severity" />}
                <Cites item={item} />
              </>,
            );
          case 'suggestions':
            return row(
              item,
              <span className="ws-stack">
                <span>
                  <Lead item={item} />
                </span>
                <Detail text={item.detail} />
                {item.agent && <span className="ws-detail">Suggested by {agentName(item.agent)}</span>}
              </span>,
              <>
                {item.tag && <span className={tagClass(item.tag.tone)}>{item.tag.label}</span>}
                <Cites item={item} />
              </>,
            );
          case 'recipients':
            return row(
              item,
              <span className="ws-stack">
                <span>{item.text ?? item.label}</span>
                {item.channel && <span className="ws-detail">{item.channel}</span>}
              </span>,
              <>
                {item.receipt && <StatusWord value={item.receipt} kind="receipt" />}
                {item.at && <time dateTime={item.at}> {formatWat(item.at)}</time>}
              </>,
            );
          case 'figures':
            return row(
              item,
              <span className="ws-stack">
                <span>{item.label ?? item.text}</span>
                <Detail text={item.detail} />
              </span>,
              item.money ? <MoneyValue money={item.money} /> : item.value !== undefined ? <span className="ws-value">{item.value}</span> : <Unknown />,
            );
          case 'timeline':
            return row(
              item,
              <span className="ws-stack">
                <span>
                  <Lead item={item} />
                </span>
                {(item.agent || item.owner) && <span className="ws-detail">{item.agent ? agentName(item.agent) : item.owner?.name}</span>}
                <Detail text={item.detail} />
              </span>,
              item.at ? <time dateTime={item.at}>{formatWat(item.at)}</time> : undefined,
            );
          default:
            // `text` and any kind the frame does not know: the words and their cites
            return row(
              item,
              <span className="ws-stack">
                <span>
                  <Lead item={item} />
                </span>
                <Detail text={item.detail} />
              </span>,
              <Cites item={item} />,
            );
        }
      })}
    </ul>
  );
}

/** Filters, total and Show more are drawn when returned, and inert: no section-page read exists in the contract. */
function Paging({ section, position }: { section: Section; position: 'top' | 'bottom' }) {
  const id = useId();
  const filters = section.filters ?? [];
  if (position === 'top') {
    if (filters.length === 0 && section.total === undefined) return null;
    return (
      <div className="ws-filters" role="group" aria-label={`${section.title ?? 'Section'} filters`} aria-describedby={`${id}-note`}>
        {filters.length > 0 && (
          <>
            <button type="button" className="psl-btn psl-btn--secondary" disabled>
              {WS_TEXT.filter}
            </button>
            {filters.map((f) => (
              <button key={f.value} type="button" className="psl-chip ws-chip" disabled>
                {f.label}
              </button>
            ))}
          </>
        )}
        {section.total !== undefined && (
          <span className="ws-count psl-mono">
            {section.items.length} of {section.total}
          </span>
        )}
        <span id={`${id}-note`} className="ws-detail">
          {WS_TEXT.noMore}
        </span>
      </div>
    );
  }
  if (!section.next_cursor) return null;
  return (
    <div className="ws-more">
      <button type="button" className="psl-btn psl-btn--secondary" disabled aria-describedby={`${id}-more`}>
        {WS_TEXT.showMore}
      </button>
      <span id={`${id}-more`} className="ws-detail">
        {WS_TEXT.noMore}
      </span>
    </div>
  );
}

export function SectionView({ section, level, controls }: { section: Section; level: 2 | 3; controls?: ItemControls }) {
  const headId = useId();
  const Heading = level === 2 ? 'h2' : 'h3';
  const restricted = section.restricted === true;
  const empty = !restricted && section.items.length === 0;
  return (
    <section className={`psl-panel ws-section ws-section--${section.kind}`} aria-labelledby={section.title ? headId : undefined}>
      {section.title && (
        <Heading id={headId} className="psl-panel__head ws-section__head">
          {section.title}
        </Heading>
      )}
      <div className="psl-panel__body ws-section__body">
        {restricted ? (
          <Restricted label={section.restricted_label} />
        ) : (
          <>
            {(section.as_of || section.coverage || section.agent) && (
              <p className="ws-meta">
                {section.agent && <span>{agentName(section.agent)}</span>}
                {section.as_of && <time dateTime={section.as_of}>{asOfLine(section.as_of)}</time>}
                {section.coverage && <span>{section.coverage}</span>}
              </p>
            )}
            {section.note && <p className="ws-note">{section.note}</p>}
            <Paging section={section} position="top" />
            {empty ? (
              <p className="ws-empty">{WS_TEXT.empty}</p>
            ) : section.kind === 'facts' ? (
              <FactsList section={section} />
            ) : section.kind === 'table' ? (
              <Table section={section} controls={controls} />
            ) : (
              <Items section={section} controls={controls} />
            )}
            <Paging section={section} position="bottom" />
            {!empty && controls?.foot?.(section)}
          </>
        )}
      </div>
    </section>
  );
}
