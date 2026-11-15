import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { parsePeriod } from '@/features/finance/month-end/model';
import { MonthEndView } from '@/features/finance/month-end/MonthEndView';

export const metadata: Metadata = { title: 'Month-end · PSL Factory' };

/** The month comes only from the URL; a missing, repeated or malformed period is not found (no default month). */
export default async function MonthEndPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const period = parsePeriod((await searchParams).period);
  if (!period) notFound();
  return <MonthEndView period={period} />;
}
