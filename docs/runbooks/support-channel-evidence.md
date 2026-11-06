# Customer-channel receipt evidence and human clocks

Engineering implementation over B14's proposed Support-owned flow standardisation, B01 supplied channel references and B03 clock definitions. This is not a Teams/WhatsApp/native vendor API, real source/owner acceptance, customer reading proof or real model evaluation. The software verifies a configured PSL-owned read-only gateway contract and independently reviewed delivery meaning. Mock and authenticated remote claims have explicit different classifications.

## Configure and capture

Use /cases/<case>/support/channels/. First capture private protocol/meaning evidence. B14.channel_receipts requires that exact evidence ID, logical reviewed endpoint/credential revision/principal/contract, channel/account/customer/recipient/human-sender identities, verifier/reviewer, independence and bounded review/lease/attempt budgets. Existing versioned policy JSON draft/validate/activate UI applies. Customer must match the canonical linked case. No URL or credential value is accepted in evidence; deployment-owned READINESS_ENDPOINTS/READINESS_SECRET_REFS resolve origin and environment secret. HTTPS is required outside explicit synthetic loopback. Sender/recipient mappings and the source gateway's actual vendor evidence still need owner validation.

Capture a supplied receipt identity against an existing human-released response packet containing the exact body. This is a claim, not proof. Its immutable namespace is tenant/channel/account/external receipt reference; a stable key cannot reassign that receipt or change source version/message/case. The claim binds case/tenant, account/customer/recipient/sender, external reference/version, packet hash and exact UTF-8 body SHA256. An internal inbox receipt is never a channel receipt.

## Read-only gateway protocol

Run `.venv/Scripts/python manage.py work_support_channels --case <UUID> --limit 1` after reserving a scoped check. The engineering protocol is GET `/support-receipts/<receipt_key>`, where receipt_key is the canonical digest of tenant/channel/account/external_ref. It transmits no response body or expected hashes for the gateway to echo. Bearer authentication, fixed reviewed origin, no redirects/proxy inheritance, bounded strict JSON/UTF-8 and closed schema apply. No POST or customer dispatch exists in this adapter.

The response must exactly match the claim's identity fields/protocol plus configured principal/contract version. It supplies status delivered/pending/failed/retracted, human_response, sent_at and delivered_at. Timestamps must be timezone-aware, ordered, nonfuture and known for delivered status. A successful check means authenticated contract-matching observation, not human approval. Pending/retracted/bot/unauthorised-send observations remain evidence; they cannot qualify for the clock. Recorded human release window/withdrawal is checked separately so actual out-of-authority observations are preserved for investigation.

Case/grant/principal locks order current source revocation before a new gateway read. Jobs retain policy/source-contract hash, actual verifier authority, keyed credential binding, stable key and bounded lease/fence/attempt budget. Confirmed local observations reconcile before current authority/runtime credential checks after a crash; protected reads and human reuse still require current native source grants. A lost GET response has no remote business effect; worker recovery repeats only the original read and never dispatches a message. Unknown checks use the scoped worker. Operator retry cannot reset the original budget or retarget intent.

## Human review and clock

Configured independent Support/D05 reviewer confirms the exact latest completed receipt, source contract and delivered human-response meaning. Preparers/verifier/message author cannot review their own evidence under original summary independence. New checks, policy/authority changes, negative/retracted evidence, return/withdrawal and review expiry hold current use. Receipt and review history stay immutable.

B14.channel_clock explicitly configures the human attestor, reviewed_human_customer_delivery basis, receipt age and late-event handling. It requires the existing metric rule to exclude bot acknowledgements. Activating this contract enrolls future qualifying human response transitions; policy revocation does not silently restore a manual bypass. Non-enrolled legacy/manual workflows retain their documented source limitations. Missing clock rules hold attestation, while receipt capture/verification/review and other case work remain available.

Only an explicit configured human action applies the exact delivery timestamp through the original Support transition. Original state/owner/flow adoption, permissions, nonfuture ordered-event and response-evidence controls remain. The private attestation links receipt/review/policy/authority to one SupportEvent. Duplicate receipt aliases cannot attest the same released message twice. No private receipt IDs or channel metadata enter public event payloads. No Finance/Engineering effects or case closure occur.

A timestamp earlier than current ordered case history holds application under the typed hold_for_correction policy. Capture and verification still work. Late-history correction, successor clock decisions and revalidation after review/source corrections are remaining engineering, not an invented backdating rule. Existing manual clocks in an enrolled legacy history require explicit reconciliation rather than being silently reclassified as verified.

If reviewed channel evidence becomes noncurrent after attestation, current metrics return unknown and dependent reviewed summaries stale. Stored first_response_at/event/attestation remain historical evidence; no clock or history is erased or silently rewritten. A successor/correction workflow is needed to reauthorise corrected evidence, including replacing or renewing an exact review pin.

## Privacy and acceptance

Channel screens/reports and live bounded guidance require current native source and separate channel action grants. Protocol evidence uses the protected agent_private_ namespace, and channel audit entries are hidden from generic timelines. Agents return live scoped metadata/questions; they do not write generic AgentRun history, approve evidence, apply a clock or send messages. Native vendor customer delivery and recipient reading remain unproven by this engineering gateway alone. Operational Support still requires its original SOP/native AF13 acceptance. Real gateways/vendors, independently validated mappings/receipt semantics, credentials and owner decisions are separate inputs.

Actual test commands/results and preservation evidence are in BUILD-TESTS.md. Synthetic fixture values are examples, not real appointments, clock/SLA values or defaults.
