use baseball_sim::{EngineError, Game, GameInput, PlateAppearance as Pa, Side, replay_game};
use serde_json::{Value, json};

fn input_value() -> Value {
    serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-input.synthetic.json"
    ))
    .unwrap()
}

fn valid(value: Value) -> bool {
    serde_json::from_value::<GameInput>(value).is_ok_and(|input| Game::new(input).is_ok())
}

#[test]
fn shared_fixture_replays_to_golden_result_and_independent_expected_counts() {
    let input: GameInput = serde_json::from_value(input_value()).unwrap();
    let events: Vec<Pa> = serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-script.synthetic.json"
    ))
    .unwrap();
    let result = replay_game(input, &events).unwrap();
    assert_eq!(result.score, [1, 2]);
    assert_eq!(result.winner, Side::Home);
    assert_eq!(result.final_state.plate_appearances, 56);
    assert_eq!(result.teams[0].outs_recorded, 27);
    assert_eq!(result.teams[1].outs_recorded, 24);
    assert_eq!(result.teams[1].left_on_base, 2);
    assert_eq!(result.teams[1].totals.hits, 3);
    assert_eq!(result.teams[1].totals.doubles, 1);
    assert_eq!(result.teams[1].totals.walks, 1);
    assert_eq!(result.teams[1].totals.intentional_walks, 1);
    let expected: Value = serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-result.synthetic.json"
    ))
    .unwrap();
    assert_eq!(serde_json::to_value(&result).unwrap(), expected);
    let roundtrip = serde_json::from_value::<baseball_sim::GameResult>(expected).unwrap();
    assert_eq!(roundtrip, result);
}

#[test]
fn seed_is_lossless_canonical_and_bounded_u64() {
    for seed in ["0", "18446744073709551615", "9007199254740993"] {
        let mut value = input_value();
        value["seed"] = json!(seed);
        assert!(valid(value));
    }
    for seed in [
        "",
        "00",
        "01",
        "-1",
        "+1",
        "1.5",
        "1e2",
        "1\n",
        "18446744073709551616",
    ] {
        let mut value = input_value();
        value["seed"] = json!(seed);
        assert!(!valid(value), "seed accepted: {seed:?}");
    }
    let mut value = input_value();
    value["seed"] = json!(42);
    assert!(!valid(value));
}

#[test]
fn invalid_versions_configuration_and_neutral_environment_are_rejected() {
    for (pointer, replacement) in [
        ("/schemaVersion", json!("future")),
        ("/rulesVersion", json!("mlb-2026")),
        ("/config/maxInnings", json!(8)),
        ("/config/maxInnings", json!(65536)),
        ("/config/maxPlateAppearances", json!(0)),
        ("/config/maxPlateAppearances", json!(1000001)),
        ("/config/advancementPolicy", json!("random")),
        ("/pitchingEnvironment/mode", json!("realPitcher")),
        ("/pitchingEnvironment/contextId", json!("invalid id")),
        ("/detail", json!("anything")),
    ] {
        let mut value = input_value();
        *value.pointer_mut(pointer).unwrap() = replacement;
        assert!(!valid(value), "invalid value accepted at {pointer}");
    }
}

#[test]
fn lineup_shape_identity_and_profile_references_are_validated() {
    let mut value = input_value();
    value["teams"]["away"]["lineup"]
        .as_array_mut()
        .unwrap()
        .pop();
    assert!(!valid(value));
    for (pointer, replacement) in [
        ("/teams/home/id", json!("away")),
        ("/teams/home/lineup/0/id", json!("away-batter-1")),
        ("/teams/away/lineup/1/id", json!("away-batter-1")),
        ("/teams/away/lineup/0/id", json!("")),
        ("/teams/away/lineup/0/id", json!("valid\n")),
        ("/teams/away/lineup/0/profileId", json!("missing-profile")),
    ] {
        let mut value = input_value();
        *value.pointer_mut(pointer).unwrap() = replacement;
        assert!(!valid(value));
    }
    let mut value = input_value();
    let duplicate = value["profiles"][0].clone();
    value["profiles"].as_array_mut().unwrap().push(duplicate);
    assert!(!valid(value));
}

#[test]
fn prepared_weights_and_sample_metadata_are_validated_without_imputation() {
    for replacement in [json!(0), json!(null), json!(-1)] {
        let mut value = input_value();
        value["profiles"][0]["sampleOpportunities"] = replacement;
        assert!(!valid(value));
    }
    for replacement in [json!(0), json!(null), json!(-1), json!(4294967295_u32)] {
        let mut value = input_value();
        value["profiles"][0]["weights"]["single"] = replacement;
        assert!(!valid(value));
    }
    let mut value = input_value();
    value["profiles"][0]["weights"]
        .as_object_mut()
        .unwrap()
        .remove("battedBallOut");
    value["profiles"][0]["weights"]["otherAtBat"] = json!(125000);
    assert!(!valid(value));
    let mut value = input_value();
    value["profiles"] = json!([]);
    assert!(!valid(value));
}

#[test]
fn unsupported_events_and_unknown_fields_are_rejected() {
    for value in [
        json!({"kind":"sacrificeFly"}),
        json!({"kind":"otherAtBat"}),
        json!({"kind":"walk"}),
        json!({"kind":"walk","intentional":null}),
        json!({"kind":"single","advanceSecond":true}),
    ] {
        assert!(serde_json::from_value::<Pa>(value).is_err());
    }
    let mut value = input_value();
    value["ignoreMe"] = json!(true);
    assert!(!valid(value));
    let historical: Value = serde_json::from_str(include_str!(
        "../../../data/fixtures/batting-profile.synthetic.json"
    ))
    .unwrap();
    assert!(serde_json::from_value::<GameInput>(historical).is_err());
}

#[test]
fn invalid_input_never_constructs_an_engine() {
    let mut input: GameInput = serde_json::from_value(input_value()).unwrap();
    input.profiles[0].weights.single = 0;
    assert!(matches!(
        Game::new(input),
        Err(EngineError::InvalidInput(_))
    ));
}
