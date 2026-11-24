# F-71 readiness answers

- F-70 (project list, journey and tab bar on live) is merged to main: PR #102, main be9d34d9.
- Split accepted (coordinator): F-71 is your proposed F-71a, the Money and Milestones tabs (SCR-12, SCR-38). The Registers and Actions tabs (SCR-11, SCR-29) are F-75.
- FE-CONNECT-1 is the task id LANES.md prescribes for connecting any already-built screen in this push (D-180); this is the explicit exception, not a gap.
- D-182 (design engineer, batch 1): "Hide, accept all recs": where live does not supply something a board draws, hide that part. Board conflicts the spec finds that are only such hides need no new question; list them, build option 1, and product acceptance is recorded under D-184.
- Money: null amount, paid or owed stays Unknown, never 0, never summed into a known total; the paid status is shown as given until B-16 is answered.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md.

## B33 and B34 answered (24 Nov 2026, D-202)
The design engineer, in chat, relayed by the main coordinator (records 2d8816cc, delivery/OVERNIGHT-DECISIONS.md): "Sign all". This signs B33 (all 10 exceptions as drafted) and B34 items 1, 2 and 3 (sample content, NGN, and a visual waiver for the six SCR-12/SCR-38 runs). fidelity-exceptions.json records each entry and waiver as signed under D-202. UI-1-1 closes on that sign-off. F-71 finishes review and acceptance under D-184.
