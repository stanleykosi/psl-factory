# Frontend decisions and role boundary, 13 Nov 2026 (later the same day)

Said by the design engineer while reviewing architecture package v1.

1. Rows per page: people choose 10, 20 or 50 rows on lists. (Default 20 is a proposal.)
2. The other proposals are followed as proposed: screen refresh by polling, and the first
   feature (My work and one decision, end to end).
3. Role boundary: the design engineer works on the frontend only and connects it to
   whatever the backend provides. They do not decide how the backend or the agents work:
   API style, sign-in mechanics, new backend records, AI and alert providers, and what
   "return" does are for the backend developer (and PSL where business rules apply).
   Those stay proposals the frontend builds against.
