//! Native-only measurement harness. Parsing and file I/O are outside timed loops.
use baseball_sim::{
    Detail, GameInput, OUTCOME_NAMES, OutcomeDistribution, SplitMix64, simulate_game,
};
use std::{hint::black_box, time::Instant};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let path = args
        .get(1)
        .ok_or("Usage: measure INPUT.json [draws=1000000] [games=5000]")?;
    let draws: u32 = args.get(2).map_or(Ok(1_000_000), |s| s.parse())?;
    let games: u32 = args.get(3).map_or(Ok(5000), |s| s.parse())?;
    if draws == 0 || games == 0 {
        return Err("Counts must be positive".into());
    }
    let mut input: GameInput = serde_json::from_slice(&std::fs::read(path)?)?;
    input.validate()?;
    input.detail = Detail::Summary;
    let distribution = OutcomeDistribution::new(&input.profiles[0].weights)?;
    let mut rng = SplitMix64::new(input.seed.parse()?);
    let mut observed = [0_u32; 9];
    let start = Instant::now();
    for _ in 0..draws {
        observed[black_box(distribution.sample_index(&mut rng))] += 1;
    }
    let sampling_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let first = black_box(simulate_game(input.clone())?);
    let single_game_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let mut appearances = 0_u64;
    for seed in 0..games {
        input.seed = seed.to_string();
        let result = black_box(simulate_game(input.clone())?);
        appearances += u64::from(result.final_state.plate_appearances);
    }
    let game_seconds = start.elapsed().as_secs_f64();
    let weights = serde_json::to_value(&input.profiles[0].weights)?;
    let frequencies: Vec<_> = OUTCOME_NAMES
        .iter()
        .enumerate()
        .map(|(i, name)| {
            serde_json::json!({"outcome":name, "weight":weights.get(name).unwrap_or(&serde_json::json!(0)), "observed":observed[i],
            "observedProbability":f64::from(observed[i])/f64::from(draws)})
        })
        .collect();
    println!(
        "{}",
        serde_json::json!({
            "engineVersion":baseball_sim::ENGINE_VERSION, "rngVersion":baseball_sim::RNG_VERSION,
            "seed":first.input.seed, "profileId":first.input.profiles[0].id,
            "draws":draws, "samplingSeconds":sampling_seconds,
            "sampledPaPerSecond":f64::from(draws)/sampling_seconds,
            "frequencies":frequencies, "singleGameSeconds":single_game_seconds,
            "singleGameScore":first.score, "singleGamePa":first.final_state.plate_appearances,
            "games":games, "gameSeconds":game_seconds, "totalGamePa":appearances,
            "gamesPerSecond":f64::from(games)/game_seconds,
            "gamePaPerSecond":appearances as f64/game_seconds
        })
    );
    Ok(())
}
