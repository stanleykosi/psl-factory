STATUS: READY
COMMIT: f91bc63ff41283e698faf47b356721f4ce2ec022
BUILDER: coordinator
LANE: records only

## Summary
- No product code changed. The only change since round 4 (5dea11e) is `delivery/features/F-17/fidelity-exceptions.json`: every exception's `approved_by` now reads "design engineer, 15 Nov (D-65)", after the design engineer accepted the frame at its measured region scores.
- The round-4 build note (round-4/build.md) holds the last product evidence: checks.sh exit 0, e2e/workspace.spec.ts 31/31, region scores in round-4/fidelity/region-scores.txt.

## Validation
- `delivery/checks.sh` at f91bc63: exit 0 (gate round 5, attempt 1).
