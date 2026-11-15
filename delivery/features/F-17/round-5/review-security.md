VERDICT: PASS
COMMIT: f91bc63ff41283e698faf47b356721f4ce2ec022
REVIEWER: reviewer-security
AUTHORITY: security reviewer

Lean confirm of a5e803ab..f91bc63. No backend changes. Frontend changes (Sections, StepForm, Workspace, usePageReload, CSS, tests) add no new API calls, URLs, cookies, auth/session handling, HTML injection or permission display changes. usePageReload now ignores a stale response after the item id changes, which prevents showing an old item's data on a new page. The submit button class change is cosmetic. The rest of the diff is fidelity reports, images and region JSON.
