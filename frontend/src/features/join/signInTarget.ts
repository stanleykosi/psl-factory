import { safeNext } from '@/shell/signInNext';

/**
 * Where the "Sign in" button goes, from the `next_url` the server returns after set-up: `/sign-in`, or `/sign-in` with
 * one safe `next`. Anything else (another path, an absolute URL, other query keys) gives plain `/sign-in`.
 */
export function signInTarget(nextUrl: unknown): string {
  const plain = '/sign-in';
  if (typeof nextUrl !== 'string') return plain;
  const [path, query, ...rest] = nextUrl.split('?');
  if (path !== plain || query === undefined || rest.length > 0) return plain;
  const params = new URLSearchParams(query);
  const keys = [...params.keys()];
  if (keys.length !== 1 || keys[0] !== 'next' || params.getAll('next').length !== 1) return plain;
  const next = safeNext(params.get('next'));
  return next ? `${plain}?next=${encodeURIComponent(next)}` : plain;
}
