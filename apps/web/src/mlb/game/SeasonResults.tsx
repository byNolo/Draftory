import SeasonDashboard, { type OpponentLabel } from './SeasonDashboard';
import { rate, simulatedRates } from './batting';
import type { SeasonSuccess, BattingLine } from '../../workers/protocol';
import { DraftEngine, type DraftState } from '../draft/engine';
import type { BattingOrder } from '../draft/batting-order';

function Cells({ stats }: { stats: BattingLine }) {
  const r = simulatedRates(stats);
  return (
    <>
      <td>{stats.plateAppearances}</td>
      <td>{stats.atBats}</td>
      <td>{stats.hits}</td>
      <td>{stats.doubles}</td>
      <td>{stats.triples}</td>
      <td>{stats.homeRuns}</td>
      <td>{stats.walks}</td>
      <td>{stats.strikeouts}</td>
      <td>{stats.runsBattedIn}</td>
      <td>{stats.runs}</td>
      <td>{rate(r.avg)}</td>
      <td>{rate(r.obp)}</td>
      <td>{rate(r.slg)}</td>
      <td>{rate(r.obp === null || r.slg === null ? null : r.obp + r.slg)}</td>
    </>
  );
}
export default function SeasonResults({
  result,
  engine,
  draft,
  order,
}: {
  result: SeasonSuccess & {
    opponents?: OpponentLabel[];
    errorAvoidance?: boolean;
  };
  engine: DraftEngine;
  draft: DraftState;
  order: BattingOrder;
}) {
  const { summary: s, batting: b } = result;
  if (!b || b.schemaVersion !== '1.0.0')
    throw new Error('Missing batting projection.');
  const rows = order.map((id) => {
    const pick = draft.history.find((p) => p.playerId === id)!;
    const player = engine.player(pick.playerId);
    const box = b.batters.find(
      (p) => p.batterId === `draft:2024:${player.id}`,
    )!;
    return { position: pick.position, pick, player, stats: box.stats };
  });
  return (
    <section aria-label="Simulated season results" className="results">
      <nav className="dashboard-nav" aria-label="Season dashboard">
        <a href="#season-overview">Overview</a>
        <a href="#season-batting">Player statistics</a>
        <a href="#opponent-summary">By opponent</a>
        <a href="#season-schedule">Game results</a>
      </nav>
      <div className="scoreboard" id="season-overview">
        <p className="eyebrow">Your season · {s.games} games</p>
        <h2 tabIndex={-1} data-screen-title>
          {s.wins}
          <span>–</span>
          {s.losses}
        </h2>
        <p>
          {((100 * s.wins) / s.games).toFixed(1)}% wins · simulated 2024
          environment
        </p>
        <div className="score-metrics">
          <div>
            <strong>{s.runsScored}</strong>
            <span>Runs scored</span>
          </div>
          <div>
            <strong>{s.runsAllowed}</strong>
            <span>Runs allowed</span>
          </div>
          <div>
            <strong>
              {s.runDifferential > 0 ? '+' : ''}
              {s.runDifferential}
            </strong>
            <span>Run differential</span>
          </div>
        </div>
        <p className="team-rate-summary">
          Team batting: AVG {rate(simulatedRates(b.totals).avg)} · OBP{' '}
          {rate(simulatedRates(b.totals).obp)} · SLG{' '}
          {rate(simulatedRates(b.totals).slg)}
        </p>
      </div>
      <div className="leaders" aria-label="Team leaders">
        {(['homeRuns', 'hits', 'runsBattedIn'] as const).map((field, i) => {
          const max = Math.max(...rows.map((r) => r.stats[field]));
          return (
            <article key={field}>
              <p className="eyebrow">
                {['Home run leaders', 'Hit leaders', 'RBI leaders'][i]}
              </p>
              <strong>{max}</strong>
              <p>
                {rows
                  .filter((r) => r.stats[field] === max)
                  .map((r) => r.player.name)
                  .join(' · ')}
              </p>
            </article>
          );
        })}
      </div>
      <p className="muted">
        Season seed: {s.seed} · Engine {s.engineVersion}
      </p>
      <p className="model-label">
        {result.dashboard?.defenseModelId
          ? 'Experimental error avoidance on'
          : 'Your defense: neutral'}{' '}
        · Opponent defense: neutral · Standardized pitching
      </p>
      <h3 id="season-batting">Season batting</h3>
      <p className="muted">
        Simulated totals, not historical projections. Players are shown in the
        batting order used for this season; fielding assignments are unchanged.
      </p>
      <div
        className="batting-scroll"
        role="region"
        aria-label="Season batting table, scroll for all statistics"
        tabIndex={0}
      >
        <table>
          <caption className="sr-only">
            Simulated player and team batting totals
          </caption>
          <thead>
            <tr>
              <th scope="col">Batting order / player / position</th>
              {[
                'PA',
                'AB',
                'H',
                '2B',
                '3B',
                'HR',
                'BB',
                'SO',
                'RBI',
                'R',
                'AVG',
                'OBP',
                'SLG',
                'OPS',
              ].map((k) => (
                <th scope="col" key={k}>
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ player, position, pick, stats }, index) => (
              <tr key={player.id}>
                <th scope="row">
                  {index + 1}. {player.name}
                  <small>
                    {position} · {pick.price} credits
                  </small>
                </th>
                <Cells stats={stats} />
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Team totals</th>
              <Cells stats={b.totals} />
            </tr>
          </tfoot>
        </table>
      </div>
      {result.dashboard && (
        <SeasonDashboard
          key={s.seed}
          dashboard={result.dashboard}
          opponents={result.opponents ?? []}
        />
      )}
      <details className="rules">
        <summary>How to read these results</summary>
        <p>
          AVG = H / AB. SLG = total bases / AB. Simulated OBP = (H + BB + HBP) /
          (AB + BB + HBP); sacrifices are not simulated. Intentional walks are
          already included in BB. Zero denominators display —. Individual games
          played are not tracked.
        </p>
        <p>
          This experimental model uses standardized pitching, neutral opponent
          defense, optional error avoidance for your fielders, and a synthetic
          Draftory schedule. Opponent lineups are representative PA-ranked
          orders using full-season profiles, not authentic starting lineups. A
          historical identity may appear on both teams. Known biases include
          excess hits and double plays and compressed scoring variance. Results
          are not predictions of real baseball.
        </p>
      </details>
    </section>
  );
}
