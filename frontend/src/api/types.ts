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

// Project retrospective (F-119): the live project-meetings operations and the closure checklist.
export type MeetingList = livePaths['/api/v1/projects/{case_id}/meetings']['get']['responses'][200]['content']['application/json'];
export type MeetingOptions = livePaths['/api/v1/projects/{case_id}/meetings/options']['get']['responses'][200]['content']['application/json'];
export type MeetingDetail = livePaths['/api/v1/projects/{case_id}/meetings/{meeting_id}']['get']['responses'][200]['content']['application/json'];
export type MeetingSaveBody = livePaths['/api/v1/projects/{case_id}/meetings']['post']['requestBody']['content']['application/json'];
export type MeetingSaved = livePaths['/api/v1/projects/{case_id}/meetings']['post']['responses'][201]['content']['application/json'];
export type ActionCreateBody = livePaths['/api/v1/projects/{case_id}/actions/create']['post']['requestBody']['content']['application/json'];
export type ClosureChecklist = livePaths['/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist']['get']['responses'][200]['content']['application/json'];
