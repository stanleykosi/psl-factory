// SourceTag (design/system/project/components/SourceTag): the record an answer or a step used, its type and
// reference in mono, outlined in action blue; a link when the person can open it. Restricted (dashed, ink-muted, a
// lock): the record exists but this person cannot open it, so only the word "Restricted" is drawn and nothing of the
// record (no label, reference or link) is passed in or drawn.
import NextLink from 'next/link';

import { Icon } from './Icon';
import { cx } from './internal';

export type SourceTagProps = { label: string; href?: string; restricted?: false; className?: string } | { restricted: true; className?: string; label?: never; href?: never };

export function SourceTag(props: SourceTagProps) {
  if (props.restricted) {
    return (
      <span className={cx('cmp-source cmp-source--restricted', props.className)}>
        <span className="cmp-source__box">
          <Icon name="lock" />
          Restricted
        </span>
      </span>
    );
  }
  const { label, href, className } = props;
  if (!href) {
    return (
      <span className={cx('cmp-source', className)}>
        <span className="cmp-source__box">{label}</span>
      </span>
    );
  }
  return (
    <NextLink href={href} className={cx('cmp-source cmp-source--link', className)}>
      <span className="cmp-source__box">{label}</span>
    </NextLink>
  );
}
