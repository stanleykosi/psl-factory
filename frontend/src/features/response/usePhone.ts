'use client';

import { useSyncExternalStore } from 'react';

const PHONE_QUERY = '(max-width: 719.98px)';

function subscribe(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** Below 720px (bp-phone) the boards draw a different layout, not only a narrower one. */
export function useIsPhone() {
  return useSyncExternalStore(subscribe, isPhoneNow, () => false);
}
