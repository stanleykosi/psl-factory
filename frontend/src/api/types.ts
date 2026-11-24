import type { paths as livePaths } from './live-schema';
import type { paths } from './schema';

// The frame reads the live contract (D-172); the rest of the types stay on v7.
export type Me = livePaths['/api/v1/me']['get']['responses'][200]['content']['application/json'];
export type DestinationKey = 'my_work' | 'projects' | 'overview' | 'setup' | 'clients' | 'assistant';

// E-WORK-ITEM is the same type as features/work-item's WorkItem (both derive from the schema).
export type WorkItem = paths['/api/v1/work/{work_id}']['get']['responses'][200]['content']['application/json'];
export type WorkTask = WorkItem['tasks'][number];
export type TaskDecision = NonNullable<WorkTask['decision']>;
export type ClaimResult = paths['/api/v1/tasks/{task_id}/claim']['post']['responses'][200]['content']['application/json'];
export type DecideBody = paths['/api/v1/tasks/{task_id}/decision']['post']['requestBody']['content']['application/json'];
export type DecideResult = paths['/api/v1/tasks/{task_id}/decision']['post']['responses'][200]['content']['application/json'];

// SCR-03 on the live contract (F-64): the work read, the task read, the decision and the decision history.
export type LiveWork = livePaths['/api/v1/work/{work_id}']['get']['responses'][200]['content']['application/json'];
export type LiveTask = LiveWork['tasks'][number];
export type LiveTaskRead = livePaths['/api/v1/tasks/{task_id}']['get']['responses'][200]['content']['application/json'];
export type LiveDecisionBody = livePaths['/api/v1/tasks/{task_id}/decision']['post']['requestBody']['content']['application/json'];
export type LiveDecisionResult = livePaths['/api/v1/tasks/{task_id}/decision']['post']['responses'][200]['content']['application/json'];
export type LiveHistoryItem = livePaths['/api/v1/work/{work_id}/history']['get']['responses'][200]['content']['application/json']['items'][number];

// F-85: the live work item (contract 1.22.0). The work item page and the line adapters read these, not the v7 WorkItem above.
type LiveGet<P extends keyof livePaths> = livePaths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type LiveWorkItem = LiveGet<'/api/v1/work/{work_id}'>;
export type LiveWorkTask = LiveWorkItem['tasks'][number];
export type LiveWorkHistory = LiveGet<'/api/v1/work/{work_id}/history'>;
export type LiveHistoryRow = LiveWorkHistory['items'][number];
export type LiveWeeklyReport = LiveGet<'/api/v1/work/{work_id}/weekly-report'>;
