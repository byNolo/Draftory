import { DataError, object } from '../lib/api/player-data';
import { hash, type SeasonInput } from './season-input';

// Explicit diagnostic opt-in. Gameplay's default assembly and published opponents
// remain v1; Rust validates every joint outcome before executing this JSON.
export async function assembleRunnerSeason(
  input: SeasonInput,
  supplied: unknown,
) {
  const model = object(supplied);
  const { id, ...body } = model;
  if (
    input.schemaVersion !== '1.0.0' ||
    input.gameSchemaVersion !== '1.2.0' ||
    input.rulesVersion !== 'contextual-nine-inning-v1' ||
    input.config.advancementPolicy !== 'retrosheet-contextual-v1' ||
    'defense' in input.config ||
    model.modelVersion !== 'retrosheet-runner-transitions-v1' ||
    model.sourceId !== input.config.contextualModel.sourceId ||
    id !== 'runner-transitions:' + (await hash(body))
  )
    throw new DataError(
      'incompatibleInput',
      'Runner transitions require a verified new model and neutral legacy input; defense is incompatible.',
    );
  return {
    ...input,
    schemaVersion: '1.2.0',
    gameSchemaVersion: '1.4.0',
    rulesVersion: 'runner-outs-nine-inning-v1',
    config: {
      ...input.config,
      advancementPolicy: 'retrosheet-runner-outs-v1',
      contextualModel: model,
    },
  };
}
