// SCR-16 recorded RFP outcome: the result heading from rfp_outcome.recorded. A pending or unknown outcome can be
// recorded again ("Record the outcome" shows the form on this route) while the block still offers results.
import type { RecordedOutcome, RfpOutcome } from './contract';
import { recordedHeading } from './labels';

/** `title`: h1 on the phone; h2 under the desktop frame (the frame holds the h1); none when the page header already shows it. */
export function RecordedView({ outcome, recorded, title, onReopen }: {
  outcome: RfpOutcome;
  recorded: RecordedOutcome;
  title: 'h1' | 'h2' | 'none';
  onReopen: () => void;
}) {
  const heading = recordedHeading(recorded.result);
  const again = (recorded.result === 'pending' || recorded.result === 'unknown') && outcome.results.length > 0;
  return (
    <div className="rfp-recorded">
      {title === 'h1' && <h1 className="shell-title">{heading}</h1>}
      {title === 'h2' && <h2 className="rfp-recorded__title">{heading}</h2>}
      {again && (
        <p className="rfp-recorded__again">
          <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg" onClick={onReopen}>
            Record the outcome
          </button>
        </p>
      )}
    </div>
  );
}
