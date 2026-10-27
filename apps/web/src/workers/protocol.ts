// Transport envelopes only. Season JSON remains the versioned Rust/contracts format.
export interface SeasonSummary {
  engineVersion: string;
  schemaVersion: string;
  seed: string;
  games: number;
  wins: number;
  losses: number;
  runsScored: number;
  runsAllowed: number;
  runDifferential: number;
}

export interface WorkerTimings {
  initializationMs: number;
  // Includes JSON decode, core simulation, JSON encode and WASM string copies.
  wasmCallMs: number;
  inputParsingMs: number;
  simulationMs: number;
  serializationMs: number;
  resultJsonBytes: number;
  wasmMemoryBeforeBytes: number;
  wasmMemoryAfterBytes: number;
  resultProcessingMs: number;
  workerTotalMs: number;
}

export interface WorkerFailure {
  code:
    | 'invalidJson'
    | 'invalidInput'
    | 'gameFailed'
    | 'serializationFailed'
    | 'initializationFailed'
    | 'busy'
    | 'workerFailed';
  message: string;
  gameNumber?: number;
}

export type WorkerRequest =
  | { type: 'initialize'; requestId: string }
  | {
      type: 'simulate';
      requestId: string;
      inputJson: string;
      // summaryBaseline keeps the M5A full-serialization path as a benchmark control.
      output: 'summary' | 'full' | 'summaryBaseline' | 'batting';
    };

export type WorkerResponse =
  | {
      type: 'ready';
      requestId: string;
      initializationMs: number;
      wasmMemoryBytes: number;
      resources: {
        name: string;
        duration: number;
        transferSize: number;
        encodedBodySize: number;
        decodedBodySize: number;
      }[];
    }
  | {
      type: 'result';
      requestId: string;
      summary: SeasonSummary;
      timings: WorkerTimings;
      resultJson?: string;
      batting?: SeasonBatting;
    }
  | { type: 'error'; requestId: string; error: WorkerFailure };

export type SeasonSuccess = Extract<WorkerResponse, { type: 'result' }> & {
  roundTripMs: number;
  endToEndMs: number;
  // Estimate includes scheduling and both message directions, not pure transfer time.
  messagingOverheadMs: number;
};

// Compact projection v1: counters copied directly from Rust season box scores.
export interface BattingLine {
  plateAppearances: number;
  atBats: number;
  hits: number;
  singles: number;
  doubles: number;
  triples: number;
  homeRuns: number;
  walks: number;
  intentionalWalks: number;
  hitByPitch: number;
  strikeouts: number;
  runs: number;
  runsBattedIn: number;
}
export interface SeasonBatting {
  schemaVersion: '1.0.0';
  teamId: string;
  totals: BattingLine;
  batters: { batterId: string; stats: BattingLine }[];
}
