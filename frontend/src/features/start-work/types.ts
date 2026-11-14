// Start work types, derived from the contract (E-LINES, E-LINE-OPTIONS, E-WORK-START).
import type { paths } from '@/api/schema';

export type Lines = paths['/api/v1/lines']['get']['responses'][200]['content']['application/json'];
export type Line = Lines['items'][number];
export type Field = Line['intake'][number];
export type LineOptions =
  paths['/api/v1/lines/{line_key}/fields/{field}/options']['get']['responses'][200]['content']['application/json'];
export type LineOption = LineOptions['items'][number];
export type StartBody = paths['/api/v1/work']['post']['requestBody']['content']['application/json'];
export type StartResult = paths['/api/v1/work']['post']['responses'][201]['content']['application/json'];
export type FieldProblem = { name: string; message: string };
