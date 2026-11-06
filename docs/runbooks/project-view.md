# Shared project metadata

The proposed P05 source contract is a permissioned project view, without another project-view approval. This implementation provides a finite live metadata projection; it does not infer phase, current gate acceptance, completeness or release readiness.

Operators with case/policy access can open **Shared project audience configuration** on the case. Draft `D11.shared_project_view` using source evidence, then validate and activate it through the existing versioned policy UI. Its exact project/classification, named disclosure principal, audience keys/recipient IDs, permitted groups, source age, missing/stale behavior and row bounds are typed. No actual configuration, recipients, thresholds or grants are installed by the build. The fixture is explicitly synthetic.

The discloser must retain current `project.share`, case read and each selected source-domain read action. Recipients need their own current exact-case `project.view` grant and current membership of the selected audience. They do not receive case read or document access. Current active principals and grants are checked again under the case/principal/grant locks. A revoked unrelated audience/source grant does not widen the selected profile or combine profiles.

The global **Shared project views** link lists at most100 granted projects, using audience key and project UUID rather than a case title the recipient may not be permitted to see. `/cases/<id>/project-view/<audience>/` opens the selected projection. Missing policy/source or exceeded configured thresholds holds this view only. Broad case/source workbenches retain their own permissions and controls.

Permitted groups are:

- Identifiers: immutable recorded ID, namespace, value and recording timestamp. These are history, not an assertion that an old alias is the current external tracker reference.
- Milestones: recorded ID, name and completion time. This does not issue an invoice or assert Finance recognition.
- Actions: recorded ID/reference, current recorded state, owner-assigned flag, recorded deadline/basis and state timestamp. No owner name, action description, reason, notes or clock policy body is disclosed.
- Delivery events: recorded event/dossier ID, kind and timestamp. Payloads, external references, evidence and Finance-confirmation events are excluded.

Each group reports truncation; each returned fact reports age against configured thresholds. Source timestamps are never replaced by rendering time. Empty sources remain unknown, unless the owner configured the dependent view to hold. Metadata text is escaped, authenticated pages use no-store responses, and recipient/source authority changes take effect on the next request.

The optional internal inspection requires `agent.project_view` as well as the same view/audience access. It uses only the identical DTO to identify missing/stale/truncated groups and actions with unknown recorded deadlines. It performs no external model call, private retrieval, approval, access change or effect. It is deterministic bounded investigation, not provider-quality evidence.

This is a bounded P05 increment. Broader source-specific progress/dependency metrics, actual disclosure/recipient/freshness agreement and operational acceptance remain separate. See BUILD-TESTS.md for actual PostgreSQL results; configuration-interface counts are separate from the122 original process IDs.
