import { useEffect, useRef, useState } from 'react';
import { PlayerDataClient } from '../../lib/api/player-data';
import { SeasonClient } from '../../workers/season-client';
import type { SeasonSuccess } from '../../workers/protocol';
import { PilotLoader } from '../pilot-loader';
import { loadCatalog, PLAYTEST_BUDGET } from '../draft/catalog';
import { DraftEngine, type DraftState } from '../draft/engine';
import { draftedSeason } from '../draft/season';
import {
  defaultBattingOrder,
  validateBattingOrder,
  type BattingOrder,
} from '../draft/batting-order';
import BattingOrderEditor from './BattingOrderEditor';
import { historicalBatting, type HistoricalBatting } from './batting';
import SeasonResults from './SeasonResults';
import { OfferCards, Roster } from './DraftBoard';

const randomSeed = () => String(crypto.getRandomValues(new Uint32Array(1))[0]);
function differentSeed(previous: string) {
  const seed = randomSeed();
  return seed === previous ? String((BigInt(seed) + 1n) % 4294967296n) : seed;
}
export default function MLBGame() {
  const [api] = useState(() => new PlayerDataClient());
  const [pilot] = useState(() => new PilotLoader());
  const [engine, setEngine] = useState<DraftEngine>();
  const [draft, setDraft] = useState<DraftState>();
  const [stats, setStats] = useState<Record<string, HistoricalBatting>>({});
  const [battingOrder, setBattingOrder] = useState<BattingOrder>([]);
  const [result, setResult] = useState<
    SeasonSuccess & { battingOrder: BattingOrder }
  >();
  const [phase, setPhase] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [seed, setSeed] = useState(randomSeed);
  const [seasonSeed, setSeasonSeed] = useState(randomSeed);
  const [retry, setRetry] = useState(0);
  const revision = useRef(0);
  const client = useRef<SeasonClient | null>(null);
  const title = useRef<HTMLElement>(null);
  const busy = phase !== '';
  const complete = draft?.status === 'complete';
  useEffect(
    () => () => {
      revision.current++;
      client.current?.dispose();
      client.current = null;
    },
    [],
  );
  useEffect(() => {
    if (!engine || !draft || draft.status !== 'drafting') return;
    let active = true;
    Promise.all(
      draft.offers.map(async (id) => {
        const player = engine.player(id);
        return [
          id,
          historicalBatting(
            await api.player(engine.catalog.datasetId, id),
            player,
            engine.catalog.year,
          ),
        ] as const;
      }),
    )
      .then((entries) => {
        if (active) {
          setStats(Object.fromEntries(entries));
          setError('');
        }
      })
      .catch((e: unknown) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [api, draft, engine, retry]);
  useEffect(() => {
    title.current?.querySelector<HTMLElement>('[data-screen-title]')?.focus();
  }, [draft?.history.length, result]);

  async function start(chosenSeed = seed) {
    const token = ++revision.current;
    setPhase('Opening the clubhouse…');
    setError('');
    setNotice('');
    setResult(undefined);
    try {
      const next = engine ?? new DraftEngine(await loadCatalog());
      const state = next.start(chosenSeed);
      if (token !== revision.current) return;
      setEngine(next);
      setDraft(state);
      setBattingOrder([]);
      setStats({});
      setSeed(chosenSeed);
      setSeasonSeed(randomSeed());
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setPhase('');
    }
  }
  function pick(id: string) {
    if (!engine || !draft || busy) return;
    try {
      const next = engine.select(draft, id);
      setNotice(
        `${engine.player(id).name} selected at ${draft.config.order[draft.history.length]} for ${engine.player(id).price} credits.`,
      );
      setDraft(next);
      if (next.status === 'complete')
        setBattingOrder(defaultBattingOrder(next));
      setStats({});
      setError('');
    } catch (e) {
      setError(String(e));
    }
  }
  async function simulate(nextSeed = seasonSeed) {
    if (!engine || !draft || !complete || busy) return;
    const token = ++revision.current;
    const started = performance.now();
    setPhase('Loading your nine batting profiles…');
    setNotice('');
    setError('');
    try {
      const order = validateBattingOrder(draft, battingOrder);
      const input = await draftedSeason(
        engine,
        draft,
        api,
        pilot,
        nextSeed,
        order,
      );
      if (token !== revision.current) return;
      if (!client.current) {
        setPhase('Preparing the season simulator…');
        client.current = new SeasonClient();
        await client.current.initialize();
      }
      if (token !== revision.current) return;
      setPhase('Simulating 162 games…');
      const value = await client.current.simulate(
        JSON.stringify(input),
        'batting',
      );
      if (token !== revision.current) return;
      const b = value.batting;
      if (
        !b ||
        b.schemaVersion !== '1.0.0' ||
        b.batters.length !== 9 ||
        input.userTeam.lineup.some(
          (p) => !b.batters.some((s) => s.batterId === p.id),
        )
      )
        throw new Error('The season returned an incomplete batting result.');
      setResult({
        ...value,
        battingOrder: order,
        endToEndMs: performance.now() - started,
      });
      setSeasonSeed(nextSeed);
      setNotice('Season complete. Your batting totals are ready.');
    } catch (e) {
      if (token === revision.current) {
        setError(`Season unavailable. Your lineup is saved. ${String(e)}`);
        client.current?.dispose();
        client.current = null;
      }
    } finally {
      if (token === revision.current) setPhase('');
    }
  }
  function cancel() {
    revision.current++;
    client.current?.dispose();
    client.current = null;
    setPhase('');
    setNotice('Season cancelled. Your lineup is saved.');
  }
  function exportSession() {
    const payload = {
      schemaVersion: '1.0.0',
      draft,
      seasonSeed,
      battingOrder,
      result,
      transfers: api.transfers,
      pilotTransfers: pilot.transfers,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'draftory-playtest.json';
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="game">
      <header className="masthead">
        <a className="wordmark" href="/" aria-label="Draftory home">
          D<span className="brand-dot">.</span> <span>Draftory</span>
        </a>
        <span className="league-tag">MLB · 2024 EDITION</span>
      </header>
      <main ref={title}>
        <div className="feedback" aria-live="polite" role="status">
          {phase || notice}
        </div>
        {busy && draft && complete && (
          <button onClick={cancel}>Cancel season</button>
        )}
        {error && (
          <div className="error" role="alert">
            <p>{error}</p>
            {complete && (
              <>
                <p>
                  If the app was updated, reload the latest version. Reloading
                  clears this draft.
                </p>
                <button onClick={() => window.location.reload()}>
                  Reload latest app
                </button>
              </>
            )}
            {draft && !complete && (
              <button
                disabled={busy}
                onClick={() => {
                  setError('');
                  setRetry((n) => n + 1);
                }}
              >
                Retry player statistics
              </button>
            )}
          </div>
        )}
        {!draft ? (
          <section className="welcome">
            <p className="eyebrow">Nine picks. One season. Your team.</p>
            <h1>
              Build a lineup.
              <br />
              <em>Make it count.</em>
            </h1>
            <p className="intro">
              Draft real hitters from the 2024 season. Stretch {PLAYTEST_BUDGET}{' '}
              fictional credits across nine positions, then see how your lineup
              handles 162 games.
            </p>
            <button
              className="primary"
              disabled={busy}
              onClick={() => void start()}
            >
              Start your draft <span aria-hidden="true">↗</span>
            </button>
            <div className="how-it-works">
              <article>
                <b>01</b>
                <h2>Choose your hitters</h2>
                <p>
                  Up to three randomized, affordable choices at every position.
                </p>
              </article>
              <article>
                <b>02</b>
                <h2>Build all nine</h2>
                <p>
                  Balance stars and value. Every offered pick leaves a path to a
                  full lineup.
                </p>
              </article>
              <article>
                <b>03</b>
                <h2>Play out the season</h2>
                <p>
                  Get your record, batting totals and team leaders. Then run it
                  back.
                </p>
              </article>
            </div>
            <details className="rules">
              <summary>Replay a draft seed</summary>
              <label>
                Draft seed
                <input
                  inputMode="numeric"
                  value={seed}
                  disabled={busy}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </label>
            </details>
          </section>
        ) : (
          engine && (
            <>
              <div className="draft-heading">
                <div>
                  <p className="eyebrow">
                    {result
                      ? 'The season is in the books'
                      : complete
                        ? 'Your starting nine'
                        : `Round ${draft.history.length + 1} of 9`}
                  </p>
                  {!result && (
                    <h1 tabIndex={-1} data-screen-title>
                      {complete ? (
                        'Lineup locked.'
                      ) : (
                        <>
                          Who’s your{' '}
                          <em>{draft.config.order[draft.history.length]}?</em>
                        </>
                      )}
                    </h1>
                  )}
                </div>
                <div className="budget">
                  <strong data-testid="game-budget">
                    {draft.remainingBudget}
                  </strong>
                  <span>credits left / {draft.config.budget}</span>
                </div>
              </div>
              <ol className="progress" aria-label="Draft progress">
                {draft.config.order.map((position, i) => (
                  <li
                    key={position}
                    className={
                      i < draft.history.length
                        ? 'filled'
                        : i === draft.history.length
                          ? 'current'
                          : ''
                    }
                    aria-current={
                      i === draft.history.length ? 'step' : undefined
                    }
                  >
                    <span aria-hidden="true">
                      {i < draft.history.length ? '✓' : i + 1}
                    </span>
                    {position}
                  </li>
                ))}
              </ol>
              {result && (
                <SeasonResults
                  result={result}
                  engine={engine}
                  draft={draft}
                  order={result.battingOrder}
                />
              )}
              {complete && !result && (
                <BattingOrderEditor
                  engine={engine}
                  draft={draft}
                  order={battingOrder}
                  disabled={busy}
                  onChange={(order, announcement) => {
                    setBattingOrder(order);
                    setNotice(announcement);
                  }}
                />
              )}
              <div className={`play-layout ${complete ? 'completed' : ''}`}>
                <section
                  aria-label={complete ? 'Next season' : 'Player offers'}
                >
                  {!complete && (
                    <OfferCards
                      engine={engine}
                      draft={draft}
                      stats={stats}
                      busy={busy}
                      onPick={pick}
                    />
                  )}
                  {complete && (
                    <div className="season-actions">
                      <h3>
                        {result ? 'Run it back' : 'Ready for opening day?'}
                      </h3>
                      <p>
                        {result
                          ? 'Keep your lineup and simulate a fresh season, or start over with new offers.'
                          : 'Your nine hitters will face a fixed opponent template across a synthetic 162-game schedule.'}
                      </p>
                      {result && (
                        <button
                          disabled={busy}
                          onClick={() => setResult(undefined)}
                        >
                          Edit batting order
                        </button>
                      )}
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() =>
                          void simulate(
                            result
                              ? differentSeed(result.summary.seed)
                              : seasonSeed,
                          )
                        }
                      >
                        {result
                          ? 'Play another season'
                          : 'Simulate 162-game season'}
                      </button>
                      <details className="rules">
                        <summary>Season seed and model notes</summary>
                        <label>
                          Season seed
                          <input
                            inputMode="numeric"
                            disabled={busy}
                            value={seasonSeed}
                            onChange={(e) => setSeasonSeed(e.target.value)}
                          />
                        </label>
                        <button disabled={busy} onClick={() => void simulate()}>
                          Replay this season seed
                        </button>
                        <p>
                          Your selected batting order is used for every game.
                          Neutral pitching and defense; no substitutions. The
                          CHA opponent can contain the same historical identity.
                          This experimental simulation has known hits,
                          double-play and scoring-variance biases.
                        </p>
                      </details>
                    </div>
                  )}
                </section>
                <Roster engine={engine} draft={draft} />
              </div>
              <button
                className="secondary new-draft"
                disabled={busy}
                onClick={() => void start(differentSeed(draft.seed))}
              >
                Start a new draft
              </button>
            </>
          )
        )}
        {(import.meta.env.DEV ||
          new URLSearchParams(location.search).has('playtest')) && (
          <details className="rules">
            <summary>Local playtest tools</summary>
            <p>
              No analytics or uploads. Export seeds, picks, compact results and
              transfer measurements for manual review.
            </p>
            <button disabled={!draft || busy} onClick={exportSession}>
              Export session JSON
            </button>
            <a href="/dev">Developer simulation harness</a>
          </details>
        )}
      </main>
      <footer>
        <p>Experimental baseball, built from history.</p>
        <details>
          <summary>Data credits & limitations</summary>
          <p>
            Historical data:{' '}
            <a href="https://sabr.org/lahman-database/">
              SABR Lahman Baseball Database
            </a>
            , created by Sean Lahman; annual update by Bryan Walko; Negro League
            data from Seamheads.{' '}
            <a href="https://creativecommons.org/licenses/by-sa/3.0/">
              CC BY-SA 3.0
            </a>
            . Simulated statistics are separate from historical records.
            Fictional prices are provisional.
          </p>
          <p>
            The information used here was obtained free of charge from and is
            copyrighted by Retrosheet. Interested parties may contact Retrosheet
            at <a href="https://www.retrosheet.org/">www.retrosheet.org</a>.
          </p>
        </details>
      </footer>
    </div>
  );
}
