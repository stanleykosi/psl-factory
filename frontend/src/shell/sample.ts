// R-SAMPLE: the data stays marked sample; the visible tag is off unless the build sets NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1
// (design decision, 14 Nov 2026). Read at render so tests can switch it; Next inlines the values at build.
export const showSampleLabel = () => process.env.NEXT_PUBLIC_SHOW_SAMPLE_LABEL === '1';

/** The frame (top bar, phone bar) is sample unless the build explicitly says the API is live. */
export const frameIsSample = () => process.env.NEXT_PUBLIC_API_MODE !== 'live';

export const SIGN_IN_URL = process.env.NEXT_PUBLIC_SIGN_IN_URL ?? '/accounts/login/';
