use baseball_sim::{Detail, SeasonInput, simulate_season};
use sim_wasm::{Projection, dashboard, project_measured};

const INPUT: &str = include_str!("../../../data/fixtures/dashboard-season-2024-v1.json");
fn input() -> SeasonInput {
    serde_json::from_str(INPUT).unwrap()
}

#[test]
fn expanded_schedule_is_balanced_order_independent_and_reconciles() {
    let source = input();
    let result = simulate_season(source.clone()).unwrap();
    let mut reordered = source.clone();
    reordered.opponents.reverse();
    reordered.profiles.reverse();
    assert_eq!(result.games, simulate_season(reordered).unwrap().games);
    let d = dashboard(&result);
    for row in d["opponents"].as_array().unwrap() {
        assert_eq!(row["games"], 18);
        let games: Vec<_> = result
            .games
            .iter()
            .filter(|g| g.opponent_id == row["opponentId"].as_str().unwrap())
            .collect();
        assert_eq!(games.iter().filter(|g| g.user_home).count(), 9);
        assert_eq!(
            row["wins"].as_u64().unwrap(),
            games.iter().filter(|g| g.won).count() as u64
        );
        assert_eq!(
            row["runsScored"].as_u64().unwrap(),
            games.iter().map(|g| u64::from(g.score[0])).sum::<u64>()
        );
    }
    assert_eq!(
        result.runs_scored,
        result.games.iter().map(|g| g.score[0]).sum::<u32>()
    );
    assert_eq!(
        result.runs_allowed,
        result.games.iter().map(|g| g.score[1]).sum::<u32>()
    );
    for (i, b) in result.team.batters.iter().enumerate() {
        for (k, v) in serde_json::to_value(b.stats).unwrap().as_object().unwrap() {
            let total: u64 = result
                .games
                .iter()
                .map(|g| {
                    serde_json::to_value(g.teams[0].batters[i].stats).unwrap()[k]
                        .as_u64()
                        .unwrap_or(0)
                })
                .sum();
            assert_eq!(v.as_u64().unwrap(), total, "{k}");
        }
    }
    let mut wins = 0;
    for (g, projected) in result.games.iter().zip(d["games"].as_array().unwrap()) {
        wins += u16::from(g.won);
        assert_eq!(projected["wins"], wins);
        assert_eq!(projected["losses"], g.game_number - wins);
        for side in 0..2 {
            let runs: u64 = projected["lineScore"]
                .as_array()
                .unwrap()
                .iter()
                .map(|line| line[side].as_u64().unwrap_or(0))
                .sum();
            assert_eq!(runs, u64::from(g.score[side]));
        }
        assert_eq!(g.user_home, g.game_number % 2 == 0);
        assert_eq!(g.seed, source.game_input(g.game_number - 1).unwrap().seed);
    }
}

#[test]
fn compact_dashboard_golden_preserves_counters_and_excludes_inputs_logs() {
    let result = project_measured(INPUT, Projection::Dashboard, || 0.0).unwrap();
    let expected: serde_json::Value = serde_json::from_str(include_str!(
        "../../../data/fixtures/dashboard-season-2024-v1.golden.json"
    ))
    .unwrap();
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&result.result_json).unwrap(),
        expected
    );
    assert!(result.result_json.len() < 150_000);
    assert!(expected.get("input").is_none());
    for g in expected["dashboard"]["games"].as_array().unwrap() {
        assert!(g.get("eventLog").is_none());
        assert!(g.get("profiles").is_none());
    }
    let mut source = input();
    source.detail = Detail::Events;
    let detailed = project_measured(
        &serde_json::to_string(&source).unwrap(),
        Projection::Dashboard,
        || 0.0,
    )
    .unwrap();
    assert_eq!(result.result_json, detailed.result_json);
}

#[test]
fn expanded_opponents_reject_missing_profiles_and_duplicate_rosters() {
    let mut x = input();
    x.profiles
        .retain(|p| p.id != x.opponents[8].lineup[0].profile_id);
    assert!(x.validate().is_err());
    let mut x = input();
    x.opponents[8].id = x.opponents[0].id.clone();
    assert!(x.validate().is_err());
    let mut x = input();
    x.opponents[8].lineup[1] = x.opponents[8].lineup[0].clone();
    assert!(x.validate().is_err());
}

#[test]
fn new_opponents_preserve_neutral_defense_and_repeatable_error_avoidance() {
    let legacy = simulate_season(input()).unwrap();
    let mut x: serde_json::Value = serde_json::from_str(INPUT).unwrap();
    let defense: serde_json::Value = serde_json::from_str(include_str!(
        "../../../data/fixtures/defense-season-2024-v1.json"
    ))
    .unwrap();
    x["schemaVersion"] = "1.1.0".into();
    x["gameSchemaVersion"] = "1.3.0".into();
    x["rulesVersion"] = "error-avoidance-nine-inning-v1".into();
    x["config"]["defense"] = defense["config"]["defense"].clone();
    let real: SeasonInput = serde_json::from_value(x.clone()).unwrap();
    assert_eq!(
        simulate_season(real.clone()).unwrap(),
        simulate_season(real).unwrap()
    );
    for assignment in x["config"]["defense"]["assignments"]
        .as_array_mut()
        .unwrap()
    {
        assignment["errorRatio"] = 1_000_000.into();
    }
    let neutral = simulate_season(serde_json::from_value(x).unwrap()).unwrap();
    assert_eq!(legacy.games, neutral.games);
    assert_eq!(legacy.team, neutral.team);
}
