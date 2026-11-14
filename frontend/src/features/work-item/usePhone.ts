'use client';

import { useSyncExternalStore } from 'react';

// bp-phone: the phone boards' order applies below 720px, the same breakpoint as the frame's phone bar.
const PHONE_QUERY = '(max-width: 719.98px)';

function subscribe(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** True below 720px, so each viewport renders its board's section order in DOM order (reading and focus order follow). */
export function useIsPhone() {
  return useSyncExternalStore(subscribe, isPhoneNow, () => false);
}
