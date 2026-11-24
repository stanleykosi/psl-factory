import type { paths } from '@/api/live-schema';

export type Overview = paths['/api/v1/overview']['get']['responses'][200]['content']['application/json'];
export type OverviewLine = Overview['lines'][number];
export type WorkCounts = paths['/api/v1/work/counts']['get']['responses'][200]['content']['application/json'];
export type CountsLine = WorkCounts['lines'][number];
