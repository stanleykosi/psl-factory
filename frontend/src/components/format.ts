// The formats in one place. Where a board draws a date or time, the screen uses that board's format (D-93):
// "12 Nov 16:40" (formatDayTime), "Mon 10 Nov 14:05" (formatWeekdayDayTime), "10:47" (formatClock), "14:30 WAT"
// (formatTime), "12 Nov" or "01 Oct" (formatDayMonth). Where no board draws one: dates "17 Nov 2026" (formatDate) and
// "17 Nov 2026 · 14:30 WAT" (formatDateTime). All times are 24-hour in Africa/Lagos. Amounts "₦4,250,000.00" (two
// decimals, never rounded), from a decimal string. A value that is missing is "Unknown", never 0 and never blank.

export const UNKNOWN = 'Unknown';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const LAGOS = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Lagos',
  weekday: 'short',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function lagosParts(value: string | Date): Record<string, string> | null {
  const at = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(at.getTime())) return null;
  return Object.fromEntries(LAGOS.formatToParts(at).map((p) => [p.type, p.value]));
}

type When = string | Date | null | undefined;

const CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A timestamp's WAT parts; null for a missing or unreadable value, and for a calendar date (it has no time). */
function timeParts(value: When): Record<string, string> | null {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string' && CALENDAR_DATE.test(value)) return null;
  return lagosParts(value);
}

/** "17 Nov 2026". A calendar date (2026-11-17) is read as written; a timestamp is read in WAT. */
export function formatDate(value: When): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  if (typeof value === 'string') {
    const day = CALENDAR_DATE.exec(value);
    if (day) return `${Number(day[3])} ${MONTHS[Number(day[2]) - 1]} ${day[1]}`;
  }
  const parts = lagosParts(value);
  return parts ? `${Number(parts.day)} ${MONTHS[Number(parts.month) - 1]} ${parts.year}` : UNKNOWN;
}

/** "14:30 WAT". Unknown for a calendar date, which has no time. */
export function formatTime(value: When): string {
  const parts = timeParts(value);
  return parts ? `${parts.hour}:${parts.minute} WAT` : UNKNOWN;
}

/** "10:47": the time alone, where a board writes it without WAT ("YOU APPROVED · 10:47"). */
export function formatClock(value: When): string {
  const parts = timeParts(value);
  return parts ? `${parts.hour}:${parts.minute}` : UNKNOWN;
}

/** "12 Nov", "01 Oct": the day (two digits, as the boards write it) and month, where a board leaves out the year. */
export function formatDayMonth(value: When): string {
  const date = formatDate(value);
  if (date === UNKNOWN) return UNKNOWN;
  const [day, month] = date.split(' ');
  return `${day.padStart(2, '0')} ${month}`;
}

/** "12 Nov 16:40", "03 Dec 10:30": what the work item, decision, alert and response boards write for a moment. */
export function formatDayTime(value: When): string {
  const parts = timeParts(value);
  return parts ? `${parts.day.padStart(2, '0')} ${MONTHS[Number(parts.month) - 1]} ${parts.hour}:${parts.minute}` : UNKNOWN;
}

/** "Mon 10 Nov 14:05": the work item header's started line. */
export function formatWeekdayDayTime(value: When): string {
  const parts = timeParts(value);
  return parts ? `${parts.weekday} ${formatDayTime(value)}` : UNKNOWN;
}

/** "17 Nov 2026 · 14:30 WAT", for screens whose boards draw no date; a calendar date alone is "17 Nov 2026". */
export function formatDateTime(value: When): string {
  const date = formatDate(value);
  if (date === UNKNOWN) return UNKNOWN;
  return timeParts(value) ? `${date} · ${formatTime(value)}` : date;
}

/** "4250000.5" → "4,250,000.5": groups the whole part, keeps the rest exactly as given. */
export function groupDigits(raw: string): string {
  const negative = raw.startsWith('-');
  const [whole, frac] = (negative ? raw.slice(1) : raw).split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '-' : ''}${grouped}${frac !== undefined ? `.${frac}` : ''}`;
}

/**
 * "₦4,250,000.00": at least two decimals, never rounded. Money is a decimal string as the API sends it ("4250000.00");
 * never a number worked out in the browser, which can lose digits (DSC-3). Missing or unreadable is "Unknown", never 0.
 */
export function formatAmount(value: string | null | undefined, { sign = true }: { sign?: boolean } = {}): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  const raw = value.replace(/,/g, '').trim();
  if (!/^-?\d+(\.\d+)?$/.test(raw)) return UNKNOWN;
  const negative = raw.startsWith('-');
  const [whole, frac = ''] = (negative ? raw.slice(1) : raw).split('.');
  return `${negative ? '-' : ''}${sign ? '₦' : ''}${groupDigits(`${whole}.${frac.padEnd(2, '0')}`)}`;
}
