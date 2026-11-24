// How lines sit on the floor. The backend does not group lines (A-35), so the floor is a display mapping owned here:
// each line key goes to one floor, with the avatar and subtitle drawn on SCR-06. A key not listed goes under "Other lines".

type Agent = 'tola' | 'chidi' | 'zainab';

/** Bump when a key moves floor or a floor is renamed. */
export const FLOOR_MAP_VERSION = 1;

export const OTHER_FLOOR = 'Other lines';

export const LINE_IDENTITY: Record<string, { agent: Agent; subtitle: string }> = {
  'Pre-sale': { agent: 'tola', subtitle: 'RFP · commercial' },
  Planning: { agent: 'tola', subtitle: 'Engagement · plan' },
  Release: { agent: 'tola', subtitle: 'Gates · go-live' },
  Closing: { agent: 'tola', subtitle: 'Hypercare · handover · closure' },
  Invoices: { agent: 'chidi', subtitle: 'Milestone to verified' },
  'Month-end': { agent: 'chidi', subtitle: 'Accounts · schedules · PPE' },
  'Cash and BU': { agent: 'chidi', subtitle: 'Forecast · BU · ledger' },
  Payroll: { agent: 'zainab', subtitle: 'Restricted' },
};

/** Floors in drawn order, each with the line keys that stand on it. "Other lines" comes last and takes the rest. */
export const FLOORS: readonly { name: string; keys: readonly string[] }[] = [
  { name: 'Pre-sale', keys: ['rfp-response/v1', 'commercial/v1'] },
  { name: 'Planning', keys: ['engagement/v1', 'planning/v1'] },
  { name: 'Release', keys: ['delivery-release/v1', 'delivery-go-live/v1'] },
  { name: 'Closing', keys: ['delivery-hypercare/v1', 'delivery-handover/v1', 'delivery-archive/v1', 'delivery-closure/v1'] },
  { name: 'Invoices', keys: ['pmo-finance/v1'] },
  { name: 'Month-end', keys: ['finance-accounts/v1', 'finance-schedules/v1', 'finance-ppe/v1'] },
  { name: 'Cash and BU', keys: ['finance-forecast/v1', 'finance-bu/v1', 'finance-ledger/v1'] },
  { name: 'Payroll', keys: ['finance-payroll/v1'] },
];

const FLOOR_OF = new Map(FLOORS.flatMap((f) => f.keys.map((k) => [k, f.name] as const)));

/** The floor a line key stands on; any key not on the map is on "Other lines". */
export const floorOf = (key: string) => FLOOR_OF.get(key) ?? OTHER_FLOOR;
