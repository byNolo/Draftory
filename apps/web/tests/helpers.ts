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
    const pending = new Map<string, (value: WorkerResponse) => void>();
    worker.onmessage = ({ data }: MessageEvent<WorkerResponse>) => {
      pending.get(data.requestId)?.(data);
      pending.delete(data.requestId);
    };
    return {
      createdAt,
      send(request: WorkerRequest): Promise<WorkerResponse> {
        return new Promise((resolve) => {
          pending.set(request.requestId, resolve);
          worker.postMessage(request);
        });
      },
      terminate() {
        worker.terminate();
      },
    };
  }, workerUrl());
}
