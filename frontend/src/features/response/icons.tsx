// The success and info callout icons drawn on the SCR-16 boards (the frame's icons.tsx has the warning one).
export function CheckIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18">
      <circle cx="9" cy="9" r="7.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.6 9.2l2.3 2.3 4.4-4.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

export function InfoIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18">
      <circle cx="9" cy="9" r="7.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 8v4.6" stroke="currentColor" strokeWidth="1.8" />
      <rect x="8.1" y="4.8" width="1.8" height="1.8" fill="currentColor" />
    </svg>
  );
}
