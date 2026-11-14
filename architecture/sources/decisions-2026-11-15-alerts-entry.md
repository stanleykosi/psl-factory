# Design engineer decision — 15 Nov 2026

**D-ALERTS-ENTRY: decided.** The alert bell sits in the desktop header, beside the person's name. It opens a full-height right-side drawer (concept 1), and the drawer groups alerts into "Needs you" and "For your information" with an Open action on each row; a "N need you" chip sits next to the bell on wide screens (concept 3). On phone the drawer is a full-height sheet with the two groups as tabs. Source: https://claude.ai/artifact/DAuPR8gxwHgaUY4dY9T6NN (design/concepts/alerts-bell-concepts.html), recommendation section; the design engineer said "go with your recommendation".

Open for the backend developer: which alerts "need you" is not in the v7 notification shape. The frontend proposes an optional `needs_you: boolean` per notification (PROPOSAL); until it exists, every alert shows under "For your information".

Still open: sign-out and the account menu links (D-SIGNIN, PSL).
