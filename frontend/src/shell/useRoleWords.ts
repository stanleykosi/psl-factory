'use client';

import { useEffect, useState } from 'react';

import { call, liveApi } from '@/api/client';

/** The workspace role names of GET /api/v1/role-dashboard (page 1): unique, first-seen order, joined with ", "; null when there are none. */
export function roleWordsFrom(positions: readonly { name: string }[]): string | null {
  const names = [...new Set(positions.map((p) => p.name.trim()).filter((name) => name !== ''))];
  return names.length > 0 ? names.join(', ') : null;
}

/**
 * Role words for the bars, read once per page load beside /me. The frame never waits for them: they are null while the
 * read is pending and when it fails or finds nothing, and a failed read shows no error.
 */
export function useRoleWords(): string | null {
  const [words, setWords] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    call(liveApi.GET('/api/v1/role-dashboard'))
      .then((dashboard) => (cancelled ? undefined : setWords(roleWordsFrom(dashboard.positions))))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return words;
}
