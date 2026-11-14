import { SHOW_SAMPLE_LABEL } from './sample';

export function SampleLabel() {
  return SHOW_SAMPLE_LABEL ? <span className="psl-sample">SAMPLE DATA</span> : null;
}
