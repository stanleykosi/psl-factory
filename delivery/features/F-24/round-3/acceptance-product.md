VERDICT: PASS
COMMIT: f264d1b41795465f5547fdfe30b9c9818c96b0a6
REVIEWER: design engineer (recorded by the coordinator)
AUTHORITY: product acceptance, design engineer, 16 Nov 2026 — D-101

The design engineer tried the F-24 branch on localhost:3000 (contract mock) and replied "accept".

Checked in the demo and by QA (round-3/review-qa.md): a person starts every work item from the prefilled Start work drawer; nothing offers approve, send or pay; replies show steps and sources; restricted sources read "Restricted"; unknown amounts read "Unknown"; the microphone is held with no speech code; agent wording claims nothing the backend won't do.

Known limits accepted: the work item reached after a start is an existing sample item; a second start shows Start work's generic 409 text (QA-3-1, follow-up).

Head update: the head moved from 2075d4aa (the build the design engineer tried) to f264d1b4 only by merging dlv-00, which brings F-22 (merged with the design engineer's approval). No F-24 file changed; checks and e2e pass on the merged head (merge-checks.log, merge-e2e.log).
