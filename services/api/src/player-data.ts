// Storage and bounded SQL only. No profile generation, simulation or draft rules.
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

export interface DatasetRow {
  id: string;
  source_id: string;
  year: number;
  metadata_json: string;
  attribution_json: string;
}

export class PlayerData {
  constructor(private db: D1Database) {}

  async seasons(after: number, limit: number) {
    return (
      await this.db
        .prepare(
          `SELECT DISTINCT d.year FROM mlb_datasets d
      JOIN mlb_publications p ON p.dataset_id=d.id WHERE d.year>? ORDER BY d.year LIMIT ?`,
        )
        .bind(after, limit)
        .all<{ year: number }>()
    ).results;
  }

  async datasets(after: string, year: number | null, limit: number) {
    const where = year === null ? 'd.id>?' : 'd.year=? AND d.id>?';
    const args = year === null ? [after, limit] : [year, after, limit];
    return (
      await this.db
        .prepare(
          `SELECT d.id, d.source_id, d.year,
      json_remove(d.metadata_json, '$.context') AS metadata_json, s.attribution_json FROM mlb_datasets d
      JOIN mlb_publications p ON p.dataset_id=d.id JOIN mlb_sources s ON s.id=d.source_id
      WHERE ${where} ORDER BY d.id LIMIT ?`,
        )
        .bind(...args)
        .all<DatasetRow>()
    ).results;
  }

  async dataset(id: string, includeContext = false): Promise<DatasetRow> {
    const row = await this.db
      .prepare(
        `SELECT d.id, d.source_id, d.year,
      ${includeContext ? 'd.metadata_json' : "json_set(json_remove(d.metadata_json, '$.context'), '$.contextId', json_extract(d.metadata_json, '$.context.id'))"} AS metadata_json,
      s.attribution_json FROM mlb_datasets d
      JOIN mlb_publications p ON p.dataset_id=d.id JOIN mlb_sources s ON s.id=d.source_id WHERE d.id=?`,
      )
      .bind(id)
      .first<DatasetRow>();
    if (!row)
      throw new ApiError(404, 'datasetNotFound', 'Published dataset not found');
    const meta = JSON.parse(row.metadata_json);
    if (
      meta.schemaVersion !== '1.0.0' ||
      meta.inputSchemaVersion !== '1.2.0' ||
      meta.modelVersion !== 'lahman-contact-adapter-v1'
    )
      throw new ApiError(
        409,
        'incompatibleProfileVersion',
        'Dataset requires an unsupported profile or input schema',
      );
    return row;
  }

  async players(
    dataset: string,
    position: string | null,
    after: number,
    limit: number,
  ) {
    const pool =
      position === null ? 'mlb_dataset_profiles' : 'mlb_dataset_positions';
    const where = position === null ? '' : ' AND pool.position=?';
    const args =
      position === null
        ? [dataset, after, limit]
        : [dataset, position, after, limit];
    return (
      await this.db
        .prepare(
          `SELECT p.id, p.display_name AS displayName, pool.profile_id AS profileId,
      pool.ordinal${position === null ? '' : ', pool.games AS positionGames'} FROM ${pool} pool
      JOIN mlb_profiles profile ON profile.id=pool.profile_id
      JOIN mlb_players p ON p.source_id=profile.source_id AND p.id=profile.player_id
      WHERE pool.dataset_id=?${where} AND pool.ordinal>? ORDER BY pool.ordinal LIMIT ?`,
        )
        .bind(...args)
        .all<{
          id: string;
          displayName: string;
          profileId: string;
          ordinal: number;
          positionGames?: number;
        }>()
    ).results;
  }

  async profiles(dataset: string, ids: string[]) {
    const rows = (
      await this.db
        .prepare(
          `SELECT p.id, p.payload_json, p.input_schema_version, p.model_version
      FROM mlb_profiles p JOIN mlb_dataset_profiles m ON m.profile_id=p.id
      WHERE m.dataset_id=? AND m.profile_id IN (${ids.map(() => '?').join(',')})`,
        )
        .bind(dataset, ...ids)
        .all<{
          id: string;
          payload_json: string;
          input_schema_version: string;
          model_version: string;
        }>()
    ).results;
    const byId = new Map(rows.map((row) => [row.id, row]));
    const missing = ids.filter((id) => !byId.has(id));
    if (missing.length)
      throw new ApiError(
        404,
        'profileNotFound',
        'One or more profiles are absent from this dataset',
        { missing },
      );
    return ids.map((id) => {
      const row = byId.get(id)!;
      if (
        row.input_schema_version !== '1.2.0' ||
        row.model_version !== 'lahman-contact-adapter-v1'
      )
        throw new ApiError(
          409,
          'incompatibleProfileVersion',
          'Profile requires an unsupported model or input schema',
        );
      return JSON.parse(row.payload_json) as Record<string, unknown>;
    });
  }

  async player(dataset: DatasetRow, id: string) {
    const player = await this.db
      .prepare(
        `SELECT p.id, p.display_name AS displayName, p.lahman_id AS lahmanId,
      p.metadata_json, m.profile_id AS profileId FROM mlb_dataset_profiles m
      JOIN mlb_players p ON p.source_id=m.source_id AND p.id=m.player_id
      WHERE m.dataset_id=? AND m.player_id=?`,
      )
      .bind(dataset.id, id)
      .first<{
        id: string;
        displayName: string;
        lahmanId: string;
        metadata_json: string;
        profileId: string;
      }>();
    if (!player)
      throw new ApiError(
        404,
        'playerNotFound',
        'Player not found in this dataset',
      );
    const args = [dataset.source_id, id, dataset.year];
    const [stints, positions] = await this.db.batch<Record<string, unknown>>([
      this.db
        .prepare(
          `SELECT b.stint, b.team_id AS teamId, b.league_id AS leagueId,
        t.name AS teamName, t.franchise_id AS franchiseId, f.name AS franchiseName,
        b.counts_json, b.source_row AS sourceRow FROM mlb_batting_stints b
        JOIN mlb_team_seasons t ON t.source_id=b.source_id AND t.year=b.year AND t.team_id=b.team_id AND t.league_id=b.league_id
        JOIN mlb_franchises f ON f.source_id=t.source_id AND f.id=t.franchise_id
        WHERE b.source_id=? AND b.player_id=? AND b.year=? ORDER BY b.stint, b.team_id, b.league_id LIMIT 101`,
        )
        .bind(...args),
      this.db
        .prepare(
          `SELECT team_id AS teamId, league_id AS leagueId, position, games, source_row AS sourceRow
        FROM mlb_position_appearances WHERE source_id=? AND player_id=? AND year=?
        ORDER BY team_id, league_id, position LIMIT 101`,
        )
        .bind(...args),
    ]);
    if (stints.results.length > 100 || positions.results.length > 100)
      throw new ApiError(
        422,
        'metadataTooLarge',
        'Player metadata exceeds the supported response size',
      );
    const { metadata_json, ...identity } = player;
    return {
      ...identity,
      metadata: JSON.parse(metadata_json),
      year: dataset.year,
      stints: stints.results.map(({ counts_json, ...stint }) => ({
        ...stint,
        counts: JSON.parse(counts_json as string),
      })),
      positions: positions.results,
    };
  }
}
