'use client';

// The two fields of a new password, shared by account set-up and password reset. The checks here are only the three
// the page can make without the server: empty, empty again, and the two differ. Length and strength are the server's.
import type { Ref } from 'react';

import { TextField, useIsPhone } from '@/components';

export type NewPasswordProblems = { password?: string; confirm?: string };

/** The messages for the two fields, or null when nothing is wrong. The first field named is the one to focus. */
export function newPasswordProblems(password: string, confirm: string): NewPasswordProblems | null {
  if (password === '') return { password: 'Enter a new password.' };
  if (confirm === '') return { confirm: 'Enter the new password again.' };
  if (password !== confirm) return { confirm: 'The two passwords don’t match.' };
  return null;
}

export function NewPasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
  errors = {},
  hint,
  passwordRef,
  confirmRef,
}: {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
  errors?: NewPasswordProblems;
  /** A fixed line under New password, linked to the field; none when not given. */
  hint?: string;
  passwordRef?: Ref<HTMLInputElement>;
  confirmRef?: Ref<HTMLInputElement>;
}) {
  const phone = useIsPhone();
  return (
    <>
      <TextField
        ref={passwordRef}
        label="New password"
        name="new-password"
        type="password"
        autoComplete="new-password"
        maxLength={128}
        phone={phone}
        value={password}
        hint={hint}
        error={errors.password}
        onChange={(event) => onPassword(event.target.value)}
      />
      <TextField
        ref={confirmRef}
        label="Confirm new password"
        name="confirm-password"
        type="password"
        autoComplete="new-password"
        maxLength={128}
        phone={phone}
        value={confirm}
        error={errors.confirm}
        onChange={(event) => onConfirm(event.target.value)}
      />
    </>
  );
}
