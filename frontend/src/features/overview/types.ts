import type { paths } from '@/api/schema';

type Contract = paths['/api/v1/overview']['get']['responses'][200]['content']['application/json'];
export type Overview = Contract;
export type OverviewLine = Contract['lines'][number];
export type OverviewStation = OverviewLine['stations'][number];
