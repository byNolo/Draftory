# Contributing to Draftory

Start with the [README](README.md) for prerequisites and local commands, and
[AGENTS.md](AGENTS.md) for architecture boundaries and coding conventions. The
planning documents linked there define scope and unresolved decisions.

1. Create a focused branch from `main`; use `codex/` for agent-created branches.
2. Keep changes within the agreed milestone. Discuss statistical models and
   permanent data schemas before implementing them.
3. Install from the committed lockfiles with `npm ci` and `uv sync --locked`
   inside `data/pipeline`. Update the appropriate lockfile when dependencies change.
4. Run the JavaScript, Rust and Python validation commands in the README. Regenerate
   Worker types after configuration changes. Add behavioral tests for new behavior.
5. Open a pull request describing the resulting behavior, validation, and any
   limitations. All three foundation CI jobs should pass before merging.

Commit only source, configuration, documentation and small synthetic fixtures.
Keep credentials, local databases, raw releases and generated datasets out of Git.
Cloudflare commands remain local during foundation work; CI does not deploy.
