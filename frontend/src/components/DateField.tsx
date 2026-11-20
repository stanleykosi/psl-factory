'use client';

// DateField (design/system/project/components/DateField): dates read "17 Nov 2026". People type a date
// (17/11/2026 or 17 Nov 2026) or pick it from the calendar. The calendar marks today with an outline, the chosen
// day filled ink, and days that are not allowed struck through; a typed day that is not allowed shows its reason.
// Calendar keys: arrows move a day or a week, Home/End the start or end of the week, Page Up/Down a month, Enter
// or Space chooses, Esc closes and returns focus to the calendar button. With `time` a 24-hour time sits beside the
// date and the value is "2026-11-17T14:30"; it stays '' until both are given.
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react';

import { FieldLabel, FieldMessage, useFieldIds, type FieldText } from './Field';
import { IconButton } from './IconButton';
import { cx, useOutsidePress } from './internal';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = [
  ['M', 'Monday'],
  ['T', 'Tuesday'],
  ['W', 'Wednesday'],
  ['T', 'Thursday'],
  ['F', 'Friday'],
  ['S', 'Saturday'],
  ['S', 'Sunday'],
];

type Ymd = { y: number; m: number; d: number };

const pad = (n: number) => String(n).padStart(2, '0');
const toIso = ({ y, m, d }: Ymd) => `${y}-${pad(m + 1)}-${pad(d)}`;
const daysIn = (y: number, m: number) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate();

function fromIso(iso: string): Ymd | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  return { y: Number(match[1]), m: Number(match[2]) - 1, d: Number(match[3]) };
}

function shift({ y, m, d }: Ymd, days: number): Ymd {
  const at = new Date(Date.UTC(y, m, d + days));
  return { y: at.getUTCFullYear(), m: at.getUTCMonth(), d: at.getUTCDate() };
}

function shiftMonth({ y, m, d }: Ymd, months: number): Ymd {
  const first = new Date(Date.UTC(y, m + months, 1));
  const ny = first.getUTCFullYear();
  const nm = first.getUTCMonth();
  return { y: ny, m: nm, d: Math.min(d, daysIn(ny, nm)) };
}

/** "17 Nov 2026" for an ISO date; '' for '' (the field's text, not a display value). */
function isoText(iso: string): string {
  const ymd = fromIso(iso);
  return ymd ? `${ymd.d} ${MONTHS[ymd.m]} ${ymd.y}` : '';
}

/** Reads 17/11/2026, 17 Nov 2026 or 17 November 2026; says what is wrong otherwise. */
export function parseDate(text: string): { iso: string } | { error: string } {
  const clean = text.trim();
  let y: number;
  let m: number;
  let d: number;
  const numeric = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(clean);
  const written = /^(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})$/.exec(clean);
  if (numeric) {
    [d, m, y] = [Number(numeric[1]), Number(numeric[2]) - 1, Number(numeric[3])];
    if (m < 0 || m > 11) return { error: 'Write the date as 17 Nov 2026.' };
  } else if (written) {
    const word = written[2].toLowerCase();
    m = MONTH_NAMES.findIndex((name) => name.toLowerCase() === word || name.slice(0, 3).toLowerCase() === word);
    if (m < 0) return { error: 'Write the date as 17 Nov 2026.' };
    [d, y] = [Number(written[1]), Number(written[3])];
  } else {
    return { error: 'Write the date as 17 Nov 2026.' };
  }
  const days = daysIn(y, m);
  if (d < 1 || d > days) return { error: `${MONTH_NAMES[m]} has ${days} days.` };
  return { iso: toIso({ y, m, d }) };
}

function todayYmd(): Ymd {
  const now = new Date();
  return { y: now.getFullYear(), m: now.getMonth(), d: now.getDate() };
}

export type DateFieldProps = FieldText & {
  /** ISO date (2026-11-17), or '' when empty or not a valid date. */
  value: string;
  onChange: (iso: string) => void;
  /** Why a day cannot be chosen, or undefined when it can ("Receipts can't be before the milestone"). */
  unavailable?: (iso: string) => string | undefined;
  /** ISO date marked as today; the device's date by default. */
  today?: string;
  /** Also ask for the time of day; the value is then "2026-11-17T14:30". */
  time?: boolean;
  /** The label is read but not drawn, where the layout already names the field. */
  hideLabel?: boolean;
  disabled?: boolean;
  id?: string;
  fieldClassName?: string;
};

export function DateField({ label, optional, hint, error, value: whole, onChange: emit, unavailable, today, time = false, hideLabel = false, disabled = false, id, fieldClassName }: DateFieldProps) {
  // With a time, the date and the time are kept apart until both are there; the value is '' before that.
  const [draftDate, setDraftDate] = useState('');
  const [draftTime, setDraftTime] = useState('');
  const value = time ? (whole ? whole.slice(0, 10) : draftDate) : whole;
  const clock = time ? (whole ? whole.slice(11, 16) : draftTime) : '';
  const onChange = (iso: string) => {
    if (!time) return emit(iso);
    setDraftDate(iso);
    emit(iso && clock ? `${iso}T${clock}` : '');
  };
  const [text, setText] = useState(() => isoText(value));
  const [shownFor, setShownFor] = useState(value);
  const [typedError, setTypedError] = useState<string | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const shown = error ?? typedError;
  const ids = useFieldIds(id, { hint, error: shown });
  const openerRef = useRef<HTMLButtonElement>(null);
  const boxRef = useRef<HTMLSpanElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  // A value set from outside (a reset, a loaded record) replaces what is written.
  if (value !== shownFor) {
    setShownFor(value);
    if (value !== '' || typedError === undefined) setText(isoText(value));
  }

  useOutsidePress([boxRef, popRef], open, () => setOpen(false));

  function commit(raw: string) {
    if (raw.trim() === '') {
      setTypedError(undefined);
      if (value !== '') onChange('');
      return;
    }
    const parsed = parseDate(raw);
    const reason = 'iso' in parsed ? unavailable?.(parsed.iso) : parsed.error;
    if ('iso' in parsed && !reason) {
      setTypedError(undefined);
      setText(isoText(parsed.iso));
      if (parsed.iso !== value) onChange(parsed.iso);
      return;
    }
    setTypedError(reason);
    if (value !== '') onChange('');
  }

  function pick(iso: string) {
    setTypedError(undefined);
    setText(isoText(iso));
    setOpen(false);
    openerRef.current?.focus();
    if (iso !== value) onChange(iso);
  }

  const anchor = (
    <div className="cmp-anchor">
      <span ref={boxRef} className={cx('psl-input cmp-wrapped', shown && 'is-error', disabled && 'is-disabled')}>
        <input
          id={ids.control}
          type="text"
          inputMode="text"
          autoComplete="off"
          placeholder="DD Mmm YYYY"
          value={text}
          disabled={disabled}
          aria-invalid={shown ? true : undefined}
          aria-describedby={ids.describedBy}
          onChange={(event) => setText(event.target.value)}
          onBlur={(event) => commit(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commit(event.currentTarget.value);
          }}
        />
        <IconButton
          ref={openerRef}
          bare
          icon="cal"
          label="Choose a date"
          className="cmp-inputbtn"
          disabled={disabled}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        />
      </span>
      {open && (
        <Calendar
          popRef={popRef}
          value={value}
          today={today ?? toIso(todayYmd())}
          unavailable={unavailable}
          onPick={pick}
          onClose={() => {
            setOpen(false);
            openerRef.current?.focus();
          }}
        />
      )}
    </div>
  );
  const clockInput = time && (
    <input
      type="time"
      className={cx('psl-input cmp-time', shown && 'is-error', disabled && 'is-disabled')}
      aria-label={typeof label === 'string' ? `${label}, time` : 'Time'}
      value={clock}
      disabled={disabled}
      onChange={(event) => {
        setDraftTime(event.target.value);
        emit(value && event.target.value ? `${value}T${event.target.value}` : '');
      }}
    />
  );

  return (
    <div className={cx('psl-field', fieldClassName)}>
      <FieldLabel htmlFor={ids.control} id={ids.label} label={label} optional={optional} hidden={hideLabel} />
      {time ? (
        <div className="cmp-datetime">
          {anchor}
          {clockInput}
        </div>
      ) : (
        anchor
      )}
      <FieldMessage id={ids.message} hint={hint} error={shown} />
    </div>
  );
}

function Calendar({ popRef, value, today, unavailable, onPick, onClose }: {
  popRef: RefObject<HTMLDivElement | null>;
  value: string;
  today: string;
  unavailable?: (iso: string) => string | undefined;
  onPick: (iso: string) => void;
  onClose: () => void;
}) {
  const [focus, setFocus] = useState<Ymd>(() => fromIso(value) ?? fromIso(today) ?? todayYmd());
  const gridRef = useRef<HTMLDivElement>(null);
  const focusIso = toIso(focus);

  useEffect(() => {
    gridRef.current?.querySelector<HTMLElement>(`[data-iso="${focusIso}"]`)?.focus();
  }, [focusIso]);

  // Monday-first weeks covering the month, with the neighbouring months' days marked out.
  const first = { y: focus.y, m: focus.m, d: 1 };
  const lead = (new Date(Date.UTC(focus.y, focus.m, 1)).getUTCDay() + 6) % 7;
  const total = Math.ceil((lead + daysIn(focus.y, focus.m)) / 7) * 7;
  const days = Array.from({ length: total }, (_, i) => shift(first, i - lead));
  const weeks = Array.from({ length: total / 7 }, (_, w) => days.slice(w * 7, w * 7 + 7));

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    const weekday = (new Date(Date.UTC(focus.y, focus.m, focus.d)).getUTCDay() + 6) % 7;
    const moves: Record<string, () => Ymd> = {
      ArrowLeft: () => shift(focus, -1),
      ArrowRight: () => shift(focus, 1),
      ArrowUp: () => shift(focus, -7),
      ArrowDown: () => shift(focus, 7),
      Home: () => shift(focus, -weekday),
      End: () => shift(focus, 6 - weekday),
      PageUp: () => shiftMonth(focus, -1),
      PageDown: () => shiftMonth(focus, 1),
    };
    if (moves[event.key]) {
      event.preventDefault();
      setFocus(moves[event.key]());
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
    }
  }

  function choose(iso: string) {
    if (!unavailable?.(iso)) onPick(iso);
  }

  return (
    <div ref={popRef} className="psl-pop psl-cal cmp-pop" role="dialog" aria-label="Choose a date">
      <div className="psl-cal__head">
        <IconButton bare icon="back" label="Previous month" onClick={() => setFocus(shiftMonth(focus, -1))} />
        <span aria-live="polite">
          {MONTH_NAMES[focus.m]} {focus.y}
        </span>
        <IconButton bare icon="chev-r" label="Next month" onClick={() => setFocus(shiftMonth(focus, 1))} />
      </div>
      <div ref={gridRef} className="psl-cal__grid" role="grid" aria-label={`${MONTH_NAMES[focus.m]} ${focus.y}`} tabIndex={-1} onKeyDown={keys}>
        <div role="row" className="cmp-cal__row">
          {WEEKDAYS.map(([short, long]) => (
            <b key={long} role="columnheader" aria-label={long}>
              {short}
            </b>
          ))}
        </div>
        {weeks.map((week) => (
          <div role="row" className="cmp-cal__row" key={toIso(week[0])}>
            {week.map((day) => {
              const iso = toIso(day);
              const reason = unavailable?.(iso);
              return (
                <span
                  key={iso}
                  role="gridcell"
                  data-iso={iso}
                  tabIndex={iso === focusIso ? 0 : -1}
                  className={cx('psl-day', iso === today && 'is-today', day.m !== focus.m && 'is-out')}
                  aria-selected={iso === value}
                  aria-disabled={reason ? true : undefined}
                  aria-label={`${day.d} ${MONTH_NAMES[day.m]} ${day.y}${iso === today ? ', today' : ''}${reason ? `, ${reason}` : ''}`}
                  onClick={() => choose(iso)}
                  onKeyDown={(event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    event.preventDefault();
                    choose(iso);
                  }}
                >
                  {day.d}
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
