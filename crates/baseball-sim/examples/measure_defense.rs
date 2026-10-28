//! Host-side benchmark; clocks never enter the simulation core.
use baseball_sim::{SeasonInput, simulate_season};
use std::{hint::black_box, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args()
        .nth(1)
        .ok_or("Usage: measure_defense INPUT.json")?;
    let input: SeasonInput = serde_json::from_slice(&std::fs::read(path)?)?;
    input.validate()?;
    let d = input
        .config
        .defense
        .as_ref()
        .ok_or("Defense input required")?;
    let model = input
        .config
        .contextual_model
        .as_ref()
        .ok_or("Context required")?;
    let start = Instant::now();
    for _ in 0..1000 {
        black_box(d.prepare(model));
    }
    let preparation_seconds = start.elapsed().as_secs_f64() / 1000.0;
    let mut rows = Vec::new();
    for (mode, mut value) in [
        ("legacy", input.clone()),
        ("neutral", input.clone()),
        ("real", input),
    ] {
        if mode == "legacy" {
            value.config.defense = None;
            value.schema_version = "1.0.0".into();
            value.game_schema_version = "1.2.0".into();
            value.rules_version = "contextual-nine-inning-v1".into();
        } else if mode == "neutral" {
            for p in
                &mut std::sync::Arc::make_mut(value.config.defense.as_mut().unwrap()).assignments
            {
                p.error_ratio = 1_000_000;
            }
        }
        let mut times = Vec::new();
        let mut bytes = 0;
        for i in 0..21 {
            let start = Instant::now();
            let result = black_box(simulate_season(value.clone())?);
            times.push(start.elapsed().as_secs_f64());
            if i == 0 {
                bytes = serde_json::to_vec(&result)?.len();
            }
        }
        rows.push(serde_json::json!({"mode":mode,"seconds":times,"resultBytes":bytes}));
    }
    println!(
        "{}",
        serde_json::json!({"preparationSecondsPerMatchup":preparation_seconds,"rows":rows})
    );
    Ok(())
}
