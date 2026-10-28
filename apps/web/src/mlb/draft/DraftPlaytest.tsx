import { useEffect, useRef, useState } from 'react';
import { PlayerDataClient } from '../../lib/api/player-data';
import { PilotLoader } from '../pilot-loader';
import type { SeasonSuccess } from '../../workers/protocol';
import { loadCatalog, PLAYTEST_BUDGET } from './catalog';
import { DEFAULTS, DraftEngine, POSITIONS, type DraftState } from './engine';
import { draftedSeason } from './season';

export default function DraftPlaytest({
  disabled,
  simulate,
}: {
  disabled: boolean;
  simulate: (input: string) => Promise<SeasonSuccess>;
}) {
  const [seed, setSeed] = useState('20261027');
  const [seasonSeed, setSeasonSeed] = useState('20261025');
  const [budget, setBudget] = useState(String(PLAYTEST_BUDGET));
  const [engine, setEngine] = useState<DraftEngine>();
  const [state, setState] = useState<DraftState>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<SeasonSuccess>();
  const [api] = useState(() => new PlayerDataClient());
  const [shared] = useState(() => new PilotLoader());
  const revision = useRef(0);
  useEffect(
    () => () => {
      revision.current++;
    },
    [],
  );
  async function start(newSeed = seed) {
    const token = ++revision.current;
    setBusy(true);
    setError('');
    setResult(undefined);
    try {
      const catalog = engine?.catalog ?? (await loadCatalog());
      const next = new DraftEngine(catalog, {
        ...DEFAULTS,
        budget: Number(budget),
      });
      const draft = next.start(newSeed);
      if (token !== revision.current) return;
      setEngine(next);
      setState(draft);
      setSeed(newSeed);
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  function handlePick(id: string) {
    if (!engine || !state) return;
    try {
      const next = engine.select(state, id);
      setState(next);
      setError('');
    } catch (e) {
      setError(String(e));
    }
  }
  async function run() {
    if (!engine || !state) return;
    const token = revision.current;
    setBusy(true);
    setError('');
    setResult(undefined);
    try {
      const input = await draftedSeason(engine, state, api, shared, seasonSeed);
      const value = await simulate(JSON.stringify(input));
      if (token === revision.current) setResult(value);
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  return (
    <section aria-label="MLB draft playtest">
      <h2>MLB draft · developer playtest</h2>
      <p>
        Experimental 2024 prices, 10 games at each fielding position, all
        hitters DH. Every offered choice preserves an affordable complete
        lineup. Fewer than three choices appear when fewer safe players remain.
        The main game at / includes three free rerolls per draft.
      </p>
      <div className="draft-settings">
        <label>
          Draft seed{' '}
          <input
            aria-label="Draft seed"
            value={seed}
            disabled={busy}
            onChange={(e) => setSeed(e.target.value)}
          />
        </label>
        <label>
          Starting credits{' '}
          <input
            aria-label="Starting credits"
            type="number"
            min="0"
            max="180"
            value={budget}
            disabled={busy}
            onChange={(e) => setBudget(e.target.value)}
          />
        </label>
        <button disabled={busy} onClick={() => void start()}>
          Start / replay draft
        </button>
        <button
          disabled={busy}
          onClick={() =>
            void start(String(crypto.getRandomValues(new Uint32Array(1))[0]))
          }
        >
          New random draft
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {busy && <p>Loading or simulating…</p>}
      {state && engine && (
        <>
          <p data-testid="draft-status">
            {state.status === 'complete'
              ? 'Draft complete'
              : `Drafting ${state.config.order[state.history.length]}`}
          </p>
          <p>
            Active draft seed: <code>{state.seed}</code> · Remaining credits:{' '}
            <strong data-testid="draft-budget">{state.remainingBudget}</strong>
          </p>
          <div className="draft-offers" aria-label="Selectable player offers">
            {state.offers.map((id) => {
              const p = engine.player(id);
              return (
                <article key={id}>
                  <h3>{p.name}</h3>
                  <p>
                    {p.price} credits · {p.positions.join(', ')}
                  </p>
                  <button disabled={busy} onClick={() => handlePick(id)}>
                    Select {p.name}
                  </button>
                </article>
              );
            })}
          </div>
          <ol aria-label="Draft roster">
            {POSITIONS.map((pos) => {
              const pick = state.history.find((p) => p.position === pos);
              return (
                <li key={pos}>
                  {pos}:{' '}
                  {pick
                    ? `${engine.player(pick.playerId).name} (${pick.price} credits)`
                    : 'Unfilled'}
                </li>
              );
            })}
          </ol>
          {state.status === 'complete' && (
            <>
              <label>
                Draft season seed{' '}
                <input
                  aria-label="Draft season seed"
                  value={seasonSeed}
                  disabled={busy}
                  onChange={(e) => setSeasonSeed(e.target.value)}
                />
              </label>
              <button disabled={disabled || busy} onClick={() => void run()}>
                Simulate drafted 162 games
              </button>
              <p>
                The fictional lineup bats in C,1B,2B,3B,SS,LF,CF,RF,DH order
                against the fixed CHA template. The same historical player may
                appear in that opponent template; selected draft identities
                remain unique. Known simulation biases apply.
              </p>
            </>
          )}
          {result && (
            <output data-testid="draft-result">
              {result.summary.games} games · {result.summary.wins}–
              {result.summary.losses} · {result.summary.runsScored} runs
            </output>
          )}
          <details>
            <summary>Inspect draft history and roster JSON</summary>
            <pre data-testid="draft-json">{JSON.stringify(state, null, 2)}</pre>
            <p>
              Catalog: <code>{state.catalogId}</code> · {state.rulesVersion} ·{' '}
              {state.rngVersion}
            </p>
          </details>
        </>
      )}
    </section>
  );
}
