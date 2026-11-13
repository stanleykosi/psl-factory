import type { paths } from './schema';

export type Me = paths['/api/v1/me']['get']['responses'][200]['content']['application/json'];
export type Destination = Me['destinations'][number];
