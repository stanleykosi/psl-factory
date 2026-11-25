// F-136: the client's response and SOW signature (SCR-16) on the live work item. Turns GET /projects/{case_id}/commercial-response
// into the Section objects the workspace renderer draws and describes the three writes of POST on the same route. Presentation only:
// what is offered comes from the response (can_record, the served lists), never from a rule here. A value the response does not give
// reads Not recorded, never a guess. Proofs are chosen from the served lists; nothing is uploaded.
// HELD, not drawn: uploading a proof file (the person picks from files already on the project), the "who may sign" rule (the
// server's own answer), the signature contract's method words (typed by the person from the proof), and a finding that holds the
// item (the desk read carries none; the work item's own blocker line is drawn by the page).
import { formatDayTime } from '@/components';
import type { paths } from '@/api/live-schema';
import { makeCommand, type CommandDescriptor } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type CommercialDesk = Get<'/api/v1/projects/{case_id}/commercial-response'>;
export type Signed = CommercialDesk['responses'][number];

export const NOT_RECORDED = 'Not recorded';
export const OUTCOMES: Record<string, string> = { signed: 'Signed', changes_requested: 'Asked for changes', declined: 'Declined' };
export const CHANNELS: Record<string, string> = { email: 'Email', whatsapp: 'WhatsApp', call: 'A phone call', portal: 'The client portal', in_person: 'In person', other: 'Another way' };

const sizeWords = (bytes: number) => (bytes >= 1_000_000 ? `${Math.round(bytes / 100_000) / 10} MB` : `${Math.max(1, Math.round(bytes / 1000))} KB`);
const fileLine = (f: CommercialDesk['owned_files'][number]) => `${f.name} (${sizeWords(f.size)})`;
const sentence = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : NOT_RECORDED);

/** The signed response the signature step is about: the newest response of kind signed, as the response lists them. */
export const signedResponse = (d: CommercialDesk): Signed | null => d.responses.find((r) => r.kind === 'signed') ?? null;
/** Signing is offered once a signed response is on file and the server has served the choices that only a person who may sign gets. */
export const signingOpen = (d: CommercialDesk) => signedResponse(d) !== null && d.requirements.length > 0 && d.signature_proofs.length > 0 && !d.adoption?.current;

export function commercialSections(d: CommercialDesk): Section[] {
  const out: Section[] = [];
  out.push({
    key: 'tosign',
    kind: 'facts',
    title: 'What is to be signed',
    items: [
      { id: 'version', label: 'Current statement of work', value: d.current_revision_id === null ? NOT_RECORDED : `Version record ${d.current_revision_id}` },
      { id: 'sent', label: 'Sent to the client', value: d.receipts.length === 0 ? 'Nothing sent yet' : `${d.receipts.length} ${d.receipts.length === 1 ? 'delivery' : 'deliveries'}` },
    ],
  });
  if (d.receipts.length > 0) out.push({ key: 'deliveries', kind: 'text', title: 'What the client was sent', items: d.receipts.map((r) => ({ id: String(r.id), text: r.label })) });

  const w = d.witness;
  if (w) {
    out.push({
      key: 'response',
      kind: 'facts',
      title: 'The client’s response',
      items: [
        { id: 'client', label: 'Answered by', value: w.client_name },
        { id: 'outcome', label: 'Answer', tag: { label: OUTCOMES[w.outcome] ?? w.outcome, tone: w.outcome === 'signed' ? 'verified' : 'neutral' } },
        { id: 'when', label: 'Answered on', value: formatDayTime(w.responded_at) },
        { id: 'via', label: 'How the answer reached us', value: w.received_via ? (CHANNELS[w.received_via] ?? w.received_via) : NOT_RECORDED },
      ],
    });
  } else {
    out.push({ key: 'response', kind: 'text', title: 'The client’s response', items: [{ id: 'none', text: 'No response from the client has been recorded yet.' }] });
  }

  const files: Item[] = [
    ...d.witness_files.map((f) => ({ id: `on-${f.id}`, text: `On the recorded response: ${fileLine(f)}` })),
    ...d.owned_files.map((f) => ({ id: `own-${f.id}`, text: `Available to attach: ${fileLine(f)}` })),
  ];
  out.push({ key: 'proofs', kind: 'text', title: 'Proof files on file', items: files.length > 0 ? files : [{ id: 'none', text: 'No proof file is on file for this project yet.' }] });

  const p = d.packet;
  const a = d.adoption;
  out.push({
    key: 'signing',
    kind: 'facts',
    title: 'Signatures and the signed baseline',
    items: [
      { id: 'sow', label: 'Statement of work signature', value: p ? sentence(p.sow) : 'Not captured yet' },
      { id: 'prd', label: 'Requirements signature', value: p ? sentence(p.prd) : 'Not captured yet' },
      ...(p ? [{ id: 'authenticity', label: 'Checked by a signature provider', value: p.authenticity.startsWith('Not verified') ? 'No' : sentence(p.authenticity) }] : []),
      { id: 'baseline', label: 'Signed baseline', ...(a === null ? { value: 'Not adopted yet' } : a.current ? { tag: { label: 'Adopted', tone: 'verified' as const } } : { tag: { label: 'Adopted earlier, not current', tone: 'neutral' as const } }) },
    ],
  });
  out.push({
    key: 'who',
    kind: 'facts',
    title: 'Who may record it',
    items: [{ id: 'record', label: 'Recording the client’s response', value: d.can_record ? 'You may record it' : 'Not open to you' }],
  });
  return out;
}

const NO_REVISION = 'There is no current version of the statement of work yet.';

/** The three writes of POST /projects/{case_id}/commercial-response. Each says why it cannot be pressed; the server still decides. */
export function commercialCommands(d: CommercialDesk, ctx: { caseId: string }): CommandDescriptor[] {
  const url = `/api/v1/projects/${ctx.caseId}/commercial-response`;
  const tokens = { case_revision: d.case_revision };
  const signed = signedResponse(d);
  const record: string | undefined = !d.can_record
    ? 'Recording the client’s response isn’t open to you.'
    : d.current_revision_id === null
      ? NO_REVISION
      : d.receipts.length === 0
        ? 'Nothing has been sent to the client yet.'
        : d.owned_files.length === 0
          ? 'There is no proof file on file to choose from yet.'
          : undefined;
  const sign: string | undefined = !signed ? 'The client’s signed response must be recorded first.' : d.requirements.length === 0 ? 'There is no requirements document on file to sign.' : d.signature_proofs.length === 0 ? 'There is no signature proof on file to choose from.' : d.parties.length === 0 ? 'No signer is named for this project yet.' : undefined;
  const adopt: string | undefined = !signed ? 'The client’s signed response must be recorded first.' : d.packet === null ? 'Record the signatures first.' : undefined;
  return [
    makeCommand({
      id: 'commercial-response.witness',
      label: 'Record the client’s response',
      url,
      tokens,
      keyField: 'operation_key',
      fixed: { revision_id: d.current_revision_id, predecessor_id: d.witness?.id ?? null },
      ...(record ? { disabledReason: record } : {}),
      successStatuses: [201],
    }),
    makeCommand({
      id: 'commercial-response.signatures',
      label: 'Record the signatures',
      url,
      tokens,
      keyField: 'operation_key',
      fixed: { response_id: signed?.id ?? null, predecessor_id: d.packet?.id ?? null },
      ...(sign ? { disabledReason: sign } : {}),
      successStatuses: [201],
    }),
    makeCommand({
      id: 'commercial-response.adopt',
      label: 'Adopt the signed baseline',
      url,
      tokens,
      fixed: { response_id: signed?.id ?? null },
      ...(adopt ? { disabledReason: adopt } : {}),
      successStatuses: [201],
    }),
  ];
}
