import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Page } from '@playwright/test';
import type { WorkerRequest, WorkerResponse } from '../src/workers/protocol';

const root = process.cwd();
export const fixture = JSON.parse(
  readFileSync(
    resolve(root, 'crates/baseball-sim/tests/fixtures/season-modern-2024.json'),
    'utf8',
  ),
);
export const artifacts = resolve(root, 'target/browser-parity');
mkdirSync(artifacts, { recursive: true });

// Capacity fixture only, not 30 real rosters: explicitly synthetic opponents reuse
// verified parameter templates with distinct instance/profile IDs. No new data/model.
export function largeFixture() {
  const value = structuredClone(fixture);
  const byId = new Map(
    value.profiles.map((profile: { id: string }) => [profile.id, profile]),
  );
  value.profiles = value.userTeam.lineup.map((batter: { profileId: string }) =>
    structuredClone(byId.get(batter.profileId)),
  );
  const template = value.opponents[0];
  value.opponentSetKind = 'synthetic';
  value.opponents = Array.from({ length: 29 }, (_, index) => {
    const id = `capacity-team-${String(index).padStart(2, '0')}`;
    return {
      id,
      lineup: template.lineup.map(
        (batter: { profileId: string }, slot: number) => {
          const profile = structuredClone(byId.get(batter.profileId)) as {
            id: string;
          };
          profile.id = `${id}:profile-${slot}`;
          value.profiles.push(profile);
          return { id: `${id}:batter-${slot}`, profileId: profile.id };
        },
      ),
    };
  });
  return value;
}

export function workerUrl() {
  const filename = readdirSync(resolve(root, 'apps/web/dist/assets')).find(
    (file) => /^season\.worker-.*\.js$/.test(file),
  );
  if (!filename)
    throw new Error(
      'Build WASM and the production frontend before browser tests.',
    );
  return `/assets/${filename}`;
}

export function nativeResult(input: typeof fixture) {
  const path = resolve(artifacts, 'input.json');
  writeFileSync(path, JSON.stringify(input));
  const binary = resolve(
    root,
    `target/release/examples/season${process.platform === 'win32' ? '.exe' : ''}`,
  );
  return JSON.parse(
    execFileSync(binary, [path], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    }),
  );
}

// Test-only handle: the production app never exposes a debug global or full results.
export async function session(page: Page) {
  return page.evaluateHandle((url) => {
    const createdAt = performance.now();
    const worker = new Worker(url, { type: 'module' });
    const pending = new Map<
      string,
      {
        resolve: (value: WorkerResponse) => void;
        reject: (error: Error) => void;
      }
    >();
    let failed: Error | undefined;
    const fail = (error: Error) => {
      failed = error;
      for (const entry of pending.values()) entry.reject(error);
      pending.clear();
    };
    worker.onerror = (event) => {
      event.preventDefault();
      fail(new Error(event.message || 'Test worker failed'));
    };
    worker.onmessageerror = () =>
      fail(new Error('Test worker response could not be decoded'));
    worker.onmessage = ({ data }: MessageEvent<WorkerResponse>) => {
      pending.get(data.requestId)?.resolve(data);
      pending.delete(data.requestId);
    };
    return {
      createdAt,
      send(request: WorkerRequest): Promise<WorkerResponse> {
        if (failed) return Promise.reject(failed);
        return new Promise((resolve, reject) => {
          pending.set(request.requestId, { resolve, reject });
          worker.postMessage(request);
        });
      },
      terminate() {
        worker.terminate();
        fail(new Error('Test worker terminated'));
      },
    };
  }, workerUrl());
}
