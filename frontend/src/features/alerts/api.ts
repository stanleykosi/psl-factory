// The shared client (same origin, X-CSRFToken on every write) typed with the F-12 proposal paths.
// Removed at the rebase onto F-13: alerts code then calls `api` from '@/api/client' directly.
import type { Client } from 'openapi-fetch';

import { api } from '@/api/client';

import type { AlertPaths } from './contract-proposal';

export const alertsApi = api as unknown as Client<AlertPaths>;
