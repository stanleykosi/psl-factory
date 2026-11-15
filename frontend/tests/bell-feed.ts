// The shell's alert bell (F-15) reads GET /api/v1/notifications once the frame is ready. Page tests that are not
// about alerts answer it here with an empty list, so their own request counts and queued responses stay theirs.
const EMPTY = { items: [], as_of: '2026-11-14T10:00:00Z', unread_count: 0 };

export const isBellFeed = (request: Request) => request.method === 'GET' && new URL(request.url).pathname === '/api/v1/notifications';

export const bellFeed = () => new Response(JSON.stringify(EMPTY), { status: 200, headers: { 'Content-Type': 'application/json' } });

/** The fetch stub with the bell's feed answered before it: the stub never sees that request. */
export function withoutBellFeed(stub: (request: Request) => Promise<Response>) {
  return (request: Request) => (isBellFeed(request) ? Promise.resolve(bellFeed()) : stub(request));
}
