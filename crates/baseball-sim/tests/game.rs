use baseball_sim::{
    Detail, EngineError, Game, GameInput, GameStatus, Half, LimitReached, PlateAppearance as Pa,
    Side, replay_game,
};

fn input() -> GameInput {
    serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-input.synthetic.json"
    ))
    .unwrap()
}

fn outs(game: &mut Game, count: usize) {
    for _ in 0..count {
        game.apply_event(Pa::Strikeout).unwrap();
    }
}

fn bottom_ninth() -> Game {
    let mut game = Game::new(input()).unwrap();
    outs(&mut game, 51);
    assert_eq!(
        (game.snapshot().inning, game.snapshot().half),
        (9, Half::Bottom)
    );
    game
}

fn assert_conservation(game: &Game) {
    let state = game.snapshot();
    assert!(state.outs <= 3);
    if state.status == GameStatus::InProgress {
        assert!(state.outs <= 2);
    }
    let mut seen = std::collections::BTreeSet::new();
    for runner in state.bases.iter().flatten() {
        assert!(seen.insert(&runner.batter_id));
    }
    let mut total_pa = 0;
    for side in [Side::Away, Side::Home] {
        let team = game.box_score(side);
        let s = team.totals;
        total_pa += s.plate_appearances;
        assert_eq!(s.hits, s.singles + s.doubles + s.triples + s.home_runs);
        assert_eq!(s.plate_appearances, s.at_bats + s.walks + s.hit_by_pitch);
        assert!(s.intentional_walks <= s.walks);
        assert_eq!(s.at_bats, s.hits + team.outs_recorded);
        assert_eq!(s.runs, state.score[side.index()]);
        assert_eq!(s.runs_batted_in, s.runs);
        assert_eq!(
            team.batters.iter().map(|b| b.stats.runs).sum::<u32>(),
            s.runs
        );
        let active_runners = if state.half.batting_side() == side {
            state.bases.iter().flatten().count() as u32
        } else {
            0
        };
        assert_eq!(
            s.plate_appearances,
            team.outs_recorded + s.runs + team.left_on_base + active_runners
        );
        assert_eq!(
            u32::from(state.next_batter[side.index()]),
            s.plate_appearances % 9
        );
    }
    assert_eq!(total_pa, state.plate_appearances);
}

#[test]
fn third_out_clears_runners_and_batting_order_persists() {
    let mut game = Game::new(input()).unwrap();
    assert_eq!(game.current_batter().unwrap().id, "away-batter-1");
    game.apply_event(Pa::Single).unwrap();
    outs(&mut game, 3);
    assert_eq!(game.snapshot().half, Half::Bottom);
    assert!(game.snapshot().bases.iter().all(Option::is_none));
    assert_eq!(game.snapshot().outs, 0);
    assert_eq!(game.box_score(Side::Away).left_on_base, 1);
    outs(&mut game, 3);
    assert_eq!(game.snapshot().inning, 2);
    assert_eq!(game.current_batter().unwrap().id, "away-batter-5");
    assert_conservation(&game);
}

#[test]
fn forced_runs_and_grand_slam_credit_runs_rbi_and_ibb_once() {
    let mut game = Game::new(input()).unwrap();
    for event in [
        Pa::Walk { intentional: true },
        Pa::HitByPitch,
        Pa::Single,
        Pa::Walk { intentional: false },
        Pa::HomeRun,
    ] {
        game.apply_event(event).unwrap();
        assert_conservation(&game);
    }
    let team = game.box_score(Side::Away);
    assert_eq!(team.totals.plate_appearances, 5);
    assert_eq!(team.totals.at_bats, 2);
    assert_eq!(team.totals.walks, 2);
    assert_eq!(team.totals.intentional_walks, 1);
    assert_eq!(team.totals.hit_by_pitch, 1);
    assert_eq!(team.totals.runs, 5);
    assert_eq!(team.batters[0].stats.runs, 1);
    assert_eq!(team.batters[3].stats.runs_batted_in, 1);
    assert_eq!(team.batters[4].stats.runs_batted_in, 4);
}

#[test]
fn third_out_never_awards_runs_from_a_loaded_inning() {
    let mut game = Game::new(input()).unwrap();
    for _ in 0..3 {
        game.apply_event(Pa::Walk { intentional: false }).unwrap();
    }
    outs(&mut game, 2);
    game.apply_event(Pa::BattedBallOut).unwrap();
    assert_eq!(game.snapshot().score, [0, 0]);
    assert_eq!(game.box_score(Side::Away).left_on_base, 3);
    assert_conservation(&game);
}

#[test]
fn home_lead_skips_bottom_ninth_and_line_score_distinguishes_unplayed() {
    let mut game = Game::new(input()).unwrap();
    outs(&mut game, 3);
    game.apply_event(Pa::HomeRun).unwrap();
    outs(&mut game, 48);
    let result = game.result().unwrap();
    assert_eq!(result.winner, Side::Home);
    assert_eq!(result.score, [0, 1]);
    assert_eq!(result.line_score.len(), 9);
    assert_eq!(result.line_score[8].home, None);
    assert_eq!(result.line_score[7].home, Some(0));
    assert!(game.current_batter().is_none());
    assert_conservation(&game);
}

#[test]
fn away_win_requires_completed_bottom_ninth_and_no_more_events() {
    let mut game = Game::new(input()).unwrap();
    game.apply_event(Pa::HomeRun).unwrap();
    outs(&mut game, 53);
    assert_eq!(game.result(), Err(EngineError::IncompleteGame));
    outs(&mut game, 1);
    let final_state = game.snapshot().clone();
    assert_eq!(game.result().unwrap().winner, Side::Away);
    assert_eq!(
        game.apply_event(Pa::HomeRun),
        Err(EngineError::GameFinished)
    );
    assert_eq!(game.snapshot(), &final_state);
    assert_conservation(&game);
}

#[test]
fn non_hr_walkoff_truncates_runs_and_extra_base_credit() {
    let mut game = bottom_ninth();
    for _ in 0..3 {
        game.apply_event(Pa::Walk { intentional: false }).unwrap();
    }
    let record = game.apply_event(Pa::Triple).unwrap();
    assert_eq!(record.supplied_event, Pa::Triple);
    assert_eq!(record.credited_event, Pa::Single);
    assert_eq!(record.scored_batter_ids, ["home-batter-7"]);
    let result = game.result().unwrap();
    assert_eq!(result.score, [0, 1]);
    assert_eq!(result.teams[1].totals.singles, 1);
    assert_eq!(result.teams[1].totals.triples, 0);
    assert_eq!(result.teams[1].left_on_base, 3);
    assert_conservation(&game);
}

#[test]
fn walkoff_double_credit_depends_on_winning_runner_origin() {
    let mut game = bottom_ninth();
    game.apply_event(Pa::Double).unwrap();
    game.apply_event(Pa::Strikeout).unwrap();
    game.apply_event(Pa::Strikeout).unwrap();
    let record = game.apply_event(Pa::Triple).unwrap();
    assert_eq!(record.credited_event, Pa::Double);
    assert_eq!(game.result().unwrap().score, [0, 1]);
    assert_eq!(game.box_score(Side::Home).totals.doubles, 2);
    assert_conservation(&game);
}

#[test]
fn walkoff_home_run_counts_all_runners_and_rbi() {
    let mut game = bottom_ninth();
    for _ in 0..3 {
        game.apply_event(Pa::Walk { intentional: false }).unwrap();
    }
    let record = game.apply_event(Pa::HomeRun).unwrap();
    assert_eq!(record.scored_batter_ids.len(), 4);
    assert_eq!(game.result().unwrap().score, [0, 4]);
    assert_eq!(game.box_score(Side::Home).totals.runs_batted_in, 4);
    assert_conservation(&game);
}

#[test]
fn loaded_walkoff_walk_and_hbp_finish_with_one_run() {
    for last in [Pa::Walk { intentional: false }, Pa::HitByPitch] {
        let mut game = bottom_ninth();
        for _ in 0..3 {
            game.apply_event(Pa::Walk { intentional: false }).unwrap();
        }
        game.apply_event(last).unwrap();
        assert_eq!(game.result().unwrap().score, [0, 1]);
        assert_eq!(game.box_score(Side::Home).totals.hits, 0);
        assert_eq!(game.box_score(Side::Home).left_on_base, 3);
        assert_conservation(&game);
    }
}

#[test]
fn extra_innings_begin_empty_and_home_can_tie_then_walk_off() {
    let mut game = Game::new(input()).unwrap();
    outs(&mut game, 54);
    assert_eq!(
        (game.snapshot().inning, game.snapshot().half),
        (10, Half::Top)
    );
    assert_eq!(game.snapshot().next_batter, [0, 0]);
    assert!(game.snapshot().bases.iter().all(Option::is_none));
    game.apply_event(Pa::HomeRun).unwrap();
    outs(&mut game, 3);
    game.apply_event(Pa::HomeRun).unwrap();
    assert_eq!(game.snapshot().status, GameStatus::InProgress);
    game.apply_event(Pa::HomeRun).unwrap();
    assert_eq!(game.result().unwrap().score, [1, 2]);
    assert_eq!(game.result().unwrap().line_score.len(), 10);
    assert_conservation(&game);
}

#[test]
fn away_can_win_in_extra_innings() {
    let mut game = Game::new(input()).unwrap();
    outs(&mut game, 54);
    game.apply_event(Pa::HomeRun).unwrap();
    outs(&mut game, 6);
    assert_eq!(game.result().unwrap().winner, Side::Away);
    assert_conservation(&game);
}

#[test]
fn safety_limits_abort_without_assigning_a_winner() {
    let mut limited = input();
    limited.config.max_innings = 9;
    let mut game = Game::new(limited).unwrap();
    outs(&mut game, 54);
    assert_eq!(game.snapshot().status, GameStatus::Aborted);
    assert_eq!(
        game.result(),
        Err(EngineError::Aborted(LimitReached::MaxInnings))
    );
    assert_eq!(
        game.apply_event(Pa::HomeRun),
        Err(EngineError::Aborted(LimitReached::MaxInnings))
    );
    assert_conservation(&game);
    let mut limited = input();
    limited.config.max_plate_appearances = 1;
    let mut game = Game::new(limited).unwrap();
    game.apply_event(Pa::Single).unwrap();
    assert_eq!(
        game.result(),
        Err(EngineError::Aborted(LimitReached::MaxPlateAppearances))
    );
    assert_conservation(&game);
}

#[test]
fn final_play_at_exact_limit_is_a_completed_game() {
    let mut limited = input();
    limited.config.max_innings = 9;
    limited.config.max_plate_appearances = 55;
    let mut game = Game::new(limited).unwrap();
    game.apply_event(Pa::HomeRun).unwrap();
    outs(&mut game, 54);
    assert_eq!(game.result().unwrap().winner, Side::Away);
}

#[test]
fn exhausted_and_trailing_scripts_are_errors() {
    assert_eq!(
        replay_game(input(), &[]),
        Err(EngineError::ScriptExhausted {
            plate_appearances: 0
        })
    );
    let mut script = vec![Pa::HomeRun];
    script.extend([Pa::Strikeout; 54]);
    script.extend([Pa::Single; 2]);
    assert_eq!(
        replay_game(input(), &script),
        Err(EngineError::TrailingEvents { remaining: 2 })
    );
}

#[test]
fn detail_level_and_unused_seed_never_change_gameplay() {
    let events: Vec<Pa> = serde_json::from_str(include_str!(
        "../../../data/fixtures/simulation-script.synthetic.json"
    ))
    .unwrap();
    let summary = replay_game(input(), &events).unwrap();
    let mut detailed = input();
    detailed.detail = Detail::Events;
    detailed.seed = "0".into();
    let mut result = replay_game(detailed, &events).unwrap();
    assert_eq!(result.event_log.as_ref().unwrap().len(), 56);
    let log = result.event_log.take().unwrap();
    assert_eq!(log.last().unwrap().state_after, summary.final_state);
    assert_eq!(result.score, summary.score);
    assert_eq!(result.teams, summary.teams);
    assert_eq!(result.line_score, summary.line_score);
    assert!(summary.event_log.is_none());
    assert_eq!(summary, replay_game(input(), &events).unwrap());
}

#[test]
fn generated_event_sequences_conserve_every_runner_and_counter() {
    let events = [
        Pa::Walk { intentional: true },
        Pa::HitByPitch,
        Pa::Single,
        Pa::Double,
        Pa::Triple,
        Pa::HomeRun,
        Pa::Strikeout,
        Pa::BattedBallOut,
        Pa::Strikeout,
    ];
    for scenario in 0..64 {
        let mut config = input();
        config.config.max_plate_appearances = 300;
        let mut game = Game::new(config).unwrap();
        for step in 0..300 {
            if game.snapshot().status != GameStatus::InProgress {
                break;
            }
            let index = (scenario * 11 + step * step + step * 7) % events.len();
            game.apply_event(events[index]).unwrap();
            assert_conservation(&game);
        }
    }
}
