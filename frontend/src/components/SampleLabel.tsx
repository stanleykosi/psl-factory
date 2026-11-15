// SampleLabel (design/system/project/components/SampleLabel, CMP-16): sample, test and mock content carries its
// label in place, every time it appears; amber with a dashed edge so it never reads as a state. Whether a frame is
// sample data is the shell's decision (src/shell/SampleLabel.tsx); this is only the label.
export type SampleKind = 'sample' | 'test' | 'mock';

const TEXT: Record<SampleKind, string> = { sample: 'SAMPLE DATA', test: 'TEST TEMPLATE', mock: 'MOCK DELIVERY' };

export function SampleLabel({ kind = 'sample' }: { kind?: SampleKind }) {
  return <span className="psl-sample">{TEXT[kind]}</span>;
}
