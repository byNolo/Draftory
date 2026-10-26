# D1 migrations

`0001_mlb_player_data.sql` adds the M6A selected-player data foundation after
Lahman exploration. Wrangler resolves this directory from
`services/api/wrangler.jsonc`. See [the data API guide](../../../docs/PLAYER_DATA_API.md)
for schema decisions, deterministic exports and the local import workflow.

Run `npm run d1:migrate --workspace @draftory/api` to apply pending migrations
locally. `npm run d1:check --workspace @draftory/api` executes `SELECT 1`.
The all-zero database ID remains a local sentinel; no cloud database has been
provisioned. Use `--local` for all imports. Production deployment needs separate
approval and a deliberately configured database.
