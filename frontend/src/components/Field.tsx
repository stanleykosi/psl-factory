// The field frame every input shares (TextField, TextArea, Select, DateField, MoneyField): the label above,
// "(optional)" where it applies, and under the control either the hint or, replacing it, the error with its
// warning icon. Not a design-system component of its own; the components import it.
import { useId, type ReactNode } from 'react';

import { Icon } from './Icon';

export type FieldText = {
  label: ReactNode;
  optional?: boolean;
  hint?: ReactNode;
  /** Replaces the hint and turns the border signal. */
  error?: ReactNode;
};

/** Ids for the control, its label and whichever message shows, and the control's aria-describedby. */
export function useFieldIds(id: string | undefined, { hint, error }: Pick<FieldText, 'hint' | 'error'>) {
  const auto = useId();
  const control = id ?? `${auto}-control`;
  const message = `${control}-message`;
  return { control, label: `${control}-label`, message, describedBy: error || hint ? message : undefined };
}

/** `hidden`: the label stays for assistive technology where the screen's own layout already names the field. */
export function FieldLabel({ htmlFor, id, label, optional, hidden = false }: { htmlFor?: string; id: string; label: ReactNode; optional?: boolean; hidden?: boolean }) {
  const text = (
    <>
      {label}
      {optional && (
        <>
          {' '}
          <span className="psl-opt">(optional)</span>
        </>
      )}
    </>
  );
  return htmlFor ? (
    <label className={hidden ? 'psl-label cmp-sr' : 'psl-label'} htmlFor={htmlFor} id={id}>
      {text}
    </label>
  ) : (
    <span className={hidden ? 'psl-label cmp-sr' : 'psl-label'} id={id}>
      {text}
    </span>
  );
}

export function FieldMessage({ id, hint, error }: { id: string; hint?: ReactNode; error?: ReactNode }) {
  if (error) {
    return (
      <span className="psl-error" id={id}>
        <Icon name="warn" />
        <span>{error}</span>
      </span>
    );
  }
  if (!hint) return null;
  return (
    <span className="psl-hint" id={id}>
      {hint}
    </span>
  );
}
