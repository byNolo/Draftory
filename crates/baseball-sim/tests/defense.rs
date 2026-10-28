use baseball_sim::*;

fn fixture() -> SeasonInput {
    serde_json::from_str(include_str!(
        "../../../data/fixtures/defense-season-2024-v1.json"
    ))
    .unwrap()
}
fn neutral(mut value: SeasonInput) -> SeasonInput {
    for p in &mut std::sync::Arc::make_mut(value.config.defense.as_mut().unwrap()).assignments {
        p.error_ratio = WEIGHT_SCALE;
    }
    value
}
fn legacy(mut value: SeasonInput) -> SeasonInput {
    value.config.defense = None;
    value.schema_version = "1.0.0".into();
    value.game_schema_version = CONTEXT_INPUT_SCHEMA_VERSION.into();
    value.rules_version = CONTEXT_RULES_VERSION.into();
    value
}

#[test]
fn explicit_neutral_preserves_every_legacy_event_and_rng_draw() {
    let mut input = neutral(fixture());
    input.detail = Detail::Events;
    let a = simulate_season(input.clone()).unwrap();
    let b = simulate_season(legacy(input)).unwrap();
    assert_eq!(a.games, b.games);
    assert_eq!(a.team, b.team);
    assert_eq!(a.opponent_totals, b.opponent_totals);
    assert_eq!(a.runs_allowed, b.runs_allowed);
}

#[test]
fn modifiers_preserve_probability_mass_geometry_support_and_gdp_choices() {
    let mut input = fixture();
    let base = input.config.contextual_model.clone().unwrap();
    for ratio in [0, 500_000, 1_000_000, 1_500_000, 1_000_000_000] {
        for p in &mut std::sync::Arc::make_mut(input.config.defense.as_mut().unwrap()).assignments {
            if p.status == "observed" {
                p.error_ratio = ratio;
            }
        }
        input.validate().unwrap();
        let changed = input.config.defense.as_ref().unwrap().prepare(&base);
        changed.validate().unwrap();
        for (a, b) in base.cells.iter().zip(&changed.cells) {
            assert_eq!(a.choices.len(), b.choices.len());
            for (x, y) in a.choices.iter().zip(&b.choices) {
                assert_eq!(x.destinations, y.destinations);
                assert_eq!(x.rbi, y.rbi);
                assert_eq!(x.reach, y.reach);
                assert!(y.weight > 0);
                if a.event != ContextEvent::OtherContact
                    || (x.destinations[0] == 0 && x.destinations[1] == 0)
                {
                    assert_eq!(x.weight, y.weight);
                }
            }
            assert_eq!(
                b.choices.iter().map(|x| x.weight).sum::<u32>(),
                WEIGHT_SCALE
            );
        }
    }
}

#[test]
fn wrong_identity_position_year_source_model_and_legacy_mode_are_rejected() {
    let base = fixture();
    for mutation in 0..9 {
        let mut input = base.clone();
        let defense = std::sync::Arc::make_mut(input.config.defense.as_mut().unwrap());
        match mutation {
            0 => defense.assignments.swap(0, 1),
            1 => defense.assignments[0].year = 2023,
            2 => defense.assignments[0].player_id = "lahman:wrong01".into(),
            3 => defense.assignments[0].source_id = "wrong-source".into(),
            4 => defense.assignments[0].model_id = "wrong-model".into(),
            5 => defense.assignments[0].error_ratio = 0, // modelNeutral cannot have an effect
            6 => input.game_schema_version = "1.2.0".into(),
            7 => input
                .config
                .contextual_model
                .as_mut()
                .unwrap()
                .cells
                .clear(),
            _ => defense.model.cells[0].components.push(ErrorComponent {
                choice_index: 999,
                position: 6,
                weight: 1,
            }),
        }
        assert!(input.validate().is_err(), "mutation {mutation}");
    }
}

#[test]
fn fielding_assignment_is_independent_of_batting_order_and_has_no_dh() {
    let mut input = fixture();
    let before = input.config.defense.clone();
    input.user_team.lineup.rotate_left(3);
    input.validate().unwrap();
    assert_eq!(input.config.defense, before);
    assert_eq!(input.config.defense.as_ref().unwrap().assignments.len(), 8);
    assert!(
        !input
            .config
            .defense
            .as_ref()
            .unwrap()
            .assignments
            .iter()
            .any(|p| p.position == "DH")
    );
}

#[test]
fn missing_observations_remain_neutral_and_defensive_events_replay_exactly() {
    let mut input = neutral(fixture());
    let p = &mut std::sync::Arc::make_mut(input.config.defense.as_mut().unwrap()).assignments[1];
    p.status = "unknown".into();
    p.games = None;
    p.inn_outs = None;
    p.chances = None;
    p.errors = None;
    input.validate().unwrap();
    input.detail = Detail::Events;
    let game_input = fixture().game_input(0).unwrap();
    let mut detailed = game_input;
    detailed.detail = Detail::Events;
    let expected = simulate_game(detailed.clone()).unwrap();
    let mut replay = Game::new(detailed).unwrap();
    for record in expected.event_log.as_ref().unwrap() {
        if let Some(index) = record.transition_index {
            replay
                .apply_contextual_event(record.supplied_event, index)
                .unwrap();
        } else {
            replay.apply_event(record.supplied_event).unwrap();
        }
    }
    assert_eq!(expected, replay.result().unwrap());
}

#[test]
fn changed_outcomes_first_diverge_while_opponent_bats_on_both_home_and_away() {
    let mut season = fixture();
    season.detail = Detail::Events;
    for game_index in [0, 1] {
        let mut witnessed = false;
        for seed in 0..100 {
            let mut a = neutral(season.clone()).game_input(game_index).unwrap();
            a.seed = seed.to_string();
            let mut b = a.clone();
            for p in &mut std::sync::Arc::make_mut(b.config.defense.as_mut().unwrap()).assignments {
                if p.status == "observed" {
                    p.error_ratio = 0;
                }
            }
            let baseline = simulate_game(a).unwrap();
            let changed = simulate_game(b).unwrap();
            if let Some((x, y)) = baseline
                .event_log
                .unwrap()
                .iter()
                .zip(changed.event_log.unwrap())
                .find(|(x, y)| **x != *y)
            {
                assert_eq!(
                    x.half,
                    if game_index == 0 {
                        Half::Bottom
                    } else {
                        Half::Top
                    }
                );
                assert_eq!(x.supplied_event, y.supplied_event);
                witnessed = true;
                break;
            }
        }
        assert!(witnessed);
    }
}

#[test]
fn real_defense_repeats_and_events_match_summary_and_new_golden() {
    let input = fixture();
    let a = simulate_season(input.clone()).unwrap();
    let b = simulate_season(input.clone()).unwrap();
    assert_eq!(a, b);
    let mut detailed = input;
    detailed.detail = Detail::Events;
    let mut events = simulate_season(detailed).unwrap();
    for g in &mut events.games {
        g.event_log = None;
    }
    events.input.detail = Detail::Summary;
    assert_eq!(a, events);
    let actual = serde_json::json!({"wins":a.wins,"losses":a.losses,
        "runsScored":a.runs_scored,"runsAllowed":a.runs_allowed,
        "team":a.team.totals,"opponent":a.opponent_totals});
    let golden: serde_json::Value = serde_json::from_str(include_str!(
        "../../../data/fixtures/defense-season-2024-v1.golden.json"
    ))
    .unwrap();
    assert_eq!(actual, golden);
}
