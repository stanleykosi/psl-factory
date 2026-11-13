# MoneyField

Amounts are entered and shown in `mono`, with the ₦ sign fixed in front and two decimals.

- Thousands separators appear as the person types; the stored value is exact (no rounding).
- An amount that is not known yet is written **Unknown** (amber tag), never 0 and never blank. "Mark as unknown" is a text button under the field where Unknown is allowed.
- Amounts that come from the contract are read-only and say where they came from.
- States: empty, focus, filled, error, read-only from contract, unknown.
