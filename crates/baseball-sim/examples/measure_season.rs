use baseball_sim::{Detail, SeasonInput, simulate_game, simulate_season};
use std::{hint::black_box, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let path = args
        .get(1)
        .ok_or("Usage: measure_season INPUT.json [repeats=1000] [summary|events]")?;
    let repeats: u16 = args.get(2).map_or(Ok(1000), |s| s.parse())?;
    if !(1..=1000).contains(&repeats) {
        return Err("Repetitions must be 1..1000".into());
    }
    let mut input: SeasonInput = serde_json::from_slice(&std::fs::read(path)?)?;
    input.detail = match args.get(3).map(String::as_str).unwrap_or("summary") {
        "summary" => Detail::Summary,
        "events" => Detail::Events,
        _ => return Err("Invalid detail".into()),
    };
    input.validate()?;
    let game = input.game_input(0)?;
    let start = Instant::now();
    black_box(simulate_game(game)?);
    let game_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let first = simulate_season(input.clone())?;
    let season_seconds = start.elapsed().as_secs_f64();
    let result_bytes = serde_json::to_vec(&first)?.len();
    drop(first);
    let start = Instant::now();
    let mut pa = 0_u64;
    for seed in 0..repeats {
        input.seed = seed.to_string();
        pa += black_box(simulate_season(input.clone())?)
            .team
            .totals
            .plate_appearances as u64;
    }
    let batch_seconds = start.elapsed().as_secs_f64();
    println!(
        "{}",
        serde_json::json!({"engineVersion":baseball_sim::ENGINE_VERSION,"detail":input.detail,
        "gamesPerSeason":input.games,"repeats":repeats,"singleGameSeconds":game_seconds,
        "singleSeasonSeconds":season_seconds,"batchSeconds":batch_seconds,
        "meanSeasonSeconds":batch_seconds/f64::from(repeats),"userPa":pa,"resultJsonBytes":result_bytes})
    );
    Ok(())
}
