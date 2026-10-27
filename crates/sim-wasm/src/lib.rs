//! JSON stays at the host boundary; baseball rules and RNG remain in baseball-sim.
use baseball_sim::{SeasonError, SeasonInput, simulate_season};
use serde::Serialize;
use std::fmt;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BoundaryError {
    pub code: &'static str,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub game_number: Option<u16>,
}
impl fmt::Display for BoundaryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}
impl std::error::Error for BoundaryError {}

/// Shared native/WASM boundary. Never decodes u64 seeds through a JS number.
pub fn simulate_json(input_json: &str) -> Result<String, BoundaryError> {
    simulate_measured(input_json, false, || 0.0).map(|run| run.result_json)
}

pub struct MeasuredRun {
    pub result_json: String,
    /// Input decode, simulation (including validation), serialization, UTF-8 bytes.
    pub measurements: [f64; 4],
}

/// Clock belongs to the adapter/host, never to the deterministic simulation core.
pub fn simulate_measured(
    input_json: &str,
    compact: bool,
    now: impl FnMut() -> f64,
) -> Result<MeasuredRun, BoundaryError> {
    project_measured(
        input_json,
        if compact {
            Projection::Summary
        } else {
            Projection::Full
        },
        now,
    )
}

#[derive(Clone, Copy)]
pub enum Projection {
    Full,
    Summary,
    Batting,
}

pub fn project_measured(
    input_json: &str,
    projection: Projection,
    mut now: impl FnMut() -> f64,
) -> Result<MeasuredRun, BoundaryError> {
    let start = now();
    let input: SeasonInput = serde_json::from_str(input_json).map_err(|error| BoundaryError {
        code: "invalidJson",
        message: error.to_string(),
        game_number: None,
    })?;
    let decoded = now();
    let result = simulate_season(input).map_err(|error| BoundaryError {
        code: if matches!(error, SeasonError::GameFailed { .. }) {
            "gameFailed"
        } else {
            "invalidInput"
        },
        message: error.to_string(),
        game_number: match error {
            SeasonError::GameFailed { game_number, .. } => Some(game_number),
            _ => None,
        },
    })?;
    let simulated = now();
    // Project computed fields before serialization, avoiding full boxes/input/log JSON
    // when React only needs a summary. Full output remains byte-for-byte compatible.
    let encoded = if !matches!(projection, Projection::Full) {
        let mut summary = serde_json::json!({
            "schemaVersion":result.schema_version,"engineVersion":result.engine_version,
            "seed":result.input.seed,"games":result.games.len(),"wins":result.wins,
            "losses":result.losses,"runsScored":result.runs_scored,"runsAllowed":result.runs_allowed,
            "runDifferential":result.run_differential
        });
        if matches!(projection, Projection::Batting) {
            summary["batting"] = serde_json::json!({
                "schemaVersion": "1.0.0", "teamId": result.team.team_id,
                "totals": result.team.totals, "batters": result.team.batters
            });
        }
        serde_json::to_string(&summary)
    } else {
        serde_json::to_string(&result)
    };
    let result_json = encoded.map_err(|error| BoundaryError {
        code: "serializationFailed",
        message: error.to_string(),
        game_number: None,
    })?;
    let serialized = now();
    let bytes = result_json.len() as f64;
    Ok(MeasuredRun {
        result_json,
        measurements: [
            decoded - start,
            simulated - decoded,
            serialized - simulated,
            bytes,
        ],
    })
}

#[cfg(target_arch = "wasm32")]
mod browser {
    use super::*;
    use std::cell::Cell;
    use wasm_bindgen::prelude::*;

    #[wasm_bindgen]
    extern "C" {
        #[wasm_bindgen(js_namespace = performance, js_name = now)]
        fn clock_ms() -> f64;
    }
    thread_local! { static MEASUREMENTS: Cell<[f64; 4]> = const { Cell::new([0.0; 4]) }; }

    fn execute(input: &str, projection: Projection) -> Result<String, JsValue> {
        project_measured(input, projection, clock_ms)
            .map(|run| {
                MEASUREMENTS.set(run.measurements);
                run.result_json
            })
            .map_err(|error| {
                wasm_bindgen::JsValue::from_str(
                    &serde_json::to_string(&error)
                        .expect("boundary error contains only JSON-safe values"),
                )
            })
    }

    #[wasm_bindgen]
    pub fn simulate_season_json(input_json: &str) -> Result<String, JsValue> {
        execute(input_json, Projection::Full)
    }

    #[wasm_bindgen]
    pub fn simulate_season_summary_json(input_json: &str) -> Result<String, JsValue> {
        execute(input_json, Projection::Summary)
    }

    #[wasm_bindgen]
    pub fn simulate_season_batting_json(input_json: &str) -> Result<String, JsValue> {
        execute(input_json, Projection::Batting)
    }

    /// Diagnostics for the last successful call in this single-request worker.
    #[wasm_bindgen]
    pub fn last_run_measurements() -> Box<[f64]> {
        MEASUREMENTS.get().into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = include_str!("../../baseball-sim/tests/fixtures/season-modern-2024.json");

    #[test]
    fn json_boundary_matches_core_and_preserves_large_seeds() {
        let mut input: SeasonInput = serde_json::from_str(FIXTURE).unwrap();
        input.seed = u64::MAX.to_string();
        input.games = 2;
        let boundary = simulate_json(&serde_json::to_string(&input).unwrap()).unwrap();
        assert_eq!(
            serde_json::from_str::<serde_json::Value>(&boundary).unwrap(),
            serde_json::to_value(simulate_season(input).unwrap()).unwrap()
        );
    }

    #[test]
    fn invalid_json_input_and_aborted_games_have_distinct_errors() {
        assert_eq!(simulate_json("{").unwrap_err().code, "invalidJson");
        let mut input: SeasonInput = serde_json::from_str(FIXTURE).unwrap();
        input.games = 0;
        assert_eq!(
            simulate_json(&serde_json::to_string(&input).unwrap())
                .unwrap_err()
                .code,
            "invalidInput"
        );
        input.games = 162;
        input.config.max_plate_appearances = 1;
        let error = simulate_json(&serde_json::to_string(&input).unwrap()).unwrap_err();
        assert_eq!(error.code, "gameFailed");
        assert_eq!(error.game_number, Some(1));
    }

    #[test]
    fn batting_projection_preserves_core_totals_and_large_seed_in_both_modes() {
        for detail in ["summary", "events"] {
            let mut value: serde_json::Value = serde_json::from_str(FIXTURE).unwrap();
            value["detail"] = detail.into();
            value["seed"] = u64::MAX.to_string().into();
            let input = value.to_string();
            let full: serde_json::Value =
                serde_json::from_str(&simulate_json(&input).unwrap()).unwrap();
            let compact = project_measured(&input, Projection::Batting, || 0.0).unwrap();
            let result: serde_json::Value = serde_json::from_str(&compact.result_json).unwrap();
            assert_eq!(result["batting"]["totals"], full["team"]["totals"]);
            assert_eq!(result["batting"]["batters"], full["team"]["batters"]);
            assert_eq!(result["seed"], value["seed"]);
            assert_eq!(result["wins"], full["wins"]);
            assert_eq!(result["runsScored"], full["runsScored"]);
            assert_eq!(result["games"], 162);
            assert!(compact.result_json.len() < 6000);
            assert!(compact.result_json.len() < full.to_string().len() / 10);
        }
    }

    #[test]
    fn compact_summary_matches_full_output_in_both_detail_modes() {
        for detail in ["summary", "events"] {
            let mut value: serde_json::Value = serde_json::from_str(FIXTURE).unwrap();
            value["detail"] = detail.into();
            value["seed"] = u64::MAX.to_string().into();
            value["games"] = 2.into();
            let input = value.to_string();
            let full: serde_json::Value =
                serde_json::from_str(&simulate_json(&input).unwrap()).unwrap();
            let mut ticks = 0.0;
            let compact = simulate_measured(&input, true, || {
                ticks += 1.0;
                ticks
            })
            .unwrap();
            let summary: serde_json::Value = serde_json::from_str(&compact.result_json).unwrap();
            assert_eq!(summary["seed"], full["input"]["seed"]);
            assert_eq!(summary["games"], full["games"].as_array().unwrap().len());
            for field in [
                "schemaVersion",
                "engineVersion",
                "wins",
                "losses",
                "runsScored",
                "runsAllowed",
                "runDifferential",
            ] {
                assert_eq!(summary[field], full[field]);
            }
            assert_eq!(&compact.measurements[..3], &[1.0; 3]);
            assert_eq!(compact.measurements[3], compact.result_json.len() as f64);
            assert!(compact.result_json.len() < 300);
        }
    }
}
