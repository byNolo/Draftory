//! M9A observation only: unchanged engine, compact game rows and optional PA traces.
use baseball_sim::{Detail, Half, PlateAppearance, SeasonInput, season_game_seed, simulate_season};
use std::collections::BTreeMap;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let inputs: Vec<SeasonInput> = serde_json::from_slice(&std::fs::read(
        args.get(1)
            .ok_or("Usage: audit_accuracy INPUTS REPEATS TRACE_REPEATS BASE_SEED")?,
    )?)?;
    let repeats: u16 = args.get(2).ok_or("Missing repeats")?.parse()?;
    let trace_repeats: u16 = args.get(3).ok_or("Missing trace repeats")?.parse()?;
    let base: u64 = args.get(4).ok_or("Missing base seed")?.parse()?;
    if inputs.is_empty()
        || inputs.len() > 30
        || !(1..=1000).contains(&repeats)
        || trace_repeats > repeats
    {
        return Err("Invalid audit bounds".into());
    }
    for (index, template) in inputs.iter().enumerate() {
        for repeat in 0..repeats {
            let mut input = template.clone();
            // Each roster uses a disjoint set of season-root seed indices.
            input.seed =
                season_game_seed(base, repeat * inputs.len() as u16 + index as u16).to_string();
            input.detail = if repeat < trace_repeats {
                Detail::Events
            } else {
                Detail::Summary
            };
            let result = simulate_season(input)?;
            let mut cells = [[0_u64; 24]; 3]; // PA, residual contact, GDP (innings 1..8).
            let mut expected_gdp = 0_f64;
            let mut inning_pa = BTreeMap::<u32, u32>::new();
            let mut games = Vec::new();
            // M9B.1 optional trace observations; existing M9A artifacts stay intact.
            let mut runner_metrics = [0_u64; 3]; // tag outs, extra batter bases, runner advance bases
            for game in &result.games {
                games.push(serde_json::json!({"won":game.won,"score":game.score,
                    "innings":game.innings,"opponent":game.opponent_id,"home":game.user_home,
                    "totals":game.teams[0].totals,"outs":game.teams[0].outs_recorded,
                    "lob":game.teams[0].left_on_base,"lines":game.line_score}));
                if let Some(log) = &game.event_log {
                    let (mut outs, mut mask) = (0_usize, 0_usize);
                    let mut half_pa = BTreeMap::<u16, u32>::new();
                    for play in log {
                        let user = (play.half == Half::Bottom) == game.user_home;
                        if user && play.inning <= 8 {
                            *half_pa.entry(play.inning).or_default() += 1;
                            cells[0][outs * 8 + mask] += 1;
                            if let Some(kind) =
                                baseball_sim::ContextEvent::from_event(play.supplied_event)
                            {
                                let model = result
                                    .input
                                    .config
                                    .contextual_model
                                    .as_ref()
                                    .ok_or("Missing model")?;
                                let c = model.cell(kind, outs as u8, mask as u8);
                                let t =
                                    &c.choices[play.transition_index.ok_or("Missing choice")?];
                                if play.outs_on_play > 0 {
                                    runner_metrics[0] += t.runner_play.map_or(0, |p| {
                                        p.out_kinds
                                            .iter()
                                            .filter(|&&k| k == baseball_sim::RunnerOutKind::Tag)
                                            .count() as u64
                                    });
                                }
                                // Terminal/walk-off destination bases are not credited as realized advances.
                                if play.state_after.status == baseball_sim::GameStatus::InProgress
                                    && play.state_after.inning == play.inning
                                    && play.state_after.half == play.half
                                {
                                    if let Some(hit) = play.supplied_event.hit_bases() {
                                        if (hit..=4).contains(&t.destinations[0]) {
                                            runner_metrics[1] += u64::from(t.destinations[0] - hit);
                                        }
                                    }
                                    for (i, &d) in t.destinations.iter().enumerate().skip(1) {
                                        if (i as u8..=4).contains(&d) {
                                            runner_metrics[2] += u64::from(d - i as u8);
                                        }
                                    }
                                }
                            }
                            if play.supplied_event == PlateAppearance::OtherContact {
                                cells[1][outs * 8 + mask] += 1;
                                cells[2][outs * 8 + mask] += u64::from(play.outs_on_play == 2);
                                let model = result
                                    .input
                                    .config
                                    .contextual_model
                                    .as_ref()
                                    .ok_or("Missing model")?;
                                let cell = model
                                    .cells
                                    .iter()
                                    .find(|c| {
                                        c.event == baseball_sim::ContextEvent::OtherContact
                                            && usize::from(c.outs) == outs
                                            && usize::from(c.base_mask) == mask
                                    })
                                    .ok_or("Missing cell")?;
                                if outs < 2 && mask & 1 != 0 {
                                    expected_gdp += cell
                                        .choices
                                        .iter()
                                        .filter(|c| {
                                            c.destinations[0] == 0 && c.destinations[1] == 0
                                        })
                                        .map(|c| f64::from(c.weight) / 1_000_000.0)
                                        .sum::<f64>();
                                }
                            }
                        }
                        outs = usize::from(play.state_after.outs);
                        mask = play
                            .state_after
                            .bases
                            .iter()
                            .enumerate()
                            .filter(|(_, b)| b.is_some())
                            .map(|(i, _)| 1 << i)
                            .sum();
                    }
                    for n in half_pa.values() {
                        *inning_pa.entry(*n).or_default() += 1;
                    }
                }
            }
            let expected: BTreeMap<_, _> = [
                "single",
                "double",
                "triple",
                "homeRun",
                "walk",
                "hitByPitch",
                "strikeout",
                "otherContact",
            ]
            .into_iter()
            .map(|event| {
                let n: f64 = result
                    .team
                    .batters
                    .iter()
                    .map(|b| {
                        let batter = result
                            .input
                            .user_team
                            .lineup
                            .iter()
                            .find(|p| p.id == b.batter_id)
                            .unwrap();
                        let profile = result
                            .input
                            .profiles
                            .iter()
                            .find(|p| p.id == batter.profile_id)
                            .unwrap();
                        let w = serde_json::to_value(&profile.weights).unwrap();
                        f64::from(b.stats.plate_appearances) * w[event].as_u64().unwrap_or(0) as f64
                            / 1_000_000.0
                    })
                    .sum();
                (event, n)
            })
            .collect();
            println!(
                "{}",
                serde_json::json!({"team":result.team.team_id,"repeat":repeat,
                "seed":result.input.seed,"engine":result.engine_version,"wins":result.wins,
                "rs":result.runs_scored,"ra":result.runs_allowed,"totals":result.team.totals,
                "games":games,"traceCells":cells,"expectedGDP":expected_gdp,
                "inningPA":inning_pa,"expectedOutcomes":expected,"runnerMetrics":runner_metrics})
            );
        }
    }
    Ok(())
}
