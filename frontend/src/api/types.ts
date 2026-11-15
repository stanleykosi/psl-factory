import type { paths } from './schema';

export type Me = paths['/api/v1/me']['get']['responses'][200]['content']['application/json'];
export type Destination = Me['destinations'][number];

// E-WORK-ITEM is the same type as features/work-item's WorkItem (both derive from the schema).
export type WorkItem = paths['/api/v1/work/{work_id}']['get']['responses'][200]['content']['application/json'];
export type WorkTask = WorkItem['tasks'][number];
export type TaskDecision = NonNullable<WorkTask['decision']>;
export type ClaimResult = paths['/api/v1/tasks/{task_id}/claim']['post']['responses'][200]['content']['application/json'];
export type DecideBody = paths['/api/v1/tasks/{task_id}/decision']['post']['requestBody']['content']['application/json'];
export type DecideResult = paths['/api/v1/tasks/{task_id}/decision']['post']['responses'][200]['content']['application/json'];
