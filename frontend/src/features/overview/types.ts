import type { paths } from '@/api/schema';

export type Overview = paths['/api/v1/overview']['get']['responses'][200]['content']['application/json'];
export type OverviewLine = Overview['lines'][number];
export type OverviewStation = OverviewLine['stations'][number];
