//! Native batch runner. Emits compact analysis rows; no Python inside simulation.
use baseball_sim::{AdvancementPolicy, Detail, SeasonInput, season_game_seed, simulate_season};
use std::{collections::BTreeMap, time::Instant};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let path = args
        .get(1)
        .ok_or("Usage: calibrate INPUTS.json REPETITIONS [baseline|contextual]")?;
    let repeats: u16 = args.get(2).ok_or("Missing repetitions")?.parse()?;
    if !(1..=1000).contains(&repeats) {
        return Err("Repetitions must be 1..1000".into());
    }
    let mut inputs: Vec<SeasonInput> = serde_json::from_slice(&std::fs::read(path)?)?;
    if inputs.is_empty() || inputs.len() > 30 {
        return Err("Provide 1..30 season inputs".into());
    }
    inputs.sort_by(|a, b| a.user_team.id.cmp(&b.user_team.id));
    let baseline = match args.get(3).map(String::as_str).unwrap_or("contextual") {
        "baseline" => true,
        "contextual" => false,
        _ => return Err("Unknown model".into()),
    };
    for input in &mut inputs {
        input.detail = Detail::Summary;
        if baseline {
            input.game_schema_version = "1.1.0".into();
            input.rules_version = baseball_sim::RULES_VERSION.into();
            input.config.advancement_policy = AdvancementPolicy::ConservativeOutsV1;
            input.config.contextual_model = None;
            for profile in &mut input.profiles {
                profile.weights.batted_ball_out = profile
                    .weights
                    .other_contact
                    .take()
                    .ok_or("Missing contact mass")?;
                profile.id = format!("baseline:{}", profile.id);
                profile.model_version = "m3-proxy-baseline-v1".into();
                profile
                    .quality_flags
                    .push("other-contact-mapped-to-m3-out-proxy".into());
            }
            for team in std::iter::once(&mut input.user_team).chain(&mut input.opponents) {
                for batter in &mut team.lineup {
                    batter.profile_id = format!("baseline:{}", batter.profile_id);
                }
            }
        }
        input.validate()?;
    }
    for repeat in 0..repeats {
        for (index, input) in inputs.iter().enumerate() {
            let mut input = input.clone();
            input.seed =
                season_game_seed(20261025, repeat * inputs.len() as u16 + index as u16).to_string();
            let start = Instant::now();
            let result = simulate_season(input)?;
            let seconds = start.elapsed().as_secs_f64();
            let mut scores = BTreeMap::<u32, u32>::new();
            let mut innings = [[0_u32; 2]; 9];
            let mut extras = 0;
            for game in &result.games {
                *scores.entry(game.score[0]).or_default() += 1;
                extras += u32::from(game.innings > 9);
                for (i, line) in game.line_score.iter().take(9).enumerate() {
                    let value = if game.user_home {
                        line.home
                    } else {
                        Some(line.away)
                    };
                    if let Some(runs) = value {
                        innings[i][0] += runs;
                        innings[i][1] += 1;
                    }
                }
            }
            println!(
                "{}",
                serde_json::json!({"repeat":repeat,"teamId":result.team.team_id,
                "engineVersion":result.engine_version,"seasonModelVersion":result.input.model_version,
                "seed":result.input.seed,"rngVersion":result.input.sampling.rng_version,
                "batchSeedBase":"20261025","batchSeedVersion":baseball_sim::SEED_DERIVATION_VERSION,
                "games":result.games.len(),"wins":result.wins,"losses":result.losses,
                "runsScored":result.runs_scored,"runsAllowed":result.runs_allowed,
                "totals":result.team.totals,"scoreHistogram":scores,"inningTotals":innings,
                "extraInningGames":extras,"seasonSeconds":seconds})
            );
        }
    }
    Ok(())
}
