use crate::{AdvancementPolicy, Bases, PlateAppearance as Pa, Runner, resolve_bases};

fn runner(id: &str) -> Runner {
    Runner {
        batter_id: id.into(),
    }
}

fn loaded() -> Bases {
    [
        Some(runner("first")),
        Some(runner("second")),
        Some(runner("third")),
    ]
}

fn resolve(bases: &Bases, outs: u8, event: Pa) -> crate::BasePlay {
    resolve_bases(
        bases,
        outs,
        runner("batter"),
        event,
        AdvancementPolicy::ConservativeOutsV1,
    )
    .unwrap()
}

fn ids(bases: &Bases) -> Vec<Option<&str>> {
    bases
        .iter()
        .map(|r| r.as_ref().map(|r| r.batter_id.as_str()))
        .collect()
}

#[test]
fn all_eight_force_states_for_walk_and_hbp() {
    let expected = [
        [Some("batter"), None, None],
        [Some("batter"), Some("first"), None],
        [Some("batter"), Some("second"), None],
        [Some("batter"), Some("first"), Some("second")],
        [Some("batter"), None, Some("third")],
        [Some("batter"), Some("first"), Some("third")],
        [Some("batter"), Some("second"), Some("third")],
        [Some("batter"), Some("first"), Some("second")],
    ];
    for (mask, expected_bases) in expected.iter().enumerate() {
        let bases = std::array::from_fn(|i| {
            (mask & (1 << i) != 0)
                .then(|| loaded()[i].clone())
                .flatten()
        });
        for event in [
            Pa::Walk { intentional: false },
            Pa::Walk { intentional: true },
            Pa::HitByPitch,
        ] {
            let play = resolve(&bases, 0, event);
            assert_eq!(ids(&play.bases), *expected_bases);
            assert_eq!(play.scorers.len(), usize::from(mask == 7));
            if mask == 7 {
                assert_eq!(play.scorers[0].runner.batter_id, "third");
            }
        }
    }
}

#[test]
fn single_and_double_use_outs_context_not_uniform_base_shifts() {
    let single = resolve(&loaded(), 0, Pa::Single);
    assert_eq!(
        ids(&single.bases),
        [Some("batter"), Some("first"), Some("second")]
    );
    assert_eq!(single.scorers.len(), 1);
    let two_out_single = resolve(&loaded(), 2, Pa::Single);
    assert_eq!(
        ids(&two_out_single.bases),
        [Some("batter"), Some("first"), None]
    );
    assert_eq!(two_out_single.scorers.len(), 2);
    let double = resolve(&loaded(), 1, Pa::Double);
    assert_eq!(ids(&double.bases), [None, Some("batter"), Some("first")]);
    assert_eq!(double.scorers.len(), 2);
    let two_out_double = resolve(&loaded(), 2, Pa::Double);
    assert_eq!(ids(&two_out_double.bases), [None, Some("batter"), None]);
    assert_eq!(two_out_double.scorers.len(), 3);
}

#[test]
fn triple_and_home_run_preserve_scoring_identities_in_lead_order() {
    let triple = resolve(&loaded(), 0, Pa::Triple);
    assert_eq!(ids(&triple.bases), [None, None, Some("batter")]);
    let hr = resolve(&loaded(), 2, Pa::HomeRun);
    assert_eq!(ids(&hr.bases), [None, None, None]);
    assert_eq!(
        hr.scorers
            .iter()
            .map(|s| s.runner.batter_id.as_str())
            .collect::<Vec<_>>(),
        ["third", "second", "first", "batter"]
    );
    assert_eq!(
        resolve(&[None, None, None], 0, Pa::HomeRun).scorers.len(),
        1
    );
}

#[test]
fn generic_outs_never_move_or_score_runners() {
    for outs in 0..3 {
        for event in [Pa::Strikeout, Pa::BattedBallOut] {
            let play = resolve(&loaded(), outs, event);
            assert_eq!(play.bases, loaded());
            assert_eq!(play.outs_on_play, 1);
            assert!(play.scorers.is_empty());
        }
    }
}

#[test]
fn exhaustive_occupancy_event_and_out_context_conservation() {
    for mask in 0..8 {
        for outs in 0..3 {
            for event in [
                Pa::Single,
                Pa::Double,
                Pa::Triple,
                Pa::HomeRun,
                Pa::Walk { intentional: false },
                Pa::HitByPitch,
                Pa::Strikeout,
                Pa::BattedBallOut,
            ] {
                let bases = std::array::from_fn(|i| {
                    (mask & (1 << i) != 0).then(|| runner(&format!("runner-{i}")))
                });
                let before = bases.iter().flatten().count();
                let play = resolve(&bases, outs, event);
                assert_eq!(
                    before + 1,
                    play.bases.iter().flatten().count()
                        + play.scorers.len()
                        + usize::from(play.outs_on_play)
                );
                let mut seen = std::collections::BTreeSet::new();
                for id in play
                    .bases
                    .iter()
                    .flatten()
                    .map(|r| &r.batter_id)
                    .chain(play.scorers.iter().map(|s| &s.runner.batter_id))
                {
                    assert!(seen.insert(id));
                }
            }
        }
    }
}

#[test]
fn invalid_base_context_is_rejected() {
    let policy = AdvancementPolicy::ConservativeOutsV1;
    assert!(resolve_bases(&loaded(), 3, runner("batter"), Pa::Single, policy).is_err());
    assert!(resolve_bases(&loaded(), 0, runner("first"), Pa::Single, policy).is_err());
    assert!(
        resolve_bases(
            &[Some(runner("x")), Some(runner("x")), None],
            0,
            runner("batter"),
            Pa::Single,
            policy
        )
        .is_err()
    );
    assert!(resolve_bases(&[None, None, None], 0, runner(""), Pa::Single, policy).is_err());
}
