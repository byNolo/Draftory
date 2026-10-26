import { SessionCache } from '../lib/api/session-cache';
import { DataError } from '../lib/api/player-data';
import { parsePilot, type Pilot } from './season-input';
import pilotUrl from '../generated/mlb-pilot-2024.json?url';
import { PILOT_ID } from '../generated/pilot-meta';

export class PilotLoader {
  private cache = new SessionCache();
  readonly transfers: { bytes: number; ms: number }[] = [];
  clear() {
    this.cache.clear();
    this.transfers.length = 0;
  }
  constructor(
    private readonly url = pilotUrl,
    private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {}
  load(): Promise<Pilot> {
    return this.cache.get(
      `pilot:engine-0.4.0:assembler-v1:${PILOT_ID}:${this.url}`,
      async () => {
        const start = performance.now();
        let response: Response;
        try {
          response = await this.fetcher(this.url);
        } catch {
          throw new DataError(
            'contextUnavailable',
            'Verified pilot artifact could not be loaded',
          );
        }
        if (!response.ok)
          throw new DataError(
            'contextUnavailable',
            'Verified pilot artifact is unavailable',
          );
        const bytes = await response.arrayBuffer();
        this.transfers.push({
          bytes: bytes.byteLength,
          ms: performance.now() - start,
        });
        return parsePilot(JSON.parse(new TextDecoder().decode(bytes)));
      },
    );
  }
}
