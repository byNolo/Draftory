# Runner outs and advancement — experimental M9B.1

This opt-in mode replaces a source-supported subset of v1 runner proxies. It
does not change Lahman outcome weights, smoothing, sacrifices, between-PA events,
defender ability, schedules, prices or the default game. See the
[completion report](../data/validation/runner-transitions-v1.md) and
[measurements](../data/validation/runner-transitions-v1.json).

## Source selection and evidence

`draftory_data.runner_transitions` verifies the unchanged M4 Retrosheet lock and
separate 2024 development-play lock. Fit uses only full regular-season PAs in
innings 1–8 of 2022/2023, excluding SH/SF, with the same single/double/residual
taxonomy and 50-observation cell floor. All 211,000 selected training observations
remain in their original base/out/event denominators. Unknown and compound cases
remain counted conservative proxies. 2024 is inspected development data; 2025 is
already inspected evidence and is not a new holdout. No 2025 plays are read here.

The fitter retains v1's already supported choices. For promotion it reconciles
actual batter/pre-runner IDs against post bases, scorer IDs, outs delta, RBI flags,
explicit raw advances and terminal LOB IDs. A restricted advancement parser accepts
`B/1/2/3` origins, safe/out destinations and simple parenthesized qualifiers. It
does not infer chronology from semicolon order. Errors on an apparent out,
appeals, uncertain records, compound events and unresolved identities remain
proxied. The parser is not a general Retrosheet interpreter.

Supported promotions:

- Single/double batter or existing-runner tag outs attempting an additional base.
  The raw attempted destination and parsed running-out evidence must agree.
- Extra batter advancement on a hit, including joint movement of existing runners.
  The credited event remains single/double even when the batter ends farther along.
- One explicitly identified force-choice retirement, with `/FO`, an occupied force
  chain, and source-confirmed batter survival. In these source windows the promoted
  force outs are at second, principally restoring terminal FC identity/credit.
- A single non-force third out with source-credited runs: those runs necessarily
  preceded the third out. This supports a bounded timing case without inventing
  play chronology. A non-terminal out plus runs does not prove their order and
  stays proxied.

After an inning-ending play, post-base columns are empty. Source LOB IDs establish
survivors. Their bookkeeping destinations use explicit safe advances when present,
otherwise the credited hit base or unchanged starting base. These are conservative
stranding positions, not reconstructed movement after the third out; they never
continue into a new half. Exact identity, outs, scoring and LOB must reconcile.

Multiple runner movements are supported; multiple new running outs, other double
plays/triple plays, complex appeals, unproven force removal, triples' running outs,
and unknown run/out chronology remain unsupported. V1 GDP geometry and suppression
remain unchanged. No sacrifice event is introduced by a safe advancing contact.
In particular, zero-out GDP advances/runs retain the v1 conservative hold/suppress
proxy; multiple-retirement scoring order is not inferred by this extension.

## Representation and rules

The 72-cell joint table retains `destinations[4]`, per-runner `rbi`, and optional
reach classification. Destinations identify batter, original first-, second- and
third-base runners: 0=retired, 1–3=base, 4=run, 5=absent. They index identities
already present in the game; the transition cannot introduce a new player.

Promoted choices additionally carry `runnerPlay`:

```json
{
  "outKinds": ["none", "tag", "none", "none"],
  "outBases": [0, 4, 0, 0],
  "runsBeforeOuts": true
}
```

`outBases` is the attempted base (4=home), zero for a survivor. `tag` and `force`
are supported new retirement kinds; `batterBeforeFirst` is reserved by the type
but not accepted as a promoted choice in this version. Existing ordinary batter
outs retain v1 handling. `runsBeforeOuts` is accepted only for runs preceding the
sole tag third out. Choices without metadata retain the documented v1 resolver.
Timing scorers must start ahead of the later retired runner; otherwise the claimed order would require passing that runner. Both the fitter and Rust reject it.
That includes v1's existing ordering assumptions for already-supported advancing
outs/choices; the new mode does not claim complete chronology for those old cases.

Rust validates presence, monotonic surviving runner order, no collisions/backward
advances, legal attempted bases and force-chain eligibility, outs limits, hit versus
reach classification and timing. A hit cannot contain a force retirement or an out
attempt before its credited hit base. Sampling selects one complete legal outcome;
there is no extra retirement roll. New metadata uses fixed arrays, not per-PA
vectors or host calls. Existing scorer/runner structures are reused.

Third force outs suppress every run; normal batter-before-first third outs and
GDP retain v1 suppression. A proven timing-third-out run may count. If it is the
winning run in a bottom ninth/later, the game ends before the later tag retirement,
so that retirement is not credited. RBI follows the actual retained scorer flags.
Non-HR walk-off hit credit keeps the existing winning-run limit. The batting cursor
advances exactly once for the PA; embedded runner actions never consume a batter.
At terminal plays, conservation accounts for all stranded identities, including
suppressed would-be scorers and canceled later retirements.

## Versions and compatibility

| Boundary                | Explicit opt-in identifier               |
| ----------------------- | ---------------------------------------- |
| Game input              | 1.4.0, `runner-game-input.schema.json`   |
| Season input            | 1.2.0, `runner-season-input.schema.json` |
| Game/season result      | 1.2.0, separate runner result schemas    |
| Rules                   | `runner-outs-nine-inning-v1`             |
| Advancement policy      | `retrosheet-runner-outs-v1`              |
| Transition model        | `retrosheet-runner-transitions-v1`       |
| Model content ID prefix | `runner-transitions:`                    |

The engine package metadata remains 0.4.0, as with the earlier defense extension,
to preserve legacy goldens. The new rules/schema/model tuple identifies behavior.
New inputs reject old models, and old/defensive inputs reject the new model or
metadata. Defense under the new mode is explicitly incompatible: its immutable
v1 error mapping has not been revalidated against these choices. No defensive
artifact or rating is rewritten or silently translated.

Original game/season inputs, profiles, RNG draw ordering and saved-run meanings
remain unchanged. Scheduler, root/game seed derivation and summary/events sampling
are shared. The new model can change conditional ticket consumption where a cell
gains choices; identical seeds do not imply the two models follow identical plays.

`assembleRunnerSeason` is an explicit diagnostic assembly function: it checks a
neutral legacy input, source identity and the new model's canonical content ID,
then creates a new input. It does not mutate the old input or activate a gameplay
setting. The current single-opponent and nine-opponent paths remain available.
The existing Worker/WASM adapter accepts the versioned JSON; React still receives
compact computed dashboard/batting data unless detailed output is explicitly
requested. No new transport, server, full-trace UI or D1 schema is needed.

## Reproduce locally

Use the existing verified sources and installed Python environment; no download,
source-lock update or publication rewrite is necessary:

```powershell
$py = '.\data\pipeline\.venv\Scripts\python.exe'
& $py -m draftory_data.runner_transitions --output-dir data/processed/m9b1/verified
cargo build --locked --release --examples
target/release/examples/season.exe data/processed/m9b1/verified/season.json
& $py -m draftory_data.runner_validation --run
```

The producer refuses different bytes at an existing model output. Full source
classifications and experiment rows stay ignored under `data/processed/m9b1`.
The attributed `data/fixtures/runner-season-2024-v1.json` is the small shared
native/browser fixture using the existing NYA/CHA observed orders and unchanged
profiles, not an authentic full-roster season. Source-backed tests reconstruct its
complete model from the locks; ordinary tests require no raw source.

Run native performance collection **after** heavy test/build jobs finish:

```powershell
& $py -m draftory_data.runner_validation --measure-native
npx playwright test --grep "runner transitions opt-in" --project chromium --project firefox --project webkit --project edge --project mobile-chromium --project mobile-webkit
```

Browser runs write new measurement files under ignored `target/m9b1`. The test
checks full native/WASM event parity at seeds zero/max-u64, repeated seeds and
compact dashboard parity before recording size, timing and WASM memory samples.
These are desktop/emulation measurements, not physical phone or WAN benchmarks.

## Remaining work

M9B.2 should address contextual SH/SF and official PA/AB/RBI/OBP accounting under
new profile/rules IDs, while retaining this runner resolution and legacy replay.
Do not insert unconditional sacrifice outcomes into impossible states or adjust
run totals to hide residual errors. Between-PA running, explicit contact types,
catcher/OF defense and pitching heterogeneity remain separate work. M9B.2 is not
implemented or started here.
