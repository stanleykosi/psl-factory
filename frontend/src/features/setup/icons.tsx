// Stroke icons as drawn on the SCR-13 boards (2px, 18px), beside the frame's WarningIcon.
export function InfoIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="9" cy="9" r="7.2" />
      <path d="M9 8v4.6" />
      <rect x="8.1" y="4.8" width="1.8" height="1.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function PaperclipIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12.5 5.5L6.5 11.5a1.8 1.8 0 0 0 2.5 2.5l6.5-6.5a3.5 3.5 0 0 0-5-5L4 9a5 5 0 0 0 7 7l4.5-4.5" />
    </svg>
  );
}

export function TickIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <path d="M3 9.5l4 4L15 5" />
    </svg>
  );
}
