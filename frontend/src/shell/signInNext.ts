import { FRAME_ROUTES } from './destinations';

const MAX_LENGTH = 2048;

// A same-site path only: one leading slash, no backslash or control character, no dot segment, and a path that is the
// home page or one of the frame's pages.
function plainPath(value: string): boolean {
  if (!value.startsWith('/') || value.startsWith('//')) return false;
  if (value.includes('\\') || /[\u0000-\u001f\u007f]/.test(value)) return false;
  const path = value.split(/[?#]/)[0];
  if (path.split('/').some((segment) => segment === '.' || segment === '..')) return false;
  return path === '/' || FRAME_ROUTES.some((route) => path === route || path.startsWith(`${route}/`));
}

/**
 * The destination after sign-in, or null when it is not a page of this app: used on the `next` query before it is sent
 * and on the `next_url` the server returns before it is followed. The value and its once-decoded form must both pass.
 */
export function safeNext(value: unknown): string | null {
  if (typeof value !== 'string' || value === '' || value.length > MAX_LENGTH) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    return null;
  }
  return plainPath(value) && plainPath(decoded) ? value : null;
}
