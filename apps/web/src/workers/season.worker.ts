/// <reference lib="webworker" />
import init, {
  simulate_season_json,
  simulate_season_summary_json,
  last_run_measurements,
} from '../wasm/sim_wasm';
import wasmUrl from '../wasm/sim_wasm_bg.wasm?url';
import type {
  SeasonSummary,
  WorkerFailure,
  WorkerRequest,
  WorkerResponse,
} from './protocol';

const scope = self as unknown as DedicatedWorkerGlobalScope;
let initialization: Promise<number> | undefined;
let busy = false;
let memory: WebAssembly.Memory;

function initialize() {
  initialization ??= (async () => {
    const start = performance.now();
    memory = (await init({ module_or_path: wasmUrl })).memory;
    return performance.now() - start;
  })();
  return initialization;
}

function send(message: WorkerResponse) {
  scope.postMessage(message);
}

function failure(error: unknown): WorkerFailure {
  if (typeof error === 'string') {
    try {
      const parsed: WorkerFailure = JSON.parse(error);
      if (
        [
          'invalidJson',
          'invalidInput',
          'gameFailed',
          'serializationFailed',
        ].includes(parsed.code) &&
        typeof parsed.message === 'string'
      )
        return parsed;
    } catch {
      /* A runtime exception, not a structured Rust error. */
    }
  }
  return {
    code: 'workerFailed',
    message: error instanceof Error ? error.message : String(error),
  };
}

scope.onmessage = async ({ data }: MessageEvent<WorkerRequest>) => {
  if (busy) {
    send({
      type: 'error',
      requestId: data.requestId,
      error: { code: 'busy', message: 'A request is already running.' },
    });
    return;
  }
  busy = true;
  const start = performance.now();
  try {
    let initializationMs: number;
    try {
      initializationMs = await initialize();
    } catch (error) {
      send({
        type: 'error',
        requestId: data.requestId,
        error: {
          code: 'initializationFailed',
          message: error instanceof Error ? error.message : String(error),
        },
      });
      return;
    }
    if (data.type === 'initialize') {
      send({
        type: 'ready',
        requestId: data.requestId,
        initializationMs,
        wasmMemoryBytes: memory.buffer.byteLength,
        resources: (
          performance.getEntriesByType(
            'resource',
          ) as PerformanceResourceTiming[]
        ).map(
          ({
            name,
            duration,
            transferSize,
            encodedBodySize,
            decodedBodySize,
          }) => ({
            name,
            duration,
            transferSize,
            encodedBodySize,
            decodedBodySize,
          }),
        ),
      });
      return;
    }
    const callStart = performance.now();
    const wasmMemoryBeforeBytes = memory.buffer.byteLength;
    const compact = data.output === 'summary';
    const resultJson = compact
      ? simulate_season_summary_json(data.inputJson)
      : simulate_season_json(data.inputJson);
    const wasmCallMs = performance.now() - callStart;
    const [inputParsingMs, simulationMs, serializationMs, resultJsonBytes] =
      last_run_measurements();
    const processingStart = performance.now();
    // Rust validates and serializes this payload. JS projects fields, never computes stats.
    const result = JSON.parse(resultJson) as Omit<
      SeasonSummary,
      'games' | 'seed'
    > & {
      input: { seed: string };
      games: unknown[];
    };
    const summary: SeasonSummary = compact
      ? (result as unknown as SeasonSummary)
      : {
          engineVersion: result.engineVersion,
          schemaVersion: result.schemaVersion,
          seed: result.input.seed,
          games: result.games.length,
          wins: result.wins,
          losses: result.losses,
          runsScored: result.runsScored,
          runsAllowed: result.runsAllowed,
          runDifferential: result.runDifferential,
        };
    send({
      type: 'result',
      requestId: data.requestId,
      summary,
      timings: {
        initializationMs,
        wasmCallMs,
        inputParsingMs,
        simulationMs,
        serializationMs,
        resultJsonBytes,
        wasmMemoryBeforeBytes,
        wasmMemoryAfterBytes: memory.buffer.byteLength,
        resultProcessingMs: performance.now() - processingStart,
        workerTotalMs: performance.now() - start,
      },
      ...(data.output === 'full' ? { resultJson } : {}),
    });
  } catch (error) {
    send({ type: 'error', requestId: data.requestId, error: failure(error) });
  } finally {
    busy = false;
  }
};
