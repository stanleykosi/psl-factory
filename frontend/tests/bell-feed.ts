// The shell's alert bell (F-15) reads GET /api/v1/notifications once the frame is ready. Page tests that are not
// about alerts answer it here with an empty list, so their own request counts and queued responses stay theirs.
const EMPTY = { items: [], as_of: '2026-11-14T10:00:00Z', page: 1, next_page: null, unread: 0, daily_summary: { date: '2026-11-14', actions_open: 0, unread_updates_today: 0, unread_without_timestamp: 0, scope: 'current_inbox' } };

export const isBellFeed = (request: Request) => request.method === 'GET' && new URL(request.url).pathname === '/api/v1/notifications';

export const bellFeed = () => new Response(JSON.stringify(EMPTY), { status: 200, headers: { 'Content-Type': 'application/json' } });

/** The fetch stub with the bell's feed (and, unless `ownRoleDashboard`, the role-dashboard read) answered before it: the stub never sees those requests. */
export function withoutBellFeed(stub: (request: Request) => Promise<Response>, { ownRoleDashboard = false } = {}) {
  return (request: Request) => {
    if (isBellFeed(request)) return Promise.resolve(bellFeed());
    if (!ownRoleDashboard && isRoleDashboard(request)) return Promise.resolve(roleDashboard());
    return stub(request);
  };
}

// The frame also reads GET /api/v1/role-dashboard once per page load for the role words (F-57). Page tests answer it with no
// positions (the bar shows the name alone), so the same request counts and queued responses stay theirs.
const DASHBOARD = { positions: [], actions: [], decisions: [], team_decisions: [], limited: false, workspace_decisions: [], approval_desks: [], has_teams: false, page: 1, has_next: false, as_of: '2026-11-23T09:00:00Z' };

export const isRoleDashboard = (request: Request) => request.method === 'GET' && new URL(request.url).pathname === '/api/v1/role-dashboard';

export const roleDashboard = () => new Response(JSON.stringify(DASHBOARD), { status: 200, headers: { 'Content-Type': 'application/json' } });
