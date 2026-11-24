import { describe, expect, it } from 'vitest';

import { ApiError } from '@/api/errors';
import { failureOf, generalMessage } from '@/features/retrospective/failure';

const invalid = (message: string, fields: { name: string; message: string }[]) => failureOf(new ApiError(422, 'invalid', 'invalid_input', message, fields));
const SAVE_FORM = ['reference', 'occurredAt', 'boxes', 'evidence'];
const ACTION_FORM = ['description', 'ownerId', 'dueAt', 'reason', 'evidence', 'reference'];

describe('a 422 the page cannot place on a field', () => {
  it('says the API message when no field is named (action create)', () => {
    expect(generalMessage(invalid('The action could not be created.', []), ACTION_FORM)).toBe('The action could not be created.');
  });
  it('says the message of a field the form has no control for (save)', () => {
    const f = invalid('Check the details.', [{ name: 'participant_ids', message: 'Pick people on the project.' }]);
    expect(generalMessage(f, SAVE_FORM)).toBe('Pick people on the project.');
    expect(f.message).not.toContain('highlighted');
  });
  it('says an owner message on the save form, where there is no owner control, and nothing on the action form, which has one', () => {
    const f = invalid('Check.', [{ name: 'owner_id', message: 'Owner is not on the project.' }]);
    expect(generalMessage(f, SAVE_FORM)).toBe('Owner is not on the project.');
    expect(generalMessage(f, ACTION_FORM)).toBeNull();
  });
  it('is silent when every named field has its control', () => {
    expect(generalMessage(invalid('Check.', [{ name: 'reference', message: 'Exists.' }]), SAVE_FORM)).toBeNull();
  });
  it('joins several loose messages and is null for other failure kinds', () => {
    const f = invalid('x', [{ name: 'a', message: 'One.' }, { name: 'b', message: 'Two.' }]);
    expect(generalMessage(f, SAVE_FORM)).toBe('One. Two.');
    expect(generalMessage(failureOf(new ApiError(409, 'stale', 'stale_revision', 'x')), SAVE_FORM)).toBeNull();
    expect(generalMessage(null, SAVE_FORM)).toBeNull();
  });
});
