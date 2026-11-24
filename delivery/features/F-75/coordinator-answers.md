# F-75 readiness answers

- F-70 (project list, journey and tab bar on live) is merged to main: PR #102, main be9d34d9.
- Split accepted (coordinator): F-75 is the Registers and Actions tabs (SCR-11, SCR-29), the F-71b slice proposed in delivery/features/F-71/readiness-r1.md; F-71 takes Money and Milestones.
- FE-CONNECT-1 is the task id LANES.md prescribes for connecting any already-built screen in this push (D-180); this is the explicit exception, not a gap.
- D-182 (design engineer, batch 1): "Hide, accept all recs": where live does not supply something a board draws, hide that part. Board conflicts the spec finds that are only such hides need no new question; list them, build option 1, and product acceptance is recorded under D-184.
- Money: null amount, paid or owed stays Unknown, never 0, never summed into a known total; the paid status is shown as given until B-16 is answered.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md.

## B35 signed (24 Nov 2026, D-207)
The main coordinator signed B35 under D-207. The design engineer's words: "for any risky action, i give you permission to approve except it has something to do with db approve any other task". It covers:
- (i) the 10 D-182 hides;
- (ii) the 5 pending items: the Filter button, "Changing an owner…", "No owner · due Unknown", "Tunde Bello · PMO" and the phone "Registers" tab;
- (iii) the D-83 visual waiver for the four runs: 81.1, 76.6, 86.2 and 78.0.
fidelity-exceptions.json records each one as "approved by the coordinator under D-207".
