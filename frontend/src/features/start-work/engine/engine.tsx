'use client';

// F-92: the form engine. `engineForm(config)` makes a registry entry (`LineForm`) whose fields, required checks, body and 422 map come
// from the line's served `request_schema` (read from `GET /lines` each time); the chooser, project picker and start state machine
// stay F-86's. A line whose schema the engine cannot fully draw is not available here (`available`), never drawn in part.
import { useMemo } from 'react';

import type { FieldValue } from '../intake';
import type { LineForm, LineFormProps } from '../lines';
import type { Line, LineOption } from '../types';
import { fileOf, jsonBody, missingOf, targetOf, textOf } from './body';
import type { EngineConfig } from './config';
import { ChoiceControl, FileControl, NO_ESCALATIONS, RecordControl, TextControl, WaitingRecord, CHOOSE_PROJECT_FIRST } from './controls';
import { escalationSource } from './escalations';
import { isMinutes, minutesParts, sendMinutes } from './minutes';
import { activeFields, planOf, type EngineField, type Plan } from './plan';

const planFor = (config: EngineConfig, line: Line | undefined) => (line ? planOf(config, line.request_schema) : 'unsupported');
const optionOf = (value: FieldValue | undefined) => (value && typeof value === 'object' && 'value' in value ? (value as LineOption) : undefined);

/** The controls that depend on `name`, at any depth. */
function dependents(plan: Plan, name: string): string[] {
  const direct = plan.fields.filter((f) => f.parent === name).map((f) => f.name);
  return [...direct, ...direct.flatMap((child) => dependents(plan, child))];
}

function Fields({ plan, values, setValue, errors, readOnly, caseId, project, onRevision, line }: LineFormProps & { plan: Plan }) {
  const escalations = useMemo(() => (project ? escalationSource(project.case_id, project.workflow_intake_url !== null) : undefined), [project]);
  const labelOf = (name: string) => plan.fields.find((f) => f.name === name)?.label ?? name;

  function control(field: EngineField) {
    const error = errors[field.name];
    if (field.kind === 'choice') {
      return <ChoiceControl key={field.name} field={field} value={typeof values[field.name] === 'string' ? (values[field.name] as string) : undefined} onChange={(v) => setValue(field.name, v)} disabled={readOnly} error={error} />;
    }
    if (field.kind === 'text') {
      return <TextControl key={field.name} name={field.name} label={field.label} required={field.required} maxLength={field.maxLength} date={field.date} value={textOf(values[field.name])} onChange={(v) => setValue(field.name, v)} disabled={readOnly} error={error} />;
    }
    if (!caseId) return <WaitingRecord key={field.name} field={field} why={CHOOSE_PROJECT_FIRST} />;
    const parentOption = field.parent ? optionOf(values[field.parent]) : undefined;
    if (field.parent && !parentOption) return <WaitingRecord key={field.name} field={field} why={`Choose ${labelOf(field.parent).toLowerCase()} first.`} />;
    const own = field.source?.kind === 'escalations' && escalations ? { source: escalations, emptyText: NO_ESCALATIONS } : undefined;
    return (
      <RecordControl
        key={field.name}
        field={field}
        caseId={caseId}
        lineKey={line.key}
        parentId={parentOption ? Number.parseInt(parentOption.value, 10) : undefined}
        value={optionOf(values[field.name])}
        onChange={(next) => {
          setValue(field.name, next);
          // A changed record clears the controls that were chosen under it.
          for (const child of dependents(plan, field.name)) setValue(child, undefined);
        }}
        onRevision={onRevision}
        list={own}
        disabled={readOnly}
        error={error}
      />
    );
  }

  return (
    <>
      {activeFields(plan, values).map(control)}
      {plan.upload && <FileControl name={plan.upload.name} label={plan.upload.label} value={fileOf(values[plan.upload.name])} onChange={(file) => setValue(plan.upload!.name, file ?? undefined)} disabledReason={caseId ? undefined : CHOOSE_PROJECT_FIRST} error={errors[plan.upload.name]} />}
      {plan.reference && <TextControl name="reference" label="Reference" required maxLength={plan.reference.maxLength} value={textOf(values.reference)} onChange={(v) => setValue('reference', v)} disabled={readOnly} error={errors.reference} />}
    </>
  );
}

export function engineForm(config: EngineConfig): LineForm {
  const planned = (line: Line | undefined) => {
    const plan = planFor(config, line);
    if (plan === 'unsupported') throw new Error(`${config.key}: the served request_schema is not one this form can build`);
    return plan;
  };
  return {
    key: config.key,
    startLabel: config.startLabel,
    drawerTitle: config.drawerTitle,
    // What belongs to one project: the record choices and the file.
    projectBound: [...Object.keys(config.sources), ...(config.upload ? [config.upload.name] : [])],
    available: (line) => planFor(config, line) !== 'unsupported',
    Form(props) {
      const plan = planFor(config, props.line);
      return plan === 'unsupported' ? null : <Fields {...props} plan={plan} />;
    },
    missing: (values, line) => {
      const plan = planFor(config, line);
      return plan === 'unsupported' ? [] : missingOf(plan, values);
    },
    buildBody(values, ctx, line) {
      const plan = planned(line);
      return plan.upload ? minutesParts(plan, values, ctx) : jsonBody(config.key, plan, values, ctx);
    },
    send: config.upload ? (prepared) => (isMinutes(prepared) ? sendMinutes(prepared) : Promise.reject(new Error('Not a minutes start'))) : undefined,
    target: (name, line) => {
      const plan = planFor(config, line);
      return plan === 'unsupported' ? undefined : targetOf(plan, name);
    },
  };
}
