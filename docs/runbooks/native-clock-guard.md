# Native action-clock reassessment

Engineering interface; owner calendar, timezone, anchor, duration and pause values remain configuration decisions. Synthetic fixtures do not select operational policy.

The existing clock configuration workbench validates versioned D04 rule references before activation. `workflow.clock.evaluate` now accepts an exact recorded `action_state_id` in the selected pilot binding UI. Current case and meeting read permission is required before source lookup. The selected action must be the current, nonterminal calculated state. Explicit and unknown deadlines remain valid commitments, but cannot be represented as calculated deadlines by this preview.

New calculated actions record both the actual meeting timestamp and actual assignment timestamp plus the exact meeting version. Reassessment reuses `calculate_action_due` with those original inputs and current validated policies. Elapsed-hour rules require anchor/deadline policy only; working-day rules additionally require timezone and calendar. Missing policy holds calculation while explicit commitment capture and unrelated work remain available.

Legacy calculated actions retain their recorded selected anchor. If the currently selected anchor kind is unchanged, that exact anchor supports reassessment with historical policy provenance. If it changes, the missing timestamp is not inferred from row creation time or a later meeting revision; the preview holds for source-backed human review.

The output is **base due reassessment only**. Stored deadlines, pause/resume extensions, owners, action permissions and completion status are unchanged. Reviewed pilot evidence and the A04 investigator cannot adopt the result. The existing human action-management service accepts an explicit, evidence-backed assignment/deadline revision, checks current authority and preserves history.

Pilot output includes identifiers, policy pins, hashes and timestamps, not action descriptions or meeting notes. Binding validation and PostgreSQL constraints reject foreign source states, malformed types, unknown keys and unselected people/operations. Observation is evidence at a point in time; source/policy/access changes require fresh observation.

PostgreSQL results and isolated recovery evidence are indexed in BUILD-TESTS.md. No live pilot, business acceptance or external-provider evaluation is implied.
