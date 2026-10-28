import { useEffect, useRef, useState } from 'react';
import type { SeasonDashboard as Dashboard } from '../../workers/protocol';

export type OpponentLabel = { id: string; name: string; abbreviation: string };
export default function SeasonDashboard({
  dashboard: d,
  opponents,
}: {
  dashboard: Dashboard;
  opponents: OpponentLabel[];
}) {
  const [opponent, setOpponent] = useState('all');
  const [outcome, setOutcome] = useState('all');
  const [selected, setSelected] = useState<number>();
  const detail = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (selected !== undefined) detail.current?.focus();
  }, [selected]);
  const names = new Map(opponents.map((t) => [t.id, t]));
  const label = (id: string) => names.get(id)?.name ?? id;
  const abbreviation = (id: string) => names.get(id)?.abbreviation ?? id;
  const filtered = d.games.filter(
    (g) =>
      (opponent === 'all' || g.opponentId === opponent) &&
      (outcome === 'all' || g.won === (outcome === 'wins')),
  );
  const game = d.games.find((g) => g.gameNumber === selected);
  const last = d.games.at(-1)!;
  const path =
    'M 30 155 ' +
    d.games
      .map(
        (g) =>
          `L ${30 + (g.gameNumber / d.games.length) * 640} ${155 - (g.wins / d.games.length) * 135}`,
      )
      .join(' ');
  return (
    <>
      <section className="dashboard-section" aria-labelledby="trend-title">
        <h3 id="trend-title">Season progress</h3>
        <p className="muted">
          Cumulative wins · finished {last.wins}–{last.losses}. The dashed line
          is a .500 pace. Each game's record is also listed below.
        </p>
        <svg
          className="season-chart"
          viewBox="0 0 700 185"
          role="img"
          aria-labelledby="wins-chart-title wins-chart-description"
        >
          <title id="wins-chart-title">Cumulative wins across the season</title>
          <desc id="wins-chart-description">
            Wins increase from zero to {last.wins} over {d.games.length} games.
            Full cumulative records appear in the game results table.
          </desc>
          {[0, 81, 162].map((n) => (
            <g key={n}>
              <line
                x1="30"
                x2="670"
                y1={155 - (n / 162) * 135}
                y2={155 - (n / 162) * 135}
                stroke="#d1d8c5"
              />
              <text x="3" y={159 - (n / 162) * 135}>
                {n}
              </text>
            </g>
          ))}
          <path
            d="M 30 155 L 670 87.5"
            stroke="#89988d"
            strokeDasharray="6 5"
            fill="none"
            strokeWidth="2"
          />
          <path d={path} stroke="#1d4c3b" fill="none" strokeWidth="3" />
          <text x="30" y="180">
            Game 0
          </text>
          <text x="340" y="180" textAnchor="middle">
            81
          </text>
          <text x="670" y="180" textAnchor="end">
            162
          </text>
        </svg>
      </section>
      <section
        className="dashboard-section"
        aria-labelledby="opponent-title"
        id="opponent-summary"
      >
        <h3 id="opponent-title">By opponent</h3>
        <div
          className="batting-scroll"
          role="region"
          aria-label="Opponent summary table"
          tabIndex={0}
        >
          <table>
            <caption className="sr-only">
              Your record and runs against each representative opponent
            </caption>
            <thead>
              <tr>
                {['Opponent', 'G', 'W', 'L', 'RS', 'RA', 'Diff'].map((s) => (
                  <th key={s} scope="col">
                    {s}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.opponents.map((t) => (
                <tr key={t.opponentId}>
                  <th scope="row">{label(t.opponentId)}</th>
                  <td>{t.games}</td>
                  <td>{t.wins}</td>
                  <td>{t.losses}</td>
                  <td>{t.runsScored}</td>
                  <td>{t.runsAllowed}</td>
                  <td>
                    {t.runDifferential > 0 ? '+' : ''}
                    {t.runDifferential}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section
        className="dashboard-section"
        aria-labelledby="schedule-title"
        id="season-schedule"
      >
        <h3 id="schedule-title">Game results</h3>
        <p className="muted">
          Synthetic Draftory schedule · representative 2024 lineups · 18 games
          per opponent, nine home and nine away. No real calendar dates.
        </p>
        <div className="schedule-filters">
          <label>
            Opponent
            <select
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
            >
              <option value="all">All opponents</option>
              {d.opponents.map((t) => (
                <option key={t.opponentId} value={t.opponentId}>
                  {label(t.opponentId)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Result
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            >
              <option value="all">All results</option>
              <option value="wins">Wins</option>
              <option value="losses">Losses</option>
            </select>
          </label>
        </div>
        <p className="muted" role="status">
          Showing {filtered.length} of {d.games.length} games. Record is
          cumulative for the full season.
        </p>
        <div
          className="batting-scroll schedule-scroll"
          role="region"
          aria-label="Game results table"
          tabIndex={0}
        >
          <table>
            <caption className="sr-only">
              Games in simulation order, scores shown your team first. Select a
              game for details.
            </caption>
            <thead>
              <tr>
                {['Game', 'Opponent', 'Venue', 'Score', 'Result', 'Record'].map(
                  (s) => (
                    <th key={s} scope="col">
                      {s}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.map((g) => (
                <tr
                  key={g.gameNumber}
                  className={g.gameNumber === selected ? 'selected-game' : ''}
                >
                  <th scope="row">
                    <button
                      className="game-link"
                      aria-label={`View game ${g.gameNumber}`}
                      aria-pressed={g.gameNumber === selected}
                      onClick={() => setSelected(g.gameNumber)}
                    >
                      Game {g.gameNumber}
                    </button>
                  </th>
                  <td title={label(g.opponentId)}>
                    {abbreviation(g.opponentId)}
                  </td>
                  <td>{g.userHome ? 'Home' : 'Away'}</td>
                  <td>
                    {g.score[0]}–{g.score[1]}
                  </td>
                  <td>{g.won ? 'W' : 'L'}</td>
                  <td>
                    {g.wins}–{g.losses}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && <p>No games match these filters.</p>}
        {game && (
          <section className="game-detail" aria-labelledby="game-detail-title">
            <h4 tabIndex={-1} ref={detail} id="game-detail-title">
              Game {game.gameNumber} · {game.userHome ? 'vs' : 'at'}{' '}
              {label(game.opponentId)}
            </h4>
            <p>
              <strong>
                {game.won ? 'Win' : 'Loss'} {game.score[0]}–{game.score[1]}
              </strong>{' '}
              · {game.innings} innings · {game.plateAppearances} combined PA ·
              Season record {game.wins}–{game.losses}
            </p>
            <div
              className="batting-scroll"
              role="region"
              aria-label="Game inning scores"
              tabIndex={0}
            >
              <table>
                <caption className="sr-only">
                  Runs by inning. An em dash means the half-inning was not
                  played.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Team</th>
                    {game.lineScore.map((_, i) => (
                      <th key={i} scope="col">
                        {i + 1}
                      </th>
                    ))}
                    <th scope="col">R</th>
                  </tr>
                </thead>
                <tbody>
                  {[0, 1].map((side) => (
                    <tr key={side}>
                      <th scope="row">
                        {side === 0
                          ? 'Your team'
                          : abbreviation(game.opponentId)}
                      </th>
                      {game.lineScore.map((line, i) => (
                        <td key={i}>{line[side] ?? '—'}</td>
                      ))}
                      <td>{game.score[side]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div
              className="batting-scroll"
              role="region"
              aria-label="Game team statistics"
              tabIndex={0}
            >
              <table>
                <caption className="sr-only">
                  Supported game batting counters. No fielding-error totals are
                  inferred.
                </caption>
                <thead>
                  <tr>
                    {['Team', 'H', 'HR', 'BB', 'SO', 'LOB'].map((s) => (
                      <th key={s} scope="col">
                        {s}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[0, 1].map((side) => (
                    <tr key={side}>
                      <th scope="row">
                        {side === 0
                          ? 'Your team'
                          : abbreviation(game.opponentId)}
                      </th>
                      {[
                        game.hits,
                        game.homeRuns,
                        game.walks,
                        game.strikeouts,
                        game.leftOnBase,
                      ].map((values, i) => (
                        <td key={i}>{values[side]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">
              Scores and counters are simulated. — means an unplayed
              half-inning. Game seed: {game.seed}. Full play-by-play is not
              loaded.
            </p>
          </section>
        )}
      </section>
    </>
  );
}
