# What changed after reviewing the recovered sources

Version 0.2 · 19 October 2026 · Documentation, not implementation approval

## Plain-language result

We now have direct, paragraph-level evidence from the three previously missing meeting documents and a redacted machine transcript of the Finance recording. A local review also inspected selected frames of the Excel demonstration. This replaces the earlier reliance on the architecture review for many BaaS and Finance descriptions. It does not supply the actual Finance workbooks, private allocation rules or missing operating procedures.

The original register still has exactly 122 entries. Their IDs and original wording do not change. Definitions distinguish what participants described, what the later PMO SOP prescribes, what a sampled screen shows, and what we propose for a future system.

## Exactly what was reviewed

- Three Word documents: all 243 body paragraphs, six empty footnote paragraphs, no tables. The 12 distinct embedded images were checked locally and are avatars/initials, not worksheet evidence.
- Finance recording: 46:30.9375. Local review inspected 163 sampled images, including potentially overlapping targeted samples, on 14 contact sheets; 18 images were inspected at native resolution. There are 44,655 video frames. This is not continuous visual inspection.
- Derived audio: 42:50–43:18 muted, with half-second guard edges. The local PCM check reported zero nonzero bytes across the requested muted interval. The machine transcript contains 661 utterances; all were read locally and used in departmental reconciliation. Speaker numbers are not verified identities, and word-level accuracy is not certified.
- Some text was conservatively redacted for possible credentials and sensitive numerical content. A redacted passage is not evidence that a particular secret was actually present. We do not reconstruct omitted material.
- No BaaS recording was supplied. The PMO SOP and supplied PMO meeting transcript were reviewed for v0.1; the original PMO recording has not been reviewed here.

These are complementary forms of evidence, not a claim that every screen action or workbook formula is understood.

## Important interpretation changes

1. The Finance reporting chain is QuickBooks → exported trial balance → Excel account alignment and notes → management statements → monthly BU results → YTD and presentation. The forecast is a separate planning view, not another complete ledger.
2. Visible formula examples use both divide-by-1,000 and multiply-by-1,000 scaling. Units, account signs and row mappings must be explicit before a calculation can be implemented. A formula visible for an off-screen selected cell must not be assigned to a nearby row.
3. Two payroll inputs are described. Headcount pooling and person-specific allocations are distinct. The private allocation worksheet was deliberately withheld; ratios, denominators, residuals and approval policy remain undecided here.
4. The trial-balance lookup expression is not established. The budget link is truncated. Narrated budget proration is not the same as verification of the exact workbook formula.
5. The asset note shows a March date inside the September management workbook. This may be a valid roll-forward, stale label or wrong period; the owner must determine which.
6. Finance’s earlier phone-call-based PMO handoff explains the visibility problem; it does not remove the later SOP’s signed-baseline, milestone-notification or closure requirements. Notification, recognition, invoicing and receipt of cash remain distinct.
7. BaaS price-inclusive reporting, direct support corrections, centralized visibility and proposed integrations are not proved to be implemented. Described Power Automate work was not inspected.
8. The forecast explicitly omits some receivables. Neither its totals nor a cash-balance formula proves receivables completeness or bank reconciliation.

## Evidence locations and namespaces

Recovered evidence is stored under 01-sources/recovered. BAAS, TEM and FIN identify the corresponding extracted Word sources; P numbers identify source document paragraphs, not rendered pages. VID U numbers identify machine-transcript utterances; V numbers identify the local sampled-visual register. E01–E20 identify evidence groups, not replacement process IDs.

The recovered handoff table uses H01–H10 independently of this package’s existing H01–H06 contracts. This package calls the recovered labels SRC-H01–SRC-H10 to prevent accidental substitution.

## Preservation and mirror limits

The six sources already in the cloud remain unchanged in this package. The four recovered original DOCX/MP4 files remain local, with before/after hashes recorded. Raw originals are not included in the cloud release. The local reviewer inspected all 24 derived addendum files and reported no actual credential values or unnecessary payroll/account-balance details; raw media, frames and environment credentials were excluded. This clearance is for the derived addendum, not raw-source upload. Derived evidence is not an original-file copy.

The local reviewer verified and unpacked the v0.1 cloud ZIP against SHA-256 367f2892771989a962f0311ee1690bda2285be79ff460187ed0d3cf966ca7794. This verifies that particular draft mirror, not the forthcoming v0.2 mirror or identical full-source folders. A new v0.2 local mirror must be checked separately.

## Still required before implementation

Obtain authorized read-only/redacted workbook samples: management accounts, BU FINANCIALS including WK, company budget, payroll join and allocation examples. Obtain the Support SOP and Recon brief. Confirm account/BU mappings, signs/units, historical periods, allocation policy, recognition versus invoice conditions, recipients/access, authority, exception handling and independently agreed mock outcomes. No completed documentation check can substitute for those decisions.
