import { rate, simulatedRates } from './batting';
import type { SeasonSuccess, BattingLine } from '../../workers/protocol';
import { DraftEngine, POSITIONS, type DraftState } from '../draft/engine';

function Cells({ stats }: { stats: BattingLine }) {
  const r = simulatedRates(stats);
  return (
    <>
      <td>{stats.plateAppearances}</td>
      <td>{stats.hits}</td>
      <td>{stats.homeRuns}</td>
      <td>{stats.runsBattedIn}</td>
      <td>{stats.runs}</td>
      <td>{rate(r.avg)}</td>
      <td>{rate(r.obp)}</td>
      <td>{rate(r.slg)}</td>
    </>
  );
}
export default function SeasonResults({
  result,
  engine,
  draft,
}: {
  result: SeasonSuccess;
  engine: DraftEngine;
  draft: DraftState;
}) {
  const { summary: s, batting: b } = result;
  if (!b || b.schemaVersion !== '1.0.0')
    throw new Error('Missing batting projection.');
  const rows = POSITIONS.map((position) => {
    const pick = draft.history.find((p) => p.position === position)!;
    const player = engine.player(pick.playerId);
    const box = b.batters.find(
      (p) => p.batterId === `draft:2024:${player.id}`,
    )!;
    return { position, pick, player, stats: box.stats };
  });
  return (
    <section aria-label="Simulated season results" className="results">
      <div className="scoreboard">
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
      <h3>Season batting</h3>
      <p className="muted">
        Simulated totals, not historical projections. Lineup order is fixed by
        position.
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
              <th scope="col">Player / position</th>
              {['PA', 'H', 'HR', 'RBI', 'R', 'AVG', 'OBP', 'SLG'].map((k) => (
                <th scope="col" key={k}>
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ player, position, pick, stats }) => (
              <tr key={player.id}>
                <th scope="row">
                  {player.name}
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
      <details className="rules">
        <summary>How to read these results</summary>
        <p>
          AVG = H / AB. SLG = total bases / AB. Simulated OBP = (H + BB + HBP) /
          (AB + BB + HBP); sacrifices are not simulated. Intentional walks are
          already included in BB. Zero denominators display —. Individual games
          played are not tracked.
        </p>
        <p>
          This experimental model uses neutral pitching and defense, a fixed CHA
          opponent template and a synthetic schedule. A historical identity may
          appear on both teams. Known biases include excess hits and double
          plays and compressed scoring variance. Results are not predictions of
          real baseball.
        </p>
      </details>
    </section>
  );
}
