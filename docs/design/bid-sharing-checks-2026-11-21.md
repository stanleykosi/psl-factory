# Original bid sharing

PSL chose Private or Public for the original bid and its recorded client conversation. The owner makes the choice. Public includes other PMO teams in the same organisation and keeps sample and operational work separate. A team can open the original bid from its own workspace and follow Tola’s citation back to it.

| In-app browser check | What happened |
| --- | --- |
| Owner opens a new bid | The bid started private. Its owner recorded the client’s request for two Wednesday evening training sessions and recordings for the support team. [Owner’s private bid](../test-evidence/bid-sharing-2026-11-21/owner-private.jpg) |
| Owner chooses Public | A member assigned to Coastal rollout opened the Cedar proposal and read the conversation. Only the owner saw the sharing controls. [Owner’s choice](../test-evidence/bid-sharing-2026-11-21/owner-public.jpg) · [Receiving team’s view](../test-evidence/bid-sharing-2026-11-21/other-team-original.jpg) |
| Receiving member asks Tola | Tola answered with the requested day, time of day, number of sessions and audience for the recordings. Her citation opened the original Cedar bid. [Tola’s answer and original source](../test-evidence/bid-sharing-2026-11-21/tola-cites-original.jpg) |
| Owner restores Private | The bid disappeared from the other team’s library. Its saved link returned 404. The earlier chat hid the answer and said the source needed a fresh check. [Receiving library](../test-evidence/bid-sharing-2026-11-21/private-other-team-library.jpg) · [Earlier chat after withdrawal](../test-evidence/bid-sharing-2026-11-21/private-earlier-chat.jpg) |
| Owner returns to the private bid | The owner could still read the original note and ask Tola about the client’s instructions. [Owner’s record](../test-evidence/bid-sharing-2026-11-21/private-owner-returns.jpg) · [Owner’s private answer](../test-evidence/bid-sharing-2026-11-21/owner-private-tola.jpg) |
| Railway design-acceptance | The signed-in PMO head opened Projects, PSL Role Testing, PMO records, Bid requests, then the bid library. That hosted workspace had no available bids. [Hosted browser check](../test-evidence/bid-sharing-2026-11-21/railway-bid-library.jpg) |

The two-team walkthrough used isolated PostgreSQL sample workspaces. Both Tola answers used the configured OpenRouter model. No customer conversations or sample bids were added to Railway during the check.

Railway reported successful design-acceptance web deployment `7d35452f-8041-4904-9bb5-1f84f415e0a6` and worker deployment `26bae55f-5575-42d0-acb0-89ee8defb080`. [Open the hosted bid library](https://psl-design-web-design-acceptance.up.railway.app/projects/961dd8cd-3bf0-4cd3-9493-4dc2423270d5/bid-library/)

The first PostgreSQL run passed 25 checks covering bid sharing, winning-answer review and assistant conversations. The final run passed 10 checks covering bid sharing, original uploads and project data-use settings. It verified that the exact uploaded Word file and its extracted text follow the owner’s current choice, that an explicit Private choice overrides an older individual-answer rule, and that other organisations and operational workspaces cannot read a published sample bid. The upload test used a simulated file store. [Bid sharing checks](../../tests/test_bid_sharing.py)
