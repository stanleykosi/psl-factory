// F-115: the words for a hypercare criterion. The API gives only a key, an owner and a result; the wording is written here.
// A key this file does not know shows as given, never hidden. Nothing here decides a result.
export type Metric = { key: string; unit: string; owner: string; operator: string; threshold: number };
export type IssueClearance = { scope?: string; reader_id?: number; blocking_statuses: string[]; blocking_severities: string[] };
export type Criteria = { clock: string; minimum_hours: number; confirmation_owners: string[]; metrics: Metric[]; financial_controls: string; issue_clearance?: IssueClearance };

const OPERATORS: Record<string, string> = { lte: 'at most', gte: 'at least', eq: 'exactly' };

/** "at most 2 percent"; an operator this file does not know is shown as given. */
export const ruleText = (m: Pick<Metric, 'operator' | 'threshold' | 'unit'>) => `${Object.hasOwn(OPERATORS, m.operator) ? OPERATORS[m.operator] : m.operator} ${m.threshold} ${m.unit}`;

/** The row label for one criterion, and the rule that goes after it (a metric or the issue clearance), when there is one. */
export function criterionLabel(key: string, owner: string | null, criteria: Criteria | null): { label: string; detail?: string } {
  if (key === 'confirmation' && owner) return { label: `${owner} confirms stability` };
  if (key === 'elapsed_hours' && owner) return { label: criteria ? `${owner} observed after ${criteria.minimum_hours} hours` : `${owner} observed after the minimum time` };
  if (key.startsWith('metric:') && owner) {
    const name = key.slice('metric:'.length);
    const metric = criteria?.metrics.find((m) => m.key === name && m.owner === owner);
    return { label: `${owner} · ${name}`, ...(metric ? { detail: ruleText(metric) } : {}) };
  }
  if (key === 'issue_clearance') {
    const c = criteria?.issue_clearance;
    return { label: 'No blocking issues', ...(c ? { detail: `Blocking: ${c.blocking_severities.join(', ')} severity, ${c.blocking_statuses.join(', ')}` } : {}) };
  }
  return { label: key };
}

export const RESULT_TAGS: Record<string, { label: string; tone: 'verified' | 'stopped' | 'uncertain' }> = {
  met: { label: 'Met', tone: 'verified' },
  not_met: { label: 'Not met', tone: 'stopped' },
  unknown: { label: 'Not known', tone: 'uncertain' },
};
