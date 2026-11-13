// Stroke icons as drawn in the design system (Icon README: 2px, square caps, 18px).
export function MenuIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <path d="M2 4.5h14M2 9h14M2 13.5h14" />
    </svg>
  );
}

export function WarningIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <path d="M9 2L16.5 15.5H1.5Z" strokeLinejoin="round" strokeLinecap="butt" />
      <path d="M9 7v3.6" />
      <rect x="8.1" y="12" width="1.8" height="1.8" fill="currentColor" stroke="none" />
    </svg>
  );
}
