import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { parseOpponents, withOpponents } from '../src/mlb/opponents';
import { parsePilot } from '../src/mlb/season-input';
import { nativeResult } from './helpers';
import { assembleRunnerSeason } from '../src/mlb/runner-transitions';

const publication = JSON.parse(
  readFileSync('data/publications/opponents-2024-v1.json', 'utf8'),
);
const fixture = JSON.parse(
  readFileSync('data/fixtures/dashboard-season-2024-v1.json', 'utf8'),
);
test('verified opponents reject missing, stale, altered, wrong-year and mismatched profiles', async () => {
  expect((await parseOpponents(publication)).opponents).toHaveLength(9);
  for (const bad of [
    null,
    { ...publication, id: 'stale' },
    { ...publication, year: 2023 },
    { ...publication, opponents: publication.opponents.slice(1) },
    { ...publication, profiles: publication.profiles.slice(1) },
  ])
    await expect(parseOpponents(bad)).rejects.toThrow();
  const pilot = await parsePilot(
    JSON.parse(
      readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
    ),
  );
  const input = await withOpponents(
    fixture,
    publication,
    pilot,
    publication.datasetId,
  );
  expect(input).toEqual(fixture);
  await expect(
    withOpponents(
      input,
      publication,
      { ...pilot, sourceId: 'wrong' },
      publication.datasetId,
    ),
  ).rejects.toThrow(/mismatch/);
  await expect(
    withOpponents(input, publication, pilot, 'wrong'),
  ).rejects.toThrow(/mismatch/);
  expect(new Set(input.profiles.map((p) => p.id)).size).toBe(
    input.profiles.length,
  );
});

test('expanded native fixture is deterministic, balances every opponent and retains the legacy fixture', () => {
  const full = nativeResult(fixture);
  expect(nativeResult(fixture)).toEqual(full);
  expect(full.games).toHaveLength(162);
  const reversed = structuredClone(fixture);
  reversed.opponents.reverse();
  expect(nativeResult(reversed).games).toEqual(full.games);
  for (const t of publication.opponents) {
    const games = full.games.filter(
      (g: { opponentId: string }) => g.opponentId === t.id,
    );
    expect(games).toHaveLength(18);
    expect(games.filter((g: { userHome: boolean }) => g.userHome)).toHaveLength(
      9,
    );
  }
  expect(
    nativeResult(
      JSON.parse(
        readFileSync(
          'crates/baseball-sim/tests/fixtures/season-modern-2024.json',
          'utf8',
        ),
      ),
    ).wins,
  ).toBe(105);
});

test('verified cached opponents are private frozen snapshots and conflicts still fail', async () => {
  const original = structuredClone(publication);
  const verified = await parseOpponents(original);
  expect(verified).not.toBe(original);
  expect(await parseOpponents(verified)).toBe(verified);
  expect(Object.isFrozen(verified.profiles[0].weights)).toBe(true);
  expect(() => {
    verified.profiles[0].weights.single++;
  }).toThrow();
  original.profiles[0].weights.single++;
  await expect(parseOpponents(original)).rejects.toThrow(/digest/);
  const pilot = await parsePilot(
    JSON.parse(
      readFileSync('apps/web/src/generated/mlb-pilot-2024.json', 'utf8'),
    ),
  );
  const once = await withOpponents(
    fixture,
    verified,
    pilot,
    verified.datasetId,
  );
  expect(
    await withOpponents(fixture, verified, pilot, verified.datasetId),
  ).toEqual(once);
  const changed = structuredClone(fixture);
  const shared = changed.profiles.find(
    (p: { id: string }) =>
      verified.profiles.some((r) => r.id === p.id) &&
      changed.userTeam.lineup.some(
        (b: { profileId: string }) => b.profileId === p.id,
      ),
  );
  expect(shared).toBeTruthy();
  shared.weights.single++;
  await expect(
    withOpponents(changed, verified, pilot, verified.datasetId),
  ).rejects.toThrow(/Conflicting/);
  await expect(
    withOpponents(
      fixture,
      verified,
      { ...pilot, leagueContextId: 'wrong' },
      verified.datasetId,
    ),
  ).rejects.toThrow(/mismatch/);
});
test('runner transition assembly is explicit, preserves profiles and rejects defense or tampering', async () => {
  const experimental = JSON.parse(
    readFileSync('data/fixtures/runner-season-2024-v1.json', 'utf8'),
  );
  const assembled = await assembleRunnerSeason(
    fixture,
    experimental.config.contextualModel,
  );
  expect(assembled.schemaVersion).toBe('1.2.0');
  expect(assembled.profiles).toEqual(fixture.profiles);
  expect(assembled.opponents).toEqual(fixture.opponents);
  expect(fixture.gameSchemaVersion).toBe('1.2.0');
  await expect(
    assembleRunnerSeason(fixture, {
      ...experimental.config.contextualModel,
      id: 'altered',
    }),
  ).rejects.toThrow();
  const defensive = JSON.parse(
    readFileSync('data/fixtures/defense-season-2024-v1.json', 'utf8'),
  );
  await expect(
    assembleRunnerSeason(defensive, experimental.config.contextualModel),
  ).rejects.toThrow();
});
