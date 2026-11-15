'use client';

// The work item page's quiet re-read after a step (F-17): E-WORK-ITEM once, without the loading state, so what
// is on screen (and a form's typed inputs) stays while it loads. The page draws the newer of this and its own
// read. Losing access on the re-read (401, 403, 404) replaces the page with the signed-out or no-access state.
import { useCallback, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { WorkItem } from '@/features/work-item/labels';

const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);

export type WorkspacePage = {
  /** Re-reads the item; the item read, or undefined when the read failed (the page then says so). */
  reload: () => Promise<WorkItem | undefined>;
  /** The last re-read failed: step controls stay off until one works. */
  refreshFailed: boolean;
  /** A step answered 401 or 404: the page shows the signed-out or no-access state. */
  onAccessLost: (error: ApiError) => void;
};

export function useWorkspacePage(id: string) {
  const [fresh, setFresh] = useState<{ item: WorkItem; at: Date } | null>(null);
  const [lost, setLost] = useState<ApiError | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  // A different item starts clean: nothing read or lost for the last one carries over.
  const [forId, setForId] = useState(id);
  if (forId !== id) {
    setForId(id);
    setFresh(null);
    setLost(null);
    setRefreshFailed(false);
  }

  const reload = useCallback(async () => {
    try {
      const item = await call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id: id } } }));
      setFresh({ item, at: new Date() });
      setRefreshFailed(false);
      return item;
    } catch (error) {
      const apiError = error instanceof ApiError ? error : networkError();
      if (ACCESS_LOST.has(apiError.kind)) setLost(apiError);
      else setRefreshFailed(true);
      return undefined;
    }
  }, [id]);

  const page: WorkspacePage = { reload, refreshFailed, onAccessLost: setLost };
  return { fresh, lost, page };
}
