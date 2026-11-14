// Stroke icons for the list toolbar, as drawn on SCR-01 (Icon README: 2px, square caps, 18px).
export function SearchIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <circle cx="7.5" cy="7.5" r="5.5" />
      <path d="M11.5 11.5L16 16" />
    </svg>
  );
}

export function FilterIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
      <path d="M2 3h14l-5.5 6.5V15l-3 1.5V9.5z" />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <path d="M4 4l10 10M14 4L4 14" />
    </svg>
  );
}
