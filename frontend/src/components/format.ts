// The README's formats, in one place: dates "17 Nov 2026", times "14:30 WAT" (24-hour, Africa/Lagos), amounts
// "₦4,250,000.00" (two decimals, never rounded). A value that is missing is "Unknown", never 0 and never blank.

export const UNKNOWN = 'Unknown';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const LAGOS = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Lagos',
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

/** "17 Nov 2026". A calendar date (2026-11-17) is read as written; a timestamp is read in WAT. */
export function formatDate(value: When): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  if (typeof value === 'string') {
    const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (day) return `${Number(day[3])} ${MONTHS[Number(day[2]) - 1]} ${day[1]}`;
  }
  const parts = lagosParts(value);
  return parts ? `${Number(parts.day)} ${MONTHS[Number(parts.month) - 1]} ${parts.year}` : UNKNOWN;
}

/** "14:30 WAT". */
export function formatTime(value: When): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  const parts = lagosParts(value);
  return parts ? `${parts.hour}:${parts.minute} WAT` : UNKNOWN;
}

/** "17 Nov 2026 14:30 WAT". */
export function formatDateTime(value: When): string {
  const date = formatDate(value);
  return date === UNKNOWN ? UNKNOWN : `${date} ${formatTime(value)}`;
}

/** "4250000.5" → "4,250,000.5": groups the whole part, keeps the rest exactly as given. */
export function groupDigits(raw: string): string {
  const negative = raw.startsWith('-');
  const [whole, frac] = (negative ? raw.slice(1) : raw).split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '-' : ''}${grouped}${frac !== undefined ? `.${frac}` : ''}`;
}

/**
 * "₦4,250,000.00": at least two decimals, never rounded (the value is a decimal string or an exact number).
 * Missing or unreadable is "Unknown", never 0.
 */
export function formatAmount(value: string | number | null | undefined, { sign = true }: { sign?: boolean } = {}): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  const raw = typeof value === 'number' ? (Number.isFinite(value) ? String(value) : '') : value.replace(/,/g, '').trim();
  if (!/^-?\d+(\.\d+)?$/.test(raw)) return UNKNOWN;
  const negative = raw.startsWith('-');
  const [whole, frac = ''] = (negative ? raw.slice(1) : raw).split('.');
  return `${negative ? '-' : ''}${sign ? '₦' : ''}${groupDigits(`${whole}.${frac.padEnd(2, '0')}`)}`;
}
