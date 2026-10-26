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
    let input: SeasonInput = serde_json::from_str(input_json).map_err(|error| BoundaryError {
        code: "invalidJson",
        message: error.to_string(),
        game_number: None,
    })?;
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
    serde_json::to_string(&result).map_err(|error| BoundaryError {
        code: "serializationFailed",
        message: error.to_string(),
        game_number: None,
    })
}

#[cfg(target_arch = "wasm32")]
#[wasm_bindgen::prelude::wasm_bindgen]
pub fn simulate_season_json(input_json: &str) -> Result<String, wasm_bindgen::JsValue> {
    simulate_json(input_json).map_err(|error| {
        wasm_bindgen::JsValue::from_str(
            &serde_json::to_string(&error).expect("boundary error contains only JSON-safe values"),
        )
    })
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
}
