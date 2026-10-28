import { DraftEngine, POSITIONS, type DraftState } from '../draft/engine';
import { rate, type HistoricalBatting } from './batting';
type RosterProps = { engine: DraftEngine; draft: DraftState };
export function Roster({ engine, draft }: RosterProps) {
  return (
    <aside className="roster" aria-label="Your lineup">
      <div className="roster-title">
        <h2>
          {draft.status === 'complete' ? 'Fielding assignments' : 'Your lineup'}
        </h2>
        <span>{draft.history.length} / 9</span>
      </div>
      <ol>
        {POSITIONS.map((pos) => {
          const p = draft.history.find((h) => h.position === pos);
          return (
            <li key={pos}>
              <span className="roster-pos">{pos}</span>
              <span>
                {p ? engine.player(p.playerId).name : 'Open position'}
              </span>
              <b>{p ? p.price : '—'}</b>
            </li>
          );
        })}
      </ol>
      <div className="roster-total">
        <span>Total spent</span>
        <strong>{90 - draft.remainingBudget} credits</strong>
      </div>
    </aside>
  );
}
export function OfferCards({
  engine,
  draft,
  stats,
  busy,
  onPick,
}: RosterProps & {
  stats: Record<string, HistoricalBatting>;
  busy: boolean;
  onPick: (id: string) => void;
}) {
  return (
    <>
      <p className="muted">
        2024 historical batting · Prices are fictional draft credits
      </p>
      <div className="offers">
        {draft.offers.map((id) => {
          const p = engine.player(id),
            s = stats[id];
          return (
            <article className="offer" key={id}>
              <div className="card-top">
                <span className="position-tag">
                  {draft.config.order[draft.history.length]}
                </span>
                <div className="price">
                  <strong>{p.price}</strong>
                  <span>credits</span>
                </div>
              </div>
              <h2>{p.name}</h2>
              <p className="positions">Eligible: {p.positions.join(' · ')}</p>
              {s ? (
                <>
                  <dl className="slash">
                    <div>
                      <dt>AVG</dt>
                      <dd>{rate(s.avg)}</dd>
                    </div>
                    <div>
                      <dt>OBP</dt>
                      <dd>{rate(s.obp)}</dd>
                    </div>
                    <div>
                      <dt>SLG</dt>
                      <dd>{rate(s.slg)}</dd>
                    </div>
                  </dl>
                  <p className="count-stats">
                    <b>{s.hr ?? '—'}</b> HR <span>·</span> <b>{s.pa ?? '—'}</b>{' '}
                    PA
                  </p>
                  <details>
                    <summary>Historical details</summary>
                    <p>
                      {s.teams.join(' / ')} · {engine.catalog.year}. All batting
                      stints combined once. OBP includes sacrifice flies in its
                      denominator. Unknown statistics display —.
                    </p>
                    <p>
                      After this pick: {draft.remainingBudget - p.price} credits
                      for {8 - draft.history.length} remaining positions.
                    </p>
                  </details>
                </>
              ) : (
                <p className="card-loading">Loading historical statistics…</p>
              )}
              <button
                className="pick-button"
                disabled={busy || !s}
                onClick={() => onPick(id)}
              >
                Draft {p.name}
              </button>
            </article>
          );
        })}
      </div>
      <p className="muted">
        {draft.offers.length} safe choices · No rerolls. Every choice preserves
        an affordable full lineup.
      </p>
    </>
  );
}
