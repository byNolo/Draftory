use baseball_sim::{
    Detail, EngineError, GameInput, GameStatus, LimitReached, PlateAppearance, replay_game,
    simulate_game,
};

fn input() -> GameInput {
    serde_json::from_str(include_str!("fixtures/lahman-modern-game.json")).unwrap()
}

#[test]
fn real_profiles_reproduce_complete_games_and_scripted_events() {
    let input = input();
    let result = simulate_game(input.clone()).unwrap();
    assert_eq!(result.score, [3, 13]);
    assert_eq!(result.final_state.plate_appearances, 90);
    assert_eq!(result, simulate_game(input.clone()).unwrap());
    assert_eq!(result.final_state.status, GameStatus::Final);
    let events: Vec<_> = result
        .event_log
        .as_ref()
        .unwrap()
        .iter()
        .map(|play| play.supplied_event)
        .collect();
    assert_eq!(
        &events[..8],
        &[
            PlateAppearance::Single,
            PlateAppearance::BattedBallOut,
            PlateAppearance::Single,
            PlateAppearance::Strikeout,
            PlateAppearance::BattedBallOut,
            PlateAppearance::BattedBallOut,
            PlateAppearance::Strikeout,
            PlateAppearance::Strikeout
        ]
    );
    assert_eq!(replay_game(input.clone(), &events).unwrap(), result);
    let mut other = input.clone();
    other.seed = "2026".into();
    assert_ne!(simulate_game(other).unwrap().event_log, result.event_log);
    let mut summary = input;
    summary.detail = Detail::Summary;
    let summary = simulate_game(summary).unwrap();
    assert!(summary.event_log.is_none());
    assert_eq!(summary.score, result.score);
    assert_eq!(summary.teams, result.teams);
    assert_eq!(summary.final_state, result.final_state);
}

#[test]
fn real_profiles_conserve_box_scores_across_one_hundred_seeds() {
    for seed in 0..100 {
        let mut input = input();
        input.seed = seed.to_string();
        let result = simulate_game(input).unwrap();
        let mut total_pa = 0;
        for (side, team) in result.teams.iter().enumerate() {
            let s = team.totals;
            assert_eq!(s.hits, s.singles + s.doubles + s.triples + s.home_runs);
            assert_eq!(s.plate_appearances, s.at_bats + s.walks + s.hit_by_pitch);
            assert_eq!(s.at_bats, s.hits + team.outs_recorded);
            assert_eq!(
                s.plate_appearances,
                team.outs_recorded + s.runs + team.left_on_base
            );
            assert_eq!(s.runs, result.score[side]);
            assert_eq!(s.runs_batted_in, s.runs);
            assert_eq!(
                team.batters
                    .iter()
                    .map(|b| b.stats.plate_appearances)
                    .sum::<u32>(),
                s.plate_appearances
            );
            total_pa += s.plate_appearances;
        }
        let log = result.event_log.as_ref().unwrap();
        assert_eq!(total_pa, result.final_state.plate_appearances);
        assert_eq!(log.len(), total_pa as usize);
        assert!(
            log.iter()
                .all(|p| p.supplied_event != PlateAppearance::Walk { intentional: true })
        );
    }
}

#[test]
fn sampled_contract_rejects_unsupported_or_inconsistent_metadata() {
    let base = serde_json::to_value(input()).unwrap();
    for (pointer, replacement) in [
        ("/sampling/rngVersion", serde_json::json!("future")),
        ("/sampling", serde_json::Value::Null),
        ("/profiles/0/provenance", serde_json::Value::Null),
        (
            "/profiles/0/provenance/contextId",
            serde_json::json!("different-context"),
        ),
        ("/profiles/0/provenance/playerId", serde_json::json!("")),
        (
            "/pitchingEnvironment/mode",
            serde_json::json!("scriptedNeutral"),
        ),
        ("/schemaVersion", serde_json::json!("1.0.0")),
    ] {
        let mut value = base.clone();
        *value.pointer_mut(pointer).unwrap() = replacement;
        assert!(
            serde_json::from_value::<GameInput>(value)
                .map_or(true, |input| input.validate().is_err()),
            "accepted {pointer}"
        );
    }
}

#[test]
fn safety_abort_is_not_reported_as_a_completed_sampled_game() {
    let mut input = input();
    input.config.max_plate_appearances = 1;
    assert!(matches!(
        simulate_game(input),
        Err(EngineError::Aborted(LimitReached::MaxPlateAppearances))
    ));
    let scripted: GameInput = serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-input.synthetic.json"
    ))
    .unwrap();
    assert!(matches!(
        simulate_game(scripted),
        Err(EngineError::InvalidInput(_))
    ));
}
