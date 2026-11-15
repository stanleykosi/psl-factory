import { frameIsSample, showSampleLabel } from './sample';

/** The one SAMPLE DATA tag. `show` defaults to the frame's sample state; records pass their own `sample` flag. */
export function SampleLabel({ show = frameIsSample() }: { show?: boolean }) {
  return showSampleLabel() && show ? <span className="psl-sample">SAMPLE DATA</span> : null;
}
