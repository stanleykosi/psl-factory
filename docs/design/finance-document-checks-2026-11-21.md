# Finance document review

From the project’s **Finance records**, choose **Read and review Finance files**. The reader accepts PDF, Excel, CSV, Word and plain text. It reads text PDFs with their page numbers and sends scanned or illustrated PDFs to OpenRouter’s PDF reader. A reviewer sees the proposed reporting period, currency, units, source fragments and individual account rows alongside a link to the original file.

A Finance member on the project or the Finance lead can correct a row, add a missing one, confirm its units, return the file, or approve the extraction. The reviewer must resolve the reader’s questions and reconcile any supplied check total. A missing check total stays unknown. Approval records both the original amounts and their full currency equivalents. Chidi’s Finance register cites the approved document. Management accounts can accept the same approved rows for its separate source and reporting checks.

The direct structured trial-balance path continues to use the existing source-specific rule. The document-review path works without a predefined client layout.

| In-app browser check | Result |
| --- | --- |
| Upload a sample November PDF as a Finance member | Chidi read the heading “All amounts in NGN thousands”, cited page one and proposed 250 for service income and 75 for consulting income. The review showed the full amounts before approval. [Review screen](../test-evidence/finance-document-review-2026-11-21/reading.jpg) |
| Enter a check total of 324 | The system kept the reading open and asked Finance to recheck the figures. [Held approval](../test-evidence/finance-document-review-2026-11-21/check-total.jpg) |
| Correct the total to 325 and approve | The saved decision showed NGN 250,000 and NGN 75,000, the checked total of NGN 325,000 and the original file link. [Approved figures](../test-evidence/finance-document-review-2026-11-21/approved-figures.jpg) |
| Open the Railway review area with the existing PMO account | The account had no Finance workspaces or visible files. [Railway screen](../test-evidence/finance-document-review-2026-11-21/railway-access.jpg) |

The positive browser example used an isolated PostgreSQL database, an invited Finance member, private object storage and the configured OpenRouter model. The initial local connection timed out. A retry reused the same upload and used Windows’ IPv4 HTTPS client to send the application’s request to OpenRouter. No customer file was used. A separate model check read an image-only PDF, identified millions, and extracted 1.25 and 0.75 from its two detail lines. A reading with no detail lines is held.

A second image-only sample used different account names and amounts. The model identified equipment hire of 1.40 million and studio hire of 0.35 million. It left the separate check-total field empty although the page printed 1.75. The review now requires Finance to enter the printed total or explicitly confirm that the document has none for those rows. A blank field alone cannot pass approval.

Twenty PostgreSQL tests passed for Finance file review and existing management-accounts intake. A separate run covering Finance document review and department assistants passed 13 tests. The checks included project access for a Finance member, department access for the Finance lead, correction, return, duplicate submissions, and handing approved amounts to accounting without multiplying them again.

All six focused Finance document tests passed on the final release, including the missing-total confirmation and the check that an empty reading cannot be approved. Django found no missing database migrations.

Railway reported success for the [web application](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/ac6b2ef8-4bd1-4dcf-9c28-5ef5b0de0de3?id=dfbf7847-6c99-4cc7-b982-ac706c9583f2) and [worker](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/9959671c-482b-4384-9164-13b532b6dc83?id=1599e133-67cf-412d-bfcd-dc3963524714). The final health check returned `ok`. The Railway browser check covered access. The real-model readings and Finance approval were verified with sample documents outside the hosted account.
