# Shared contracts

Language-neutral JSON Schema is the source of truth for exchanged artifacts.
`source-manifest.schema.json` v0.1.0 defines acquisition provenance: original
archive URL, UTC retrieval timestamp, release label, archive SHA-256 and extracted
file SHA-256 values. Retain upstream readme and license files alongside raw inputs
and include them in the file list. A checksum identifies bytes; it does not prove
upstream authenticity unless independently published and verified.

The synthetic fixture under `data/fixtures/` uses deliberately fake checksums and
an invalid example domain; it is not evidence of an acquired Lahman release.
Python tests validate the schema and reject missing/invalid provenance.

The data foundation adds:

- `normalized-lahman-record.schema.json`: definitions for eight JSONL fact files,
  including player, stint, season, team-season, appearance and fielding records.
- `normalized-lahman-manifest.schema.json`: source lock identity, output row counts
  and SHA-256 values for normalized artifacts.
- `batting-profile.schema.json`: preliminary descriptive profiles, explicit
  aggregation/filter requests, sample lineage and insufficient-data results.

See [the data workflow](../docs/LAHMAN_DATA_FOUNDATION.md) for field semantics,
canonical profile hashes, examples and restrictions on simulation use. The source
is an official folder, so the pipeline uses its own v1 acquisition receipt and
per-file lock, rather than claiming the archive-oriented v0.1 example is a real
import manifest.

Do not turn the illustrative PA vector or TypeScript interface in the planning
documents into a final simulation contract yet. Add sport-specific schemas and
cross-language fixtures when consumers exist. Breaking artifact changes require
a schema version bump and coordinated fixture/consumer updates; producer, source,
model and rules versions remain separate concepts.
