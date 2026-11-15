VERDICT: PASS
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary

Lean confirm of f91bc63..9757462 (frontend/src only: Workspace.tsx, useWorkspaceStep.ts, workspace.css). The client now cannot start a second send on an item awaiting reconcile, by any path in the workspace and for any viewer. No new API call, URL, auth handling or HTML injection is introduced. Duplicate-send protection still depends on backend idempotency, which is not built yet; that is carried forward below.

## Findings

- SEC-5-C1 | non-blocking | medium | backend (carried forward, not a finding against this diff) | The real guard against a duplicate client email is backend idempotency: the server must reject or replay a step on an item awaiting reconcile and honour the idempotency_key. It is not built yet. The frontend lock is a UI safeguard only. It does not stop a second tab, a stale tab, a direct API call or a retry from another client. It must be built and tested before any real send is enabled.

## Verified

- useWorkspaceStep now sets allLocked = pressLocked || awaitingReconcile. awaitingReconcile comes from Boolean(item.reconcile), not from the viewer's permissions, so a viewer without the reconcile permission is locked too. hasReconcile (which needs allowed_actions to include 'reconcile') only controls the reconcile affordance and the pinned-button styling.
- submit() is the only path to postStep. It returns { kind: 'kept' } when allLocked is true, before it sets writing or builds a body. Every entry point reaches it through run(): press() (which also checks off(step), and off() includes flow.allLocked), the StepForm onSubmit, the "Try again" button (the notice-driven retry via run(last.current)), and the multi-item steps (itemIds). I found no other postStep caller in the workspace.
- A reload keeps the lock. After a reload, item.reconcile is still set, so the lock is re-derived from server state rather than from component memory. This closes QA-5-5. pressLocked still locks at once on effect_uncertain, before the reload returns.
- The lock is conservative. Once pressLocked is set it stays until the page is reopened, even if reconcile later clears. That is the safe direction.
- The CSS change (.ws-decide--flow, white-space: normal, padding and scroll-padding) is presentation only. The :has() rules do not hide or enable controls. Buttons are disabled in logic (off(), the guard in submit), not only visually.
- No new endpoints, storage, cookies, dangerouslySetInnerHTML, or logging of ids or tokens. No new dependencies. No secrets.
