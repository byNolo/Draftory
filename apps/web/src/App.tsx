import { useEffect, useRef, useState } from 'react';
import fixtureJson from '../../../crates/baseball-sim/tests/fixtures/season-modern-2024.json?raw';
import { SeasonClient } from './workers/season-client';
import type { SeasonSuccess } from './workers/protocol';

export default function App() {
  const client = useRef<SeasonClient | null>(null);
  const [generation, setGeneration] = useState(0);
  const [status, setStatus] = useState<
    'initializing' | 'ready' | 'running' | 'error' | 'stopped'
  >('initializing');
  const [initializationMs, setInitializationMs] = useState<number>();
  const [result, setResult] = useState<SeasonSuccess>();
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let instance: SeasonClient | undefined;
    async function initialize() {
      instance = new SeasonClient();
      client.current = instance;
      return instance.initialize();
    }
    initialize()
      .then((elapsed) => {
        if (active && client.current === instance) {
          setInitializationMs(elapsed);
          setStatus('ready');
        }
      })
      .catch((reason: unknown) => {
        if (active && (!instance || client.current === instance)) {
          setError(String(reason));
          setStatus('error');
        }
      });
    return () => {
      active = false;
      client.current = null;
      instance?.dispose();
    };
  }, [generation]);

  async function run() {
    const instance = client.current;
    if (!instance || status !== 'ready') return;
    const start = performance.now();
    setStatus('running');
    setError('');
    setResult(undefined);
    try {
      const response = await instance.simulate(fixtureJson);
      if (client.current !== instance) return;
      setResult({ ...response, endToEndMs: performance.now() - start });
      setStatus('ready');
    } catch (reason) {
      if (client.current !== instance) return;
      setError(String(reason));
      setStatus('error');
    }
  }

  function stop() {
    const instance = client.current;
    client.current = null;
    instance?.dispose();
    setStatus('stopped');
  }

  function restart() {
    setStatus('initializing');
    setError('');
    setResult(undefined);
    setInitializationMs(undefined);
    setGeneration((value) => value + 1);
  }

  return (
    <main>
      <h1>Draftory</h1>
      <p>Browser simulation test · M5A</p>
      <p>
        Bundled M4 fixture: 2024 NYA versus CHA, fixed historical starting
        orders, 162-game synthetic schedule. Season schema 1.0.0; seed{' '}
        <code>20261025</code>.
      </p>
      <p>
        The simulator is not fully calibrated. Hits, plate appearances, double
        plays, and scoring variance retain known biases.
      </p>
      <p role="status">
        {status === 'initializing'
          ? 'Initializing WebAssembly…'
          : status === 'running'
            ? 'Simulating 162 games in the Web Worker…'
            : status === 'ready'
              ? 'Ready'
              : status === 'stopped'
                ? 'Worker stopped'
                : 'Simulation unavailable'}
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="actions">
        <button disabled={status !== 'ready'} onClick={() => void run()}>
          Simulate 162 games
        </button>
        <button disabled={status === 'stopped'} onClick={stop}>
          Stop worker
        </button>
        {(status === 'stopped' || status === 'error') && (
          <button onClick={restart}>Restart worker</button>
        )}
        {status === 'error' && (
          <button onClick={() => window.location.reload()}>Reload app</button>
        )}
      </div>
      {initializationMs !== undefined && (
        <p>WASM initialization: {initializationMs.toFixed(2)} ms</p>
      )}
      {result && (
        <section aria-label="Season result">
          <h2>
            {result.summary.wins}–{result.summary.losses}
          </h2>
          <dl>
            <dt>Games</dt>
            <dd>{result.summary.games}</dd>
            <dt>Runs scored</dt>
            <dd>{result.summary.runsScored}</dd>
            <dt>Runs allowed</dt>
            <dd>{result.summary.runsAllowed}</dd>
            <dt>Run differential</dt>
            <dd>{result.summary.runDifferential}</dd>
            <dt>Rust/WASM call (JSON + simulation)</dt>
            <dd>{result.timings.wasmCallMs.toFixed(2)} ms</dd>
            <dt>Worker result processing</dt>
            <dd>{result.timings.resultProcessingMs.toFixed(2)} ms</dd>
            <dt>Worker round trip</dt>
            <dd>{result.roundTripMs.toFixed(2)} ms</dd>
            <dt>Messaging / scheduling estimate</dt>
            <dd>{result.messagingOverheadMs.toFixed(2)} ms</dd>
            <dt>End to end (click to result)</dt>
            <dd>{result.endToEndMs.toFixed(2)} ms</dd>
            <dt>Engine</dt>
            <dd>{result.summary.engineVersion}</dd>
          </dl>
        </section>
      )}
      <p className="attribution">
        Data: SABR Lahman (CC BY-SA 3.0) and Retrosheet. The information used
        here was obtained free of charge from and is copyrighted by Retrosheet.
        Interested parties may contact Retrosheet at{' '}
        <a href="https://www.retrosheet.org/">www.retrosheet.org</a>.
      </p>
    </main>
  );
}
