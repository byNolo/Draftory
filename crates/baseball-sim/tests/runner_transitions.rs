use baseball_sim::*;
use serde_json::json;

fn input() -> SeasonInput {
    let mut i: SeasonInput =
        serde_json::from_str(include_str!("fixtures/season-modern-2024.json")).unwrap();
    i.schema_version = "1.2.0".into();
    i.game_schema_version = RUNNER_INPUT_VERSION.into();
    i.rules_version = RUNNER_RULES_VERSION.into();
    i.config.advancement_policy = AdvancementPolicy::RetrosheetRunnerOutsV1;
    i.config.contextual_model.as_mut().unwrap().model_version = RUNNER_MODEL_VERSION.into();
    i
}
fn choice(d: [u8; 4], kinds: [&str; 4], timing: bool, reach: Option<&str>) -> RunnerTransition {
    let mut v = json!({"weight":1000000,"destinations":d,"rbi":d.map(|x|x==4),
        "runnerPlay":{"outKinds":kinds,"outBases": std::array::from_fn::<_,4,_>(|i| if d[i]==0 { if i==0 {2} else {i+1} } else {0}),"runsBeforeOuts":timing}});
    if let Some(reach) = reach {
        v["reach"] = reach.into();
    }
    serde_json::from_value(v).unwrap()
}
fn bases(mask: u8) -> Bases {
    std::array::from_fn(|i| {
        (mask & (1 << i) != 0).then(|| Runner {
            batter_id: format!("runner{i}"),
        })
    })
}
fn resolve(
    mask: u8,
    outs: u8,
    event: PlateAppearance,
    c: &RunnerTransition,
) -> Result<BasePlay, EngineError> {
    resolve_transition(
        &bases(mask),
        outs,
        Runner {
            batter_id: "batter".into(),
        },
        event,
        c,
    )
}
fn game(outs: u8, mask: u8, event: ContextEvent, c: RunnerTransition) -> Game {
    let mut i = input().game_input(0).unwrap();
    let model = i.config.contextual_model.as_mut().unwrap();
    let cell = model
        .cells
        .iter_mut()
        .find(|x| x.event == event && x.outs == outs && x.base_mask == mask)
        .unwrap();
    cell.choices = vec![c];
    Game::new(i).unwrap()
}
#[test]
fn tag_outs_at_second_third_and_home_preserve_hit_credit_and_identities() {
    // Destination attempted is source evidence; terminal destination 0 retires that identity.
    for (mask, d) in [(0, [0, 5, 5, 5]), (1, [1, 0, 5, 5]), (2, [1, 5, 0, 5])] {
        let mut kinds = ["none"; 4];
        kinds[d.iter().position(|x| *x == 0).unwrap()] = "tag";
        let c = choice(d, kinds, false, None);
        let p = resolve(mask, 0, PlateAppearance::Single, &c).unwrap();
        assert_eq!(p.outs_on_play, 1);
        assert!(p.scorers.is_empty());
        assert_eq!(p.bases.iter().flatten().count(), mask.count_ones() as usize);
    }
    let c = choice([0, 5, 5, 5], ["tag", "none", "none", "none"], false, None);
    let mut g = game(0, 0, ContextEvent::Single, c);
    g.apply_contextual_event(PlateAppearance::Single, 0)
        .unwrap();
    let b = g.box_score(Side::Away);
    assert_eq!(b.totals.hits, 1);
    assert_eq!(b.totals.singles, 1);
    assert_eq!(b.totals.plate_appearances, 1);
    assert_eq!(b.outs_recorded, 1);
    assert_eq!(g.snapshot().next_batter, [1, 0]);
}
#[test]
fn extra_batter_base_is_distinct_from_credited_double_and_joint_movements() {
    for attempted in [3, 4] {
        let mut c = choice([2, 0, 5, 5], ["none", "tag", "none", "none"], false, None);
        c.runner_play.as_mut().unwrap().out_bases[1] = attempted;
        let p = resolve(1, 1, PlateAppearance::Double, &c).unwrap();
        assert_eq!(p.outs_on_play, 1);
        assert_eq!(p.bases[1].as_ref().unwrap().batter_id, "batter");
    }
    let c = choice([3, 4, 5, 5], ["none"; 4], false, None);
    let p = resolve(1, 0, PlateAppearance::Double, &c).unwrap();
    assert_eq!(p.bases[2].as_ref().unwrap().batter_id, "batter");
    assert_eq!(p.scorers[0].runner.batter_id, "runner0");
    let mut g = game(0, 1, ContextEvent::Double, c);
    g.apply_event(PlateAppearance::Walk { intentional: false })
        .unwrap();
    g.apply_contextual_event(PlateAppearance::Double, 0)
        .unwrap();
    let b = g.box_score(Side::Away);
    assert_eq!(
        (b.totals.doubles, b.totals.triples, b.totals.runs_batted_in),
        (1, 0, 1)
    );
    let c = choice([2, 3, 4, 4], ["none"; 4], false, None);
    let p = resolve(7, 1, PlateAppearance::Single, &c).unwrap();
    assert_eq!(
        p.scorers.iter().map(|r| r.origin_base).collect::<Vec<_>>(),
        vec![3, 2]
    );
    assert_eq!(p.bases[1].as_ref().unwrap().batter_id, "batter");
    assert_eq!(p.bases[2].as_ref().unwrap().batter_id, "runner0");
}
#[test]
fn force_third_out_suppresses_runs_but_proven_tag_timing_allows_them() {
    let forced = choice(
        [1, 0, 4, 4],
        ["none", "force", "none", "none"],
        false,
        Some("fieldersChoice"),
    );
    assert!(
        resolve(7, 2, PlateAppearance::OtherContact, &forced)
            .unwrap()
            .scorers
            .is_empty()
    );
    let tag = choice([1, 0, 3, 4], ["none", "tag", "none", "none"], true, None);
    let p = resolve(7, 2, PlateAppearance::Single, &tag).unwrap();
    assert_eq!(p.outs_on_play, 1);
    assert_eq!(p.scorers.len(), 1);
    let mut timing = game(2, 7, ContextEvent::Single, tag);
    for _ in 0..3 {
        timing
            .apply_event(PlateAppearance::Walk { intentional: false })
            .unwrap();
    }
    for _ in 0..2 {
        timing.apply_event(PlateAppearance::Strikeout).unwrap();
    }
    timing
        .apply_contextual_event(PlateAppearance::Single, 0)
        .unwrap();
    let line = timing.box_score(Side::Away);
    assert_eq!(
        (
            line.totals.runs,
            line.totals.runs_batted_in,
            line.outs_recorded,
            line.left_on_base
        ),
        (1, 1, 3, 2)
    );
    assert_eq!(line.batters[0].stats.runs, 1);
    assert_eq!(line.batters[5].stats.runs_batted_in, 1);
    let mut g = game(2, 7, ContextEvent::OtherContact, forced);
    for _ in 0..3 {
        g.apply_event(PlateAppearance::Walk { intentional: false })
            .unwrap();
    }
    for _ in 0..2 {
        g.apply_event(PlateAppearance::Strikeout).unwrap();
    }
    g.apply_contextual_event(PlateAppearance::OtherContact, 0)
        .unwrap();
    let b = g.box_score(Side::Away);
    assert_eq!(b.totals.runs, 0);
    assert_eq!(b.totals.runs_batted_in, 0);
    assert_eq!(b.left_on_base, 3);
    assert_eq!(g.snapshot().half, Half::Bottom);
}
#[test]
fn walkoff_precedes_tag_out_and_counts_only_legal_runs_rbi_and_lob() {
    let c = choice([1, 0, 3, 4], ["none", "tag", "none", "none"], true, None);
    let mut g = game(2, 7, ContextEvent::Single, c);
    for _ in 0..51 {
        g.apply_event(PlateAppearance::Strikeout).unwrap();
    }
    assert_eq!((g.snapshot().inning, g.snapshot().half), (9, Half::Bottom));
    for _ in 0..3 {
        g.apply_event(PlateAppearance::Walk { intentional: false })
            .unwrap();
    }
    for _ in 0..2 {
        g.apply_event(PlateAppearance::Strikeout).unwrap();
    }
    let before = g.snapshot().next_batter[1];
    let record = g
        .apply_contextual_event(PlateAppearance::Single, 0)
        .unwrap();
    assert_eq!(record.outs_on_play, 0);
    assert_eq!(record.state_after.next_batter[1], (before + 1) % 9);
    let result = g.result().unwrap();
    assert_eq!(result.score, [0, 1]);
    let b = &result.teams[1];
    assert_eq!(b.totals.runs_batted_in, 1);
    assert_eq!(b.totals.hits, 1);
    assert_eq!(
        b.totals.plate_appearances,
        b.outs_recorded + b.totals.runs + b.left_on_base
    );
}
#[test]
fn impossible_geometry_timing_and_incompatible_modes_are_rejected() {
    let passing = choice([1, 4, 0, 5], ["none", "none", "tag", "none"], true, None);
    assert!(resolve(3, 2, PlateAppearance::Single, &passing).is_err());
    for c in [
        choice([2, 2, 5, 5], ["none"; 4], false, None),
        choice([3, 2, 5, 5], ["none"; 4], false, None),
        choice([1, 0, 3, 4], ["none", "tag", "none", "none"], false, None),
    ] {
        assert!(resolve(7, 2, PlateAppearance::Single, &c).is_err());
    }
    let mut i = input();
    i.config.contextual_model.as_mut().unwrap().model_version =
        "retrosheet-contact-transitions-v1".into();
    assert!(i.validate().is_err());
    let mut legacy: SeasonInput =
        serde_json::from_str(include_str!("fixtures/season-modern-2024.json")).unwrap();
    legacy
        .config
        .contextual_model
        .as_mut()
        .unwrap()
        .model_version = RUNNER_MODEL_VERSION.into();
    assert!(legacy.validate().is_err());
    let mut defense: SeasonInput = serde_json::from_str(include_str!(
        "../../../data/fixtures/defense-season-2024-v1.json"
    ))
    .unwrap();
    defense
        .config
        .contextual_model
        .as_mut()
        .unwrap()
        .model_version = RUNNER_MODEL_VERSION.into();
    assert!(defense.validate().is_err());
    let mut bad = bases(1);
    bad[0].as_mut().unwrap().batter_id = "batter".into();
    assert!(
        resolve_transition(
            &bad,
            0,
            Runner {
                batter_id: "batter".into()
            },
            PlateAppearance::Single,
            &choice([2, 3, 5, 5], ["none"; 4], false, None)
        )
        .is_err()
    );
}

#[test]
fn source_model_choices_and_completed_seasons_conserve_and_replay() {
    let mut input: SeasonInput = serde_json::from_str(include_str!(
        "../../../data/fixtures/runner-season-2024-v1.json"
    ))
    .unwrap();
    let model = input.config.contextual_model.as_ref().unwrap();
    model.validate().unwrap();
    for cell in &model.cells {
        let event = match cell.event {
            ContextEvent::Single => PlateAppearance::Single,
            ContextEvent::Double => PlateAppearance::Double,
            ContextEvent::OtherContact => PlateAppearance::OtherContact,
        };
        for choice in &cell.choices {
            let p = resolve(cell.base_mask, cell.outs, event, choice).unwrap();
            assert!(cell.outs + p.outs_on_play <= 3);
            if cell.outs + p.outs_on_play < 3 {
                assert_eq!(
                    1 + cell.base_mask.count_ones() as usize,
                    p.bases.iter().flatten().count() + p.scorers.len() + p.outs_on_play as usize
                );
            }
        }
    }
    input.detail = Detail::Events;
    let result = simulate_season(input.clone()).unwrap();
    assert_eq!(result, simulate_season(input.clone()).unwrap());
    assert_eq!(result.schema_version, "1.2.0");
    let mut promoted = 0;
    for (index, game) in result.games.iter().enumerate() {
        for team in &game.teams {
            assert_eq!(
                team.totals.plate_appearances,
                team.outs_recorded + team.totals.runs + team.left_on_base
            );
            assert_eq!(
                team.totals.hits,
                team.batters.iter().map(|b| b.stats.hits).sum::<u32>()
            );
        }
        let mut replay = Game::new(input.game_input(index as u16).unwrap()).unwrap();
        for play in game.event_log.as_ref().unwrap() {
            if let Some(choice) = play.transition_index {
                let state = replay.snapshot();
                let cell = model.cell(
                    ContextEvent::from_event(play.supplied_event).unwrap(),
                    state.outs,
                    base_mask(&state.bases),
                );
                promoted += u32::from(cell.choices[choice].runner_play.is_some());
                assert_eq!(
                    replay
                        .apply_contextual_event(play.supplied_event, choice)
                        .unwrap(),
                    *play
                );
            } else {
                assert_eq!(replay.apply_event(play.supplied_event).unwrap(), *play);
            }
        }
        let repeated = replay.result().unwrap();
        let user = usize::from(game.user_home);
        assert_eq!(game.score, [repeated.score[user], repeated.score[1 - user]]);
    }
    assert!(promoted > 0);
    input.detail = Detail::Summary;
    let summary = simulate_season(input).unwrap();
    assert_eq!(summary.team, result.team);
    assert_eq!(summary.wins, result.wins);
    assert_eq!(summary.runs_scored, result.runs_scored);
    assert_eq!(
        summary.team.totals.runs,
        summary
            .team
            .batters
            .iter()
            .map(|b| b.stats.runs)
            .sum::<u32>()
    );
}
