-- MLB-specific facts; a second sport should add its own tables and contracts.
CREATE TABLE mlb_sources (
  id TEXT PRIMARY KEY NOT NULL,
  provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
  attribution_json TEXT NOT NULL CHECK (json_valid(attribution_json))
) STRICT;

CREATE TABLE mlb_players (
  source_id TEXT NOT NULL REFERENCES mlb_sources(id),
  id TEXT NOT NULL,
  lahman_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
  source_row INTEGER NOT NULL CHECK (source_row >= 2),
  PRIMARY KEY (source_id, id),
  UNIQUE (source_id, lahman_id)
) STRICT;

CREATE TABLE mlb_franchises (
  source_id TEXT NOT NULL REFERENCES mlb_sources(id),
  id TEXT NOT NULL,
  name TEXT,
  PRIMARY KEY (source_id, id)
) STRICT;

CREATE TABLE mlb_team_seasons (
  source_id TEXT NOT NULL,
  year INTEGER NOT NULL CHECK (year BETWEEN 1871 AND 2100),
  team_id TEXT NOT NULL,
  league_id TEXT NOT NULL,
  franchise_id TEXT NOT NULL,
  name TEXT,
  source_row INTEGER NOT NULL CHECK (source_row >= 2),
  PRIMARY KEY (source_id, year, team_id, league_id),
  FOREIGN KEY (source_id, franchise_id) REFERENCES mlb_franchises(source_id, id)
) STRICT;

-- Full-season counts derive from stints; never join appearances into batting sums.
CREATE TABLE mlb_player_seasons (
  source_id TEXT NOT NULL,
  player_id TEXT NOT NULL,
  year INTEGER NOT NULL CHECK (year BETWEEN 1871 AND 2100),
  PRIMARY KEY (source_id, player_id, year),
  FOREIGN KEY (source_id, player_id) REFERENCES mlb_players(source_id, id)
) STRICT;

CREATE TABLE mlb_batting_stints (
  source_id TEXT NOT NULL,
  player_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  stint INTEGER NOT NULL CHECK (stint >= 1),
  team_id TEXT NOT NULL,
  league_id TEXT NOT NULL,
  counts_json TEXT NOT NULL CHECK (json_valid(counts_json)),
  source_row INTEGER NOT NULL CHECK (source_row >= 2),
  PRIMARY KEY (source_id, player_id, year, stint, team_id, league_id),
  FOREIGN KEY (source_id, player_id, year) REFERENCES mlb_player_seasons(source_id, player_id, year),
  FOREIGN KEY (source_id, year, team_id, league_id) REFERENCES mlb_team_seasons(source_id, year, team_id, league_id)
) STRICT;

CREATE TABLE mlb_position_appearances (
  source_id TEXT NOT NULL,
  player_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  team_id TEXT NOT NULL,
  league_id TEXT NOT NULL,
  position TEXT NOT NULL CHECK (position IN ('P','C','1B','2B','3B','SS','LF','CF','RF','OF','DH')),
  games INTEGER CHECK (games >= 0),
  source_row INTEGER NOT NULL CHECK (source_row >= 2),
  PRIMARY KEY (source_id, player_id, year, team_id, league_id, position),
  FOREIGN KEY (source_id, player_id, year) REFERENCES mlb_player_seasons(source_id, player_id, year),
  FOREIGN KEY (source_id, year, team_id, league_id) REFERENCES mlb_team_seasons(source_id, year, team_id, league_id)
) STRICT;

CREATE TABLE mlb_profiles (
  id TEXT PRIMARY KEY NOT NULL,
  source_id TEXT NOT NULL,
  player_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  input_schema_version TEXT NOT NULL,
  historical_profile_id TEXT NOT NULL,
  aggregation TEXT NOT NULL CHECK (aggregation IN ('aggregate','season_rate_mean','season_rate_median')),
  definition_json TEXT NOT NULL CHECK (json_valid(definition_json)),
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json) AND length(payload_json) <= 16384),
  UNIQUE (id, source_id, player_id),
  FOREIGN KEY (source_id, player_id) REFERENCES mlb_players(source_id, id),
  CHECK (json_extract(payload_json, '$.id') IS id),
  CHECK (json_extract(payload_json, '$.modelVersion') IS model_version),
  CHECK (json_extract(payload_json, '$.provenance.playerId') IS player_id),
  CHECK (json_extract(payload_json, '$.provenance.sourceId') IS source_id)
) STRICT;

CREATE TABLE mlb_datasets (
  id TEXT PRIMARY KEY NOT NULL,
  source_id TEXT NOT NULL REFERENCES mlb_sources(id),
  year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2025),
  metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
  UNIQUE (id, source_id, year)
) STRICT;
CREATE INDEX mlb_datasets_year ON mlb_datasets(year, id);

CREATE TABLE mlb_dataset_profiles (
  dataset_id TEXT NOT NULL,
  profile_id TEXT NOT NULL REFERENCES mlb_profiles(id),
  source_id TEXT NOT NULL,
  player_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  PRIMARY KEY (dataset_id, ordinal),
  UNIQUE (dataset_id, profile_id),
  UNIQUE (dataset_id, player_id),
  FOREIGN KEY (profile_id, source_id, player_id) REFERENCES mlb_profiles(id, source_id, player_id),
  FOREIGN KEY (dataset_id, source_id, year) REFERENCES mlb_datasets(id, source_id, year),
  FOREIGN KEY (source_id, player_id, year) REFERENCES mlb_player_seasons(source_id, player_id, year)
) STRICT;

-- Position observations, not gameplay eligibility. Dense ordinals enable future
-- uniform random integer -> indexed lookup without sorting the historical table.
CREATE TABLE mlb_dataset_positions (
  dataset_id TEXT NOT NULL,
  position TEXT NOT NULL CHECK (position IN ('P','C','1B','2B','3B','SS','LF','CF','RF','OF','DH')),
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  profile_id TEXT NOT NULL,
  games INTEGER NOT NULL CHECK (games > 0),
  PRIMARY KEY (dataset_id, position, ordinal),
  UNIQUE (dataset_id, position, profile_id),
  FOREIGN KEY (dataset_id, profile_id) REFERENCES mlb_dataset_profiles(dataset_id, profile_id)
) STRICT;

-- Insert last. Incomplete imports are invisible to the public API.
CREATE TABLE mlb_publications (
  dataset_id TEXT PRIMARY KEY NOT NULL REFERENCES mlb_datasets(id),
  player_count INTEGER NOT NULL CHECK (player_count > 0),
  position_counts_json TEXT NOT NULL CHECK (json_valid(position_counts_json))
) STRICT;

CREATE TRIGGER mlb_publication_complete BEFORE INSERT ON mlb_publications BEGIN
  SELECT RAISE(ABORT, 'Incomplete dataset membership') WHERE
    NEW.player_count != (SELECT count(*) FROM mlb_dataset_profiles WHERE dataset_id=NEW.dataset_id)
    OR NEW.player_count != (SELECT max(ordinal)+1 FROM mlb_dataset_profiles WHERE dataset_id=NEW.dataset_id);
  SELECT RAISE(ABORT, 'Inconsistent position pool') WHERE EXISTS (
    SELECT 1 FROM json_each(NEW.position_counts_json) AS j
    WHERE j.value != (SELECT count(*) FROM mlb_dataset_positions WHERE dataset_id=NEW.dataset_id AND position=j.key)
       OR j.value != (SELECT max(ordinal)+1 FROM mlb_dataset_positions WHERE dataset_id=NEW.dataset_id AND position=j.key)
  ) OR (SELECT count(*) FROM json_each(NEW.position_counts_json)) !=
    (SELECT count(DISTINCT position) FROM mlb_dataset_positions WHERE dataset_id=NEW.dataset_id);
END;
