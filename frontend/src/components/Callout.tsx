'use client';

// Callout (design/system/project/components/Callout, CMP-24): a tinted box with a leading icon that names its kind;
// no side bar. Info and warning are plain text in the page (no live role). A problem or success shown in response
// to an action is announced (`announce`): problem as role="alert", success as role="status"; a problem that is
// part of the page as it loads is not (D-92: alert only in response to an action). `focusOnShow` moves focus to
// it when it appears (after a failed submit).
import { useEffect, useRef, type ReactNode } from 'react';

import { Icon, type IconName } from './Icon';
import { cx } from './internal';

export type CalloutKind = 'info' | 'warning' | 'problem' | 'success';

const ICON: Record<CalloutKind, IconName> = { info: 'info', warning: 'warn', problem: 'warn', success: 'ok' };
const ROLE: Partial<Record<CalloutKind, 'alert' | 'status'>> = { problem: 'alert', success: 'status' };

export function Callout({ kind, children, announce = true, focusOnShow = false, className, id }: {
  kind: CalloutKind;
  /** Problem and success only: false when the callout is part of the page as loaded, not a response to an action. */
  announce?: boolean;
  children: ReactNode;
  focusOnShow?: boolean;
  className?: string;
  id?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focusOnShow) ref.current?.focus();
  }, [focusOnShow]);
  return (
    <div ref={ref} id={id} className={cx('psl-callout', `psl-callout--${kind}`, className)} role={announce ? ROLE[kind] : undefined} tabIndex={focusOnShow ? -1 : undefined}>
      <Icon name={ICON[kind]} />
      <span>{children}</span>
    </div>
  );
}
