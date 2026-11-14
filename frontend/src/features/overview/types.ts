import type { paths } from '@/api/schema';

/**
 * Proposed optional E-OVERVIEW line field (not yet in the contract, which closes `lines[]` with
 * additionalProperties: false). It sets the tag tone on SCR-06; without it the tone follows needs_person.
 */
export type LineStatus = 'on_track' | 'waiting' | 'stopped' | 'uncertain' | 'problems';

type Contract = paths['/api/v1/overview']['get']['responses'][200]['content']['application/json'];
export type OverviewLine = Contract['lines'][number] & { status?: LineStatus };
export type Overview = Omit<Contract, 'lines'> & { lines: OverviewLine[] };
export type OverviewStation = OverviewLine['stations'][number];
