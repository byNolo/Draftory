# D1 migrations

No application tables yet. Add numbered SQL migrations only after Lahman source
exploration and schema review. Wrangler resolves this directory from
`services/api/wrangler.jsonc`.

From the repository root, `npm run d1:check --workspace @draftory/api` executes
`SELECT 1` against local D1 without creating application tables. All database
commands during foundation work must use `--local`. The configured all-zero ID
is a local sentinel; no cloud database exists and this configuration is not
ready for deployment.
