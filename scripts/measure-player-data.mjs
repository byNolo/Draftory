// Local HTTP observations, not cloud CPU, CDN latency or billable D1 row counts.
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const origin = new URL(process.argv[2] ?? 'http://127.0.0.1:8787');
if (
  origin.protocol !== 'http:' ||
  !['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname)
)
  throw new Error('This benchmark only targets a local HTTP Worker');
const get = async (path, options) => {
  const start = performance.now();
  const response = await fetch(new URL(path, origin), options);
  const text = await response.text();
  const ms = performance.now() - start;
  if (!response.ok) throw new Error(`${response.status}: ${text}`);
  return { ms, bytes: Buffer.byteLength(text), body: JSON.parse(text) };
};
const catalog = await get('/api/datasets?season=2024');
const dataset = catalog.body.datasets[0];
if (!dataset)
  throw new Error('Import the 2024 publication before benchmarking');
const query = `?dataset=${dataset.id}`;
const players = (await get(`/api/players${query}&limit=20`)).body.players;
const batch = players.slice(0, 9).map((p) => p.profileId);
const requests = [
  ['catalog', '/api/datasets?season=2024'],
  ['players20', `/api/players${query}&limit=20`],
  ['catchers20', `/api/players${query}&position=C&limit=20`],
  ['profile', `/api/profiles/${batch[0]}${query}`],
  ['playerMetadata', `/api/players/${players[0].id}${query}`],
  [
    'profiles9',
    '/api/profiles/batch',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ datasetId: dataset.id, profileIds: batch }),
    },
  ],
];
const measurements = [];
for (const [name, path, options] of requests) {
  for (let i = 0; i < 5; i++) await get(path, options);
  const samples = [];
  for (let i = 0; i < 30; i++) samples.push(await get(path, options));
  const values = samples.map((s) => s.ms).sort((a, b) => a - b);
  const mean = values.reduce((a, b) => a + b) / values.length;
  measurements.push({
    name,
    responseBytes: samples[0].bytes,
    medianMs: (values[14] + values[15]) / 2,
    minMs: values[0],
    maxMs: values[29],
    sdMs: Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / 29),
    samplesMs: samples.map((s) => s.ms),
  });
}
const report = {
  schemaVersion: '1.0.0',
  measuredAt: new Date().toISOString(),
  origin: origin.origin,
  datasetId: dataset.id,
  warmups: 5,
  repetitions: 30,
  measurements,
  scope:
    'Local HTTP fetch through complete JSON response. No hosted CPU/cache/billing claim.',
};
mkdirSync('target', { recursive: true });
writeFileSync(
  resolve('target/m6a-api-performance.json'),
  JSON.stringify(report, null, 2) + '\n',
);
console.log(JSON.stringify(report, null, 2));
