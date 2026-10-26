use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use crate::{AdvancementPolicy, EngineError, PlateAppearance};

#[cfg(test)]
mod tests;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Runner {
    pub batter_id: String,
}

/// First, second, third. Each occupied slot carries the runner's identity.
pub type Bases = [Option<Runner>; 3];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScoringRunner {
    pub runner: Runner,
    /// 1..3 for existing runners, 0 for the batter on a home run.
    pub origin_base: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BasePlay {
    pub bases: Bases,
    /// Lead runner first; permits truncating a non-HR walk-off at the winning run.
    pub scorers: Vec<ScoringRunner>,
    pub outs_on_play: u8,
}

pub fn resolve_bases(
    bases: &Bases,
    outs: u8,
    batter: Runner,
    event: PlateAppearance,
    policy: AdvancementPolicy,
) -> Result<BasePlay, EngineError> {
    let mut ids = BTreeSet::new();
    if outs > 2 || batter.batter_id.is_empty() {
        return Err(EngineError::InvalidInput(
            "Invalid base/outs context".into(),
        ));
    }
    ids.insert(batter.batter_id.as_str());
    for runner in bases.iter().flatten() {
        if runner.batter_id.is_empty() || !ids.insert(runner.batter_id.as_str()) {
            return Err(EngineError::InvalidInput(
                "Duplicate or empty runner identity".into(),
            ));
        }
    }
    match policy {
        AdvancementPolicy::ConservativeOutsV1 => {}
    }
    let mut play = BasePlay {
        bases: bases.clone(),
        scorers: Vec::new(),
        outs_on_play: 0,
    };
    match event {
        PlateAppearance::Strikeout | PlateAppearance::BattedBallOut => {
            play.outs_on_play = 1;
        }
        PlateAppearance::Walk { .. } | PlateAppearance::HitByPitch => {
            if let Some(first) = &bases[0] {
                if let Some(second) = &bases[1] {
                    if let Some(third) = &bases[2] {
                        play.scorers.push(ScoringRunner {
                            runner: third.clone(),
                            origin_base: 3,
                        });
                    }
                    play.bases[2] = Some(second.clone());
                }
                play.bases[1] = Some(first.clone());
            }
            play.bases[0] = Some(batter);
        }
        hit @ (PlateAppearance::Single
        | PlateAppearance::Double
        | PlateAppearance::Triple
        | PlateAppearance::HomeRun) => {
            let hit_bases = hit.hit_bases().expect("remaining events are hits");
            play.bases = std::array::from_fn(|_| None);
            for index in (0..3).rev() {
                if let Some(runner) = &bases[index] {
                    let destination = match (hit_bases, index, outs) {
                        (1, 0, _) => 1,
                        (1, 1, 0 | 1) | (2, 0, 0 | 1) => 2,
                        _ => 3,
                    };
                    if destination == 3 {
                        play.scorers.push(ScoringRunner {
                            runner: runner.clone(),
                            origin_base: index as u8 + 1,
                        });
                    } else {
                        play.bases[destination] = Some(runner.clone());
                    }
                }
            }
            if hit_bases == 4 {
                play.scorers.push(ScoringRunner {
                    runner: batter,
                    origin_base: 0,
                });
            } else {
                play.bases[usize::from(hit_bases - 1)] = Some(batter);
            }
        }
    }
    Ok(play)
}
