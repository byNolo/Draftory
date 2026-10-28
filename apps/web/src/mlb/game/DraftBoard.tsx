import {
  DraftEngine,
  POSITIONS,
  REROLL_LIMIT,
  type DraftState,
} from '../draft/engine';
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
        <strong>{draft.config.budget - draft.remainingBudget} credits</strong>
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
  onReroll,
}: RosterProps & {
  stats: Record<string, HistoricalBatting>;
  busy: boolean;
  onPick: (id: string) => void;
  onReroll: () => void;
}) {
  const remaining = REROLL_LIMIT - (draft.rerollRounds?.length ?? 0);
  const available = engine.canReroll(draft);
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
              <div className="offer-statistics">
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
                      <b>{s.hr ?? '—'}</b> HR <span>·</span>{' '}
                      <b>{s.pa ?? '—'}</b> historical PA
                    </p>
                    <details>
                      <summary>Historical details</summary>
                      <p>
                        Historical PA is the sample behind this profile. Every
                        selected hitter currently plays a full simulated season;
                        historical PA is not an availability limit.
                      </p>
                      <p>
                        {s.teams.join(' / ')} · {engine.catalog.year}. All
                        batting stints combined once. OBP includes sacrifice
                        flies in its denominator. Unknown statistics display —.
                      </p>
                      <p>
                        After this pick: {draft.remainingBudget - p.price}{' '}
                        credits for {8 - draft.history.length} remaining
                        positions.
                      </p>
                    </details>
                  </>
                ) : (
                  <p className="card-loading">Loading historical statistics…</p>
                )}
              </div>
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
      <div
        className={`offer-actions ${available ? 'reroll-active' : ''}`}
        role="group"
        aria-label="Reroll current offers"
      >
        <div className="reroll-description" id="reroll-help">
          <strong>
            {remaining === 0
              ? 'All three rerolls used'
              : 'Want different players?'}
          </strong>
          <p>
            {remaining === 0
              ? 'Choose from these offers to keep building your lineup.'
              : !available
                ? 'Too few affordable alternatives to replace every player. Your rerolls are saved.'
                : `Replace all ${draft.offers.length} offers. Keep your picks and credits.`}
          </p>
        </div>
        <button
          className="reroll-button"
          disabled={busy || !available}
          onClick={onReroll}
          aria-describedby="reroll-help"
          aria-label={`Reroll players (${remaining} left)`}
        >
          <svg
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            aria-hidden="true"
          >
            <path
              d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M18 18a8 8 0 0 1-13-3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>Reroll players</span>
          <span className="reroll-count">{remaining} left</span>
        </button>
      </div>
      <p className="muted offer-note">
        Every offered player leaves enough credits to complete your lineup.
        Three free rerolls per draft.
      </p>
    </>
  );
}
