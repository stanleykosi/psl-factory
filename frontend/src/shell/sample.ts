// R-SAMPLE: the frame is labelled as sample data unless the build explicitly says the API is live.
export const SHOW_SAMPLE_LABEL = process.env.NEXT_PUBLIC_API_MODE !== 'live';

export const SIGN_IN_URL = process.env.NEXT_PUBLIC_SIGN_IN_URL ?? '/accounts/login/';
