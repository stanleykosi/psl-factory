// Start work types. The chooser, project and source pickers and the weekly start are typed from the live contract; the
// v7 `Field`, `LineOption` and `Legacy*` names stay for the intake pieces StepForm and StartProof still use.
import type { paths as livePaths } from '@/api/live-schema';
import type { paths } from '@/api/schema';

export type Lines = livePaths['/api/v1/lines']['get']['responses'][200]['content']['application/json'];
export type Line = Lines['items'][number];
export type ProjectOptions = livePaths['/api/v1/lines/projects']['get']['responses'][200]['content']['application/json'];
export type Project = ProjectOptions['items'][number];
export type IntakeSources = livePaths['/api/v1/projects/{case_id}/intake-sources']['get']['responses'][200]['content']['application/json'];
export type StartBody = livePaths['/api/v1/work']['post']['requestBody']['content']['application/json'];
export type WeeklyBody = Extract<StartBody, { line: 'pmo-weekly-report/v1' }>;
export type StartResult = livePaths['/api/v1/work']['post']['responses'][200]['content']['application/json'];
export type FieldProblem = { name: string; message: string };

type LegacyLines = paths['/api/v1/lines']['get']['responses'][200]['content']['application/json'];
export type LegacyLine = LegacyLines['items'][number];
export type Field = LegacyLine['intake'][number];
export type LineOptions =
  paths['/api/v1/lines/{line_key}/fields/{field}/options']['get']['responses'][200]['content']['application/json'];
export type LineOption = LineOptions['items'][number];
export type LegacyStartBody = paths['/api/v1/work']['post']['requestBody']['content']['application/json'];
