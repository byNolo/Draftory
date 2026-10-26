use baseball_sim::{
    Detail, EngineError, Game, GameStatus, LimitReached, PlateAppearance as Pa, SeasonError,
    SeasonInput, Side, season_game_seed, simulate_game, simulate_season,
};

fn input() -> SeasonInput {
    serde_json::from_str(include_str!("fixtures/season-modern-2024.json")).unwrap()
}

#[test]
fn indexed_game_seeds_are_frozen_and_unique() {
    assert_eq!(season_game_seed(0, 0), 0xe220a8397b1dcdaf);
    assert_eq!(season_game_seed(0, 1), 0x6e789e6aa1b965f4);
    assert_eq!(season_game_seed(0, 2), 0x06c45d188009454f);
    let seeds: std::collections::BTreeSet<_> =
        (0..1000).map(|i| season_game_seed(u64::MAX, i)).collect();
    assert_eq!(seeds.len(), 1000);
}

#[test]
fn season_is_reproducible_and_every_game_reconciles_with_totals() {
    let mut input = input();
    input.games = 12;
    let result = simulate_season(input.clone()).unwrap();
    assert_eq!(result, simulate_season(input.clone()).unwrap());
    assert_eq!(result.wins + result.losses, 12);
    assert_eq!(result.games.len(), 12);
    assert_eq!(
        result.runs_scored,
        result.games.iter().map(|g| g.score[0]).sum::<u32>()
    );
    assert_eq!(
        result.runs_allowed,
        result.games.iter().map(|g| g.score[1]).sum::<u32>()
    );
    assert_eq!(result.team.totals.runs, result.runs_scored);
    assert_eq!(result.opponent_totals.runs, result.runs_allowed);
    for (i, game) in result.games.iter().enumerate() {
        let single = simulate_game(input.game_input(i as u16).unwrap()).unwrap();
        let user = usize::from(game.user_home);
        assert_eq!(game.score, [single.score[user], single.score[1 - user]]);
        assert_eq!(game.teams[0], single.teams[user]);
        assert_eq!(game.seed, single.input.seed);
    }
    for (i, batter) in result.team.batters.iter().enumerate() {
        let games: Vec<_> = result
            .games
            .iter()
            .map(|g| serde_json::to_value(g.teams[0].batters[i].stats).unwrap())
            .collect();
        for (field, value) in serde_json::to_value(batter.stats)
            .unwrap()
            .as_object()
            .unwrap()
        {
            assert_eq!(
                value.as_u64().unwrap(),
                games
                    .iter()
                    .map(|g| g[field].as_u64().unwrap_or(0))
                    .sum::<u64>()
            );
        }
    }
    let s = result.team.totals;
    assert_eq!(s.at_bats, s.plate_appearances - s.walks - s.hit_by_pitch);
    assert_eq!(
        s.plate_appearances,
        result.team.outs_recorded + s.runs + result.team.left_on_base
    );
    input.seed = "42".into();
    assert_ne!(result.games, simulate_season(input).unwrap().games);
}

#[test]
fn defaults_full_length_detail_and_input_ordering_are_stable() {
    let mut value = serde_json::to_value(input()).unwrap();
    value.as_object_mut().unwrap().remove("games");
    let full: SeasonInput = serde_json::from_value(value).unwrap();
    let result = simulate_season(full).unwrap();
    assert_eq!(result.games.len(), 162);
    let golden: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/season-modern-2024.golden.json")).unwrap();
    let observed = serde_json::json!({"wins":result.wins,"losses":result.losses,
        "runsScored":result.runs_scored,"runsAllowed":result.runs_allowed,"runDifferential":result.run_differential,
        "firstFiveScores":result.games.iter().take(5).map(|g|g.score).collect::<Vec<_>>(),"teamTotals":result.team.totals});
    assert_eq!(observed, golden);
    let mut input = input();
    input.games = 4;
    let mut extra = input.opponents[0].clone();
    extra.id = "extra-team".into();
    for (i, b) in extra.lineup.iter_mut().enumerate() {
        b.id = format!("extra-batter-{i}");
    }
    input.opponents.push(extra);
    let a = simulate_season(input.clone()).unwrap();
    input.opponents.reverse();
    input.profiles.reverse();
    let b = simulate_season(input.clone()).unwrap();
    assert_eq!(a.games, b.games);
    input.detail = Detail::Events;
    let detailed = simulate_season(input).unwrap();
    assert_eq!(detailed.team, a.team);
    assert_eq!(detailed.wins, a.wins);
    for (summary, events) in a.games.iter().zip(&detailed.games) {
        assert_eq!(summary.score, events.score);
        assert_eq!(summary.teams, events.teams);
        assert!(summary.event_log.is_none());
        assert_eq!(
            events.event_log.as_ref().unwrap().len(),
            events.plate_appearances as usize
        );
    }
}

#[test]
fn aborts_and_unreached_invalid_opponents_are_never_silently_omitted() {
    let mut duplicate = self::input();
    duplicate.opponents[0].lineup[0].profile_id = duplicate.user_team.lineup[0].profile_id.clone();
    assert!(
        duplicate
            .validate()
            .unwrap_err()
            .to_string()
            .contains("Duplicate player identity")
    );
    duplicate.user_lineup_kind = baseball_sim::LineupSourceKind::Synthetic;
    duplicate.opponent_set_kind = baseball_sim::LineupSourceKind::Synthetic;
    assert!(duplicate.validate().is_ok());
    let mut input = input();
    input.config.max_plate_appearances = 1;
    assert!(matches!(
        simulate_season(input),
        Err(SeasonError::GameFailed {
            game_number: 1,
            source: EngineError::Aborted(LimitReached::MaxPlateAppearances)
        })
    ));
    let mut input = self::input();
    input.games = 1;
    let mut extra = input.opponents[0].clone();
    extra.id = "unreached".into();
    extra.lineup[0].profile_id = "missing".into();
    input.opponents.push(extra);
    assert!(input.validate().is_err());
    for bad in ["01", "+1", "-1", "18446744073709551616", ""] {
        let mut input = self::input();
        input.seed = bad.into();
        assert!(input.validate().is_err());
    }
}

#[test]
fn contextual_games_replay_recorded_choices_and_preserve_conservation() {
    for seed in 0..16 {
        let mut input = input();
        input.detail = Detail::Events;
        let mut game_input = input.game_input(0).unwrap();
        game_input.seed = seed.to_string();
        let result = simulate_game(game_input.clone()).unwrap();
        let mut replay = Game::new(game_input).unwrap();
        for record in result.event_log.as_ref().unwrap() {
            let play = if let Some(index) = record.transition_index {
                replay
                    .apply_contextual_event(record.supplied_event, index)
                    .unwrap()
            } else {
                replay.apply_event(record.supplied_event).unwrap()
            };
            assert_eq!(&play, record);
            let state = replay.snapshot();
            for side in [Side::Away, Side::Home] {
                let team = replay.box_score(side);
                let s = team.totals;
                let occupied = if side == state.half.batting_side() {
                    state.bases.iter().flatten().count() as u32
                } else {
                    0
                };
                assert_eq!(
                    s.plate_appearances,
                    team.outs_recorded + s.runs + team.left_on_base + occupied
                );
                assert_eq!(s.at_bats, s.plate_appearances - s.walks - s.hit_by_pitch);
                assert!(s.runs_batted_in <= s.runs);
            }
        }
        assert_eq!(replay.snapshot().status, GameStatus::Final);
        assert_eq!(replay.result().unwrap(), result);
    }
}

#[test]
fn double_play_ends_inning_without_a_force_play_run_or_rbi() {
    let input = input().game_input(0).unwrap();
    let model = input.config.contextual_model.as_ref().unwrap();
    let cell = model.cell(baseball_sim::ContextEvent::OtherContact, 1, 7);
    let choice = cell
        .choices
        .iter()
        .position(|t| t.destinations[1] == 0)
        .unwrap();
    let mut game = Game::new(input).unwrap();
    for _ in 0..3 {
        game.apply_event(Pa::Walk { intentional: false }).unwrap();
    }
    game.apply_event(Pa::Strikeout).unwrap();
    let play = game
        .apply_contextual_event(Pa::OtherContact, choice)
        .unwrap();
    assert_eq!(play.outs_on_play, 2);
    assert!(play.scored_batter_ids.is_empty());
    assert_eq!(game.snapshot().score, [0, 0]);
    assert_eq!(game.box_score(Side::Away).left_on_base, 2);
    assert_eq!(
        game.box_score(Side::Away).totals.grounded_into_double_plays,
        1
    );
}

#[test]
fn all_transition_choices_conserve_runners_and_reject_illegal_maps() {
    let input = input();
    let model = input.config.contextual_model.as_ref().unwrap();
    for cell in &model.cells {
        let event = match cell.event {
            baseball_sim::ContextEvent::Single => Pa::Single,
            baseball_sim::ContextEvent::Double => Pa::Double,
            _ => Pa::OtherContact,
        };
        let bases = std::array::from_fn(|i| {
            (cell.base_mask & (1 << i) != 0).then(|| baseball_sim::Runner {
                batter_id: format!("runner-{i}"),
            })
        });
        for choice in &cell.choices {
            let play = baseball_sim::resolve_transition(
                &bases,
                cell.outs,
                baseball_sim::Runner {
                    batter_id: "batter".into(),
                },
                event,
                choice,
            )
            .unwrap();
            assert_eq!(
                bases.iter().flatten().count() + 1,
                play.bases.iter().flatten().count()
                    + play.scorers.len()
                    + usize::from(play.outs_on_play)
            );
        }
    }
    for change in [0, 1, 2] {
        let mut bad = model.clone();
        if change == 0 {
            bad.cells[0].choices[0].weight = 0;
        }
        if change == 1 {
            bad.cells[0].choices[0].destinations[0] = 5;
        }
        if change == 2 {
            bad.cells.swap(0, 1);
        }
        assert!(bad.validate().is_err());
    }
}

#[test]
fn errors_and_force_choices_preserve_batter_and_runner_identity() {
    let input = input().game_input(0).unwrap();
    let model = input.config.contextual_model.as_ref().unwrap();
    let error = model
        .cell(baseball_sim::ContextEvent::OtherContact, 0, 0)
        .choices
        .iter()
        .position(|t| t.reach == Some(baseball_sim::ContactReach::Error) && t.destinations[0] == 1)
        .unwrap();
    let choice = model
        .cell(baseball_sim::ContextEvent::OtherContact, 0, 1)
        .choices
        .iter()
        .position(|t| {
            t.reach == Some(baseball_sim::ContactReach::FieldersChoice) && t.destinations[1] == 0
        })
        .unwrap();
    let mut game = Game::new(input).unwrap();
    let first = game.current_batter().unwrap().id.clone();
    game.apply_contextual_event(Pa::OtherContact, error)
        .unwrap();
    assert_eq!(game.snapshot().outs, 0);
    assert_eq!(game.snapshot().bases[0].as_ref().unwrap().batter_id, first);
    let second = game.current_batter().unwrap().id.clone();
    game.apply_contextual_event(Pa::OtherContact, choice)
        .unwrap();
    assert_eq!(game.snapshot().outs, 1);
    assert_eq!(game.snapshot().bases[0].as_ref().unwrap().batter_id, second);
    let s = game.box_score(Side::Away).totals;
    assert_eq!(
        (
            s.plate_appearances,
            s.at_bats,
            s.hits,
            s.reached_on_error,
            s.fielders_choices
        ),
        (2, 2, 0, 1, 1)
    );
}

#[test]
fn contextual_walkoff_outs_are_not_counted_as_stranded_runners() {
    for reach in [None, Some(baseball_sim::ContactReach::FieldersChoice)] {
        let input = input().game_input(0).unwrap();
        let choice = input
            .config
            .contextual_model
            .as_ref()
            .unwrap()
            .cell(baseball_sim::ContextEvent::OtherContact, 0, 7)
            .choices
            .iter()
            .position(|t| t.reach == reach && t.destinations.contains(&0) && t.destinations[3] == 4)
            .unwrap();
        let mut game = Game::new(input).unwrap();
        for _ in 0..51 {
            game.apply_event(Pa::Strikeout).unwrap();
        }
        for _ in 0..3 {
            game.apply_event(Pa::Walk { intentional: false }).unwrap();
        }
        let play = game
            .apply_contextual_event(Pa::OtherContact, choice)
            .unwrap();
        assert_eq!(play.outs_on_play, 1);
        assert_eq!(game.snapshot().score, [0, 1]);
        assert_eq!(game.snapshot().status, GameStatus::Final);
        let team = game.box_score(Side::Home);
        assert_eq!(team.left_on_base, 2);
        assert_eq!(
            team.totals.plate_appearances,
            team.outs_recorded + team.totals.runs + team.left_on_base
        );
    }
}

#[test]
fn contextual_walkoff_truncates_runner_and_rbi_credit_at_winning_run() {
    let input = input().game_input(0).unwrap();
    let choice = input
        .config
        .contextual_model
        .as_ref()
        .unwrap()
        .cell(baseball_sim::ContextEvent::Single, 0, 7)
        .choices
        .iter()
        .position(|t| t.destinations[3] == 4 && t.rbi[3])
        .unwrap();
    let mut game = Game::new(input).unwrap();
    for _ in 0..51 {
        game.apply_event(Pa::Strikeout).unwrap();
    }
    for _ in 0..3 {
        game.apply_event(Pa::Walk { intentional: false }).unwrap();
    }
    let play = game.apply_contextual_event(Pa::Single, choice).unwrap();
    assert_eq!(play.scored_batter_ids.len(), 1);
    assert_eq!(game.snapshot().score, [0, 1]);
    assert_eq!(game.snapshot().status, GameStatus::Final);
    let team = game.box_score(Side::Home);
    assert_eq!(
        (
            team.totals.runs,
            team.totals.runs_batted_in,
            team.left_on_base
        ),
        (1, 1, 3)
    );
}
