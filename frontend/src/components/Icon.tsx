// Icon (design/system/project/components/Icon): 2px stroke icons with square caps, 18px on the 20px grid, in the
// text colour around them. Always decorative: icons support words; an icon button names itself with aria-label.
import type { ReactNode } from 'react';

import { cx } from './internal';

const fill = { fill: 'currentColor', stroke: 'none' } as const;

const PATHS = {
  plus: <path d="M9 2v14M2 9h14" />,
  chev: <path d="M3.5 6.5L9 12l5.5-5.5" />,
  'chev-r': <path d="M6.5 3.5L12 9l-5.5 5.5" />,
  back: <path d="M11 3.5L5.5 9l5.5 5.5" />,
  search: (
    <>
      <circle cx="7.5" cy="7.5" r="5.5" />
      <path d="M11.8 11.8L16 16" />
    </>
  ),
  filter: <path d="M2 3h14l-5.5 6.5V15l-3 1.5V9.5z" strokeLinejoin="round" />,
  close: <path d="M4 4l10 10M14 4L4 14" />,
  check: <path d="M3 9.5l4 4 8-9" />,
  warn: (
    <>
      <path d="M9 2L16.5 15.5H1.5Z" strokeLinejoin="round" strokeLinecap="butt" />
      <path d="M9 7v3.6" />
      <rect x="8.1" y="12" width="1.8" height="1.8" {...fill} />
    </>
  ),
  info: (
    <>
      <circle cx="9" cy="9" r="7.2" />
      <path d="M9 8v4.6" />
      <rect x="8.1" y="4.8" width="1.8" height="1.8" {...fill} />
    </>
  ),
  ok: (
    <>
      <circle cx="9" cy="9" r="7.2" />
      <path d="M5.6 9.2l2.3 2.3 4.4-4.6" />
    </>
  ),
  cal: (
    <>
      <rect x="2" y="3.5" width="14" height="12.5" />
      <path d="M2 7.5h14M6 1.5v3M12 1.5v3" />
    </>
  ),
  clip: <path d="M12.5 5.5L6.5 11.5a1.8 1.8 0 0 0 2.5 2.5l6.5-6.5a3.5 3.5 0 0 0-5-5L4 9a5 5 0 0 0 7 7l4.5-4.5" strokeLinecap="butt" />,
  upload: <path d="M9 12V2.5M5 6l4-4 4 4M2.5 12.5v3.5h13v-3.5" />,
  camera: <path d="M2.5 5.5h3l1.5-2h4l1.5 2h3v9h-13zM9 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" />,
  more: (
    <>
      <rect x="2.5" y="8" width="2" height="2" {...fill} />
      <rect x="8" y="8" width="2" height="2" {...fill} />
      <rect x="13.5" y="8" width="2" height="2" {...fill} />
    </>
  ),
  menu: <path d="M2 4.5h14M2 9h14M2 13.5h14" />,
  send: <path d="M2.5 9h11M9 4l5 5-5 5" />,
  doc: (
    <>
      <path d="M4 1.5h7l3 3v12H4z" strokeLinejoin="miter" />
      <path d="M7 8h5M7 11h5M7 14h3" />
    </>
  ),
  lock: (
    <>
      <rect x="3.5" y="8" width="11" height="8" />
      <path d="M6 8V5.5a3 3 0 0 1 6 0V8" />
    </>
  ),
  external: <path d="M10 2.5h5.5V8M15.5 2.5L8 10M13 11v4.5H2.5V5H7" />,
  sort: <path d="M5 7l4-4 4 4M5 11l4 4 4-4" />,
  down: <path d="M9 3v12M4.5 10.5L9 15l4.5-4.5" />,
  bell: <path d="M4 13V8a5 5 0 0 1 10 0v5l1.5 1.5h-13zM7.5 16.5h3" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof PATHS;
export const ICON_NAMES = Object.keys(PATHS) as IconName[];

// The set draws sort and down at 14px; every other icon at 18px.
const SMALL = new Set<IconName>(['sort', 'down']);

export function Icon({ name, className }: { name: IconName; className?: string }) {
  const size = SMALL.has(name) ? 14 : 18;
  return (
    <svg
      className={cx('psl-icon', className)}
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="square"
    >
      {PATHS[name]}
    </svg>
  );
}
