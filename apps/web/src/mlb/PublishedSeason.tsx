import { useEffect, useRef, useState } from 'react';
import {
  PlayerDataClient,
  type Dataset,
  type Player,
  type PreparedProfile,
} from '../lib/api/player-data';
import { assembleSeason, validateDataset, type Pilot } from './season-input';
import { PilotLoader } from './pilot-loader';
import type { SeasonSuccess } from '../workers/protocol';

interface Loaded {
  dataset: Dataset;
  pilot: Pilot;
  players: Player[];
  profiles: PreparedProfile[];
}
export default function PublishedSeason({
  disabled,
  simulate,
}: {
  disabled: boolean;
  simulate: (input: string) => Promise<SeasonSuccess>;
}) {
  const [api] = useState(() => new PlayerDataClient());
  const [shared] = useState(() => new PilotLoader());
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [nextAfter, setNextAfter] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState('');
  const [loaded, setLoaded] = useState<Loaded>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [seed, setSeed] = useState('20261025');
  const [metrics, setMetrics] = useState<{
    fetchMs: number;
    assemblyMs?: number;
    roundTripMs?: number;
    wasmMs?: number;
    requests: number;
    bytes: number;
  }>();
  const revision = useRef(0);
  useEffect(
    () => () => {
      revision.current++;
    },
    [],
  );
  function clear() {
    revision.current++;
    api.clear();
    shared.clear();
    setLoaded(undefined);
    setMetrics(undefined);
    setError('');
    setBusy(false);
  }
  async function catalog(after?: string) {
    const token = revision.current;
    setBusy(true);
    setError('');
    try {
      const page = await api.datasets(after);
      if (token !== revision.current) return;
      setDatasets((old) =>
        after ? [...old, ...page.datasets] : page.datasets,
      );
      setNextAfter(page.nextAfter);
      if (!after) {
        setDatasetId(page.datasets[0]?.id ?? '');
        setLoaded(undefined);
      }
      if (!page.datasets.length && !after)
        setError(
          'No published datasets. Apply local migrations and import the 2024 publication.',
        );
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  async function load() {
    const token = revision.current;
    setBusy(true);
    setError('');
    setLoaded(undefined);
    const start = performance.now();
    try {
      const [dataset, pilot] = await Promise.all([
        api.dataset(datasetId),
        shared.load(),
      ]);
      validateDataset(dataset, pilot);
      const players = await Promise.all(
        pilot.userPlayerIds.map((id) => api.player(dataset.id, id)),
      );
      const profiles = await api.profiles(
        dataset.id,
        players.map((p) => p.profileId),
      );
      // Validate the entire combination now, before enabling the WASM button.
      const assemblyStart = performance.now();
      await assembleSeason(dataset, players, profiles, pilot, seed);
      if (token !== revision.current) return;
      setLoaded({ dataset, pilot, players, profiles });
      setMetrics({
        fetchMs: assemblyStart - start,
        assemblyMs: performance.now() - assemblyStart,
        requests: api.transfers.length + shared.transfers.length,
        bytes: [...api.transfers, ...shared.transfers].reduce(
          (n, t) => n + t.bytes,
          0,
        ),
      });
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  async function run() {
    if (!loaded) return;
    const token = revision.current;
    setBusy(true);
    setError('');
    try {
      const start = performance.now();
      const input = await assembleSeason(
        loaded.dataset,
        loaded.players,
        loaded.profiles,
        loaded.pilot,
        seed,
      );
      const inputJson = JSON.stringify(input);
      const assemblyMs = performance.now() - start;
      const result = await simulate(inputJson);
      if (token !== revision.current) return;
      setMetrics((old) => ({
        fetchMs: old?.fetchMs ?? 0,
        assemblyMs,
        roundTripMs: result.roundTripMs,
        wasmMs: result.timings.wasmCallMs,
        requests: api.transfers.length + shared.transfers.length,
        bytes: [...api.transfers, ...shared.transfers].reduce(
          (n, t) => n + t.bytes,
          0,
        ),
      }));
    } catch (e) {
      if (token === revision.current) setError(String(e));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  return (
    <section aria-label="Published player data">
      <h2>Published player data · M6B developer pilot</h2>
      <p>
        Load the fixed 2024 NYA order from D1. CHA opponent profiles and
        observed transitions come from the verified M4 snapshot. This is a
        synthetic schedule against one fixed opponent.
      </p>
      <button disabled={busy} onClick={() => void catalog()}>
        Load published datasets
      </button>
      {nextAfter && (
        <button disabled={busy} onClick={() => void catalog(nextAfter)}>
          More datasets
        </button>
      )}
      <label>
        Published dataset{' '}
        <select
          aria-label="Published dataset"
          value={datasetId}
          disabled={busy}
          onChange={(e) => {
            clear();
            setDatasetId(e.target.value);
          }}
        >
          <option value="">Select a dataset</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.year} · {d.profileType} · {d.id}
            </option>
          ))}
        </select>
      </label>
      <button disabled={!datasetId || busy} onClick={() => void load()}>
        Load pilot data
      </button>
      <button disabled={busy} onClick={clear}>
        Clear session cache
      </button>
      <label>
        Season seed{' '}
        <input
          aria-label="Season seed"
          value={seed}
          disabled={busy}
          onChange={(e) => setSeed(e.target.value)}
        />
      </label>
      <button disabled={disabled || busy || !loaded} onClick={() => void run()}>
        Simulate published 162 games
      </button>
      <p data-testid="data-status">
        {busy
          ? 'Loading or running…'
          : loaded
            ? 'Published input ready'
            : 'Bundled offline fixture remains available above'}
      </p>
      {error && <p role="alert">{error}</p>}
      {metrics && (
        <output
          aria-label="Data integration measurements"
          data-fetch-ms={metrics.fetchMs}
          data-assembly-ms={metrics.assemblyMs}
          data-wasm-ms={metrics.wasmMs}
          data-roundtrip-ms={metrics.roundTripMs}
          data-requests={metrics.requests}
          data-bytes={metrics.bytes}
        >
          <p>
            Data requests: {metrics.requests}; decoded response bytes:{' '}
            {metrics.bytes}; data loading: {metrics.fetchMs.toFixed(2)} ms;
            assembly: {metrics.assemblyMs?.toFixed(2)} ms
          </p>
          {metrics.wasmMs !== undefined && (
            <p>
              WASM call: {metrics.wasmMs.toFixed(2)} ms; worker round trip:{' '}
              {metrics.roundTripMs?.toFixed(2)} ms. Repeat runs use the loaded
              session snapshot.
            </p>
          )}
        </output>
      )}
      {loaded && (
        <details>
          <summary>Inspect selected players and profiles</summary>
          <p>
            Dataset: <code>{loaded.dataset.id}</code>; shared artifact:{' '}
            <code>{loaded.pilot.id}</code>
          </p>
          <ol>
            {loaded.players.map((p) => (
              <li key={p.id}>
                {p.displayName} · <code>{p.id}</code> ·{' '}
                <code>{p.profileId}</code>
              </li>
            ))}
          </ol>
          <p>Opponent: {loaded.pilot.season.opponents[0].id}</p>
          <ul>
            {loaded.pilot.opponentProfiles.map((p) => (
              <li key={p.id}>
                <code>{p.provenance.playerId}</code> · <code>{p.id}</code>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
