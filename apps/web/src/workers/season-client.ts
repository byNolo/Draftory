import type {
  SeasonSuccess,
  WorkerFailure,
  WorkerRequest,
  WorkerResponse,
} from './protocol';

export class SimulationError extends Error {
  constructor(readonly failure: WorkerFailure) {
    super(failure.message);
    this.name = 'SimulationError';
  }
}

export class SeasonClient {
  private worker = new Worker(new URL('./season.worker.ts', import.meta.url), {
    type: 'module',
  });
  private nextId = 0;
  private stopped = false;
  private pending?: {
    id: string;
    resolve: (response: WorkerResponse) => void;
    reject: (error: Error) => void;
  };

  constructor() {
    this.worker.onmessage = ({ data }: MessageEvent<WorkerResponse>) => {
      const pending = this.pending;
      if (!pending || data.requestId !== pending.id) return;
      this.pending = undefined;
      if (data.type === 'error')
        pending.reject(new SimulationError(data.error));
      else pending.resolve(data);
    };
    this.worker.onerror = (event) => {
      event.preventDefault();
      this.dispose(
        new Error(event.message || 'The simulation worker crashed.'),
      );
    };
    this.worker.onmessageerror = () =>
      this.dispose(new Error('The worker response could not be decoded.'));
  }

  private request(request: WorkerRequest): Promise<WorkerResponse> {
    if (this.stopped)
      return Promise.reject(new Error('The simulation worker has stopped.'));
    if (this.pending)
      return Promise.reject(
        new SimulationError({
          code: 'busy',
          message: 'A request is already running.',
        }),
      );
    return new Promise((resolve, reject) => {
      this.pending = { id: request.requestId, resolve, reject };
      try {
        this.worker.postMessage(request);
      } catch (error) {
        this.pending = undefined;
        reject(error);
      }
    });
  }

  async initialize(): Promise<number> {
    const response = await this.request({
      type: 'initialize',
      requestId: String(++this.nextId),
    });
    if (response.type !== 'ready')
      throw new Error('Unexpected initialization response.');
    return response.initializationMs;
  }

  async simulate(
    inputJson: string,
    output: 'summary' | 'full' = 'summary',
  ): Promise<SeasonSuccess> {
    const start = performance.now();
    const response = await this.request({
      type: 'simulate',
      requestId: String(++this.nextId),
      inputJson,
      output,
    });
    const roundTripMs = performance.now() - start;
    if (response.type !== 'result')
      throw new Error('Unexpected simulation response.');
    return {
      ...response,
      roundTripMs,
      endToEndMs: roundTripMs,
      messagingOverheadMs: Math.max(
        0,
        roundTripMs - response.timings.workerTotalMs,
      ),
    };
  }

  dispose(reason = new Error('The simulation worker was terminated.')) {
    this.stopped = true;
    this.worker.terminate();
    this.pending?.reject(reason);
    this.pending = undefined;
  }
}
