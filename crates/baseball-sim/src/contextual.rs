//! Empirical hit/contact transitions, with explicit unsupported-play proxies.
use crate::{BasePlay, Bases, EngineError, PlateAppearance, Runner, ScoringRunner, WEIGHT_SCALE};
use serde::{Deserialize, Serialize};

pub const CONTEXT_RULES_VERSION: &str = "contextual-nine-inning-v1";
pub const CONTEXT_INPUT_SCHEMA_VERSION: &str = "1.2.0";
pub const RUNNER_INPUT_VERSION: &str = "1.4.0";
pub const RUNNER_RULES_VERSION: &str = "runner-outs-nine-inning-v1";
pub const RUNNER_MODEL_VERSION: &str = "retrosheet-runner-transitions-v1";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum RunnerOutKind {
    None,
    Tag,
    Force,
    BatterBeforeFirst,
}

/// A bounded joint outcome, never independent retirement coins. Timing is explicit.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RunnerPlay {
    pub out_kinds: [RunnerOutKind; 4],
    /// Attempted base, 1..4 (home); zero for a runner not retired.
    pub out_bases: [u8; 4],
    pub runs_before_outs: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ContextEvent {
    Single,
    Double,
    OtherContact,
}
impl ContextEvent {
    pub fn from_event(event: PlateAppearance) -> Option<Self> {
        match event {
            PlateAppearance::Single => Some(Self::Single),
            PlateAppearance::Double => Some(Self::Double),
            PlateAppearance::OtherContact => Some(Self::OtherContact),
            _ => None,
        }
    }
    fn index(self) -> usize {
        match self {
            Self::Single => 0,
            Self::Double => 1,
            Self::OtherContact => 2,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RunnerTransition {
    pub weight: u32,
    /// Batter, runner at first, second, third. 0=out, 1..3=base, 4=run, 5=absent.
    pub destinations: [u8; 4],
    /// RBI credit belongs to scoring runners, allowing correct walk-off truncation.
    pub rbi: [bool; 4],
    #[serde(
        default,
        deserialize_with = "crate::contract::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub reach: Option<ContactReach>,
    #[serde(
        default,
        deserialize_with = "crate::contract::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub runner_play: Option<RunnerPlay>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ContactReach {
    Error,
    FieldersChoice,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TransitionCell {
    pub event: ContextEvent,
    pub outs: u8,
    pub base_mask: u8,
    pub observations: u32,
    pub fallback: bool,
    pub choices: Vec<RunnerTransition>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ContextualModel {
    pub id: String,
    pub model_version: String,
    pub source_id: String,
    pub cells: Vec<TransitionCell>,
}

pub fn base_mask(bases: &Bases) -> u8 {
    bases
        .iter()
        .enumerate()
        .fold(0, |mask, (i, r)| mask | (u8::from(r.is_some()) << i))
}
impl ContextualModel {
    pub fn cell(&self, event: ContextEvent, outs: u8, mask: u8) -> &TransitionCell {
        &self.cells[event.index() * 24 + usize::from(outs) * 8 + usize::from(mask)]
    }
    pub fn validate(&self) -> Result<(), EngineError> {
        let invalid = || EngineError::InvalidInput("Invalid contextual transition model".into());
        if !["retrosheet-contact-transitions-v1", RUNNER_MODEL_VERSION]
            .contains(&self.model_version.as_str())
            || !crate::contract::valid_id(&self.id)
            || !crate::contract::valid_id(&self.source_id)
            || self.cells.len() != 72
        {
            return Err(invalid());
        }
        for (i, cell) in self.cells.iter().enumerate() {
            if cell.event.index() != i / 24
                || usize::from(cell.outs) != (i % 24) / 8
                || usize::from(cell.base_mask) != i % 8
                || cell.choices.is_empty()
                || cell.choices.len() > 128
                || cell
                    .choices
                    .iter()
                    .map(|c| u64::from(c.weight))
                    .sum::<u64>()
                    != u64::from(WEIGHT_SCALE)
            {
                return Err(invalid());
            }
            for (index, choice) in cell.choices.iter().enumerate() {
                if self.model_version != RUNNER_MODEL_VERSION && choice.runner_play.is_some() {
                    return Err(invalid());
                }
                validate_transition(cell.event, cell.outs, cell.base_mask, choice).map_err(
                    |e| {
                        EngineError::InvalidInput(format!(
                            "Transition cell {i} choice {index}: {e}; {choice:?}"
                        ))
                    },
                )?;
            }
        }
        Ok(())
    }
}

fn validate_transition(
    event: ContextEvent,
    outs: u8,
    mask: u8,
    t: &RunnerTransition,
) -> Result<(), EngineError> {
    let invalid = || EngineError::InvalidInput("Illegal runner transition".into());
    if outs > 2 || mask > 7 || t.weight == 0 {
        return Err(invalid());
    }
    if let Some(play) = t.runner_play {
        return validate_runner_play(event, outs, mask, t, play);
    }
    let mut occupied = 0_u8;
    let mut retired = 0;
    let mut last_destination = 0;
    for (i, &dest) in t.destinations.iter().enumerate() {
        let present = i == 0 || mask & (1 << (i - 1)) != 0;
        if !present {
            if dest != 5 || t.rbi[i] {
                return Err(invalid());
            }
            continue;
        }
        if dest > 4 || (t.rbi[i] && dest != 4) {
            return Err(invalid());
        }
        if dest == 0 {
            retired += 1;
            continue;
        }
        if i > 0 && dest < i as u8 {
            return Err(invalid());
        }
        if dest < last_destination {
            return Err(invalid());
        }
        last_destination = dest;
        if dest < 4 {
            let bit = 1 << dest;
            if occupied & bit != 0 {
                return Err(invalid());
            }
            occupied |= bit;
        }
    }
    match event {
        ContextEvent::Single | ContextEvent::Double => {
            let expected = if event == ContextEvent::Single { 1 } else { 2 };
            if t.destinations[0] != expected || retired != 0 || t.reach.is_some() {
                return Err(invalid());
            }
        }
        ContextEvent::OtherContact => {
            if let Some(reach) = t.reach {
                if !(1..=3).contains(&t.destinations[0])
                    || (reach == ContactReach::Error && retired != 0)
                    || (reach == ContactReach::FieldersChoice && retired > 1)
                {
                    return Err(invalid());
                }
            } else if t.destinations[0] != 0 || !(1..=2).contains(&retired) {
                return Err(invalid());
            }
            if retired == 2
                && (outs == 2
                    || mask & 1 == 0
                    || t.destinations[1] != 0
                    || t.destinations.contains(&4)
                    || t.rbi.iter().any(|&b| b))
            {
                return Err(invalid());
            }
        }
    }
    if retired + outs > 3 || (retired + outs == 3 && t.destinations.contains(&4)) {
        return Err(invalid());
    }
    Ok(())
}

fn validate_runner_play(
    event: ContextEvent,
    outs: u8,
    mask: u8,
    t: &RunnerTransition,
    play: RunnerPlay,
) -> Result<(), EngineError> {
    use RunnerOutKind::{BatterBeforeFirst, Force, None as NoOut, Tag};
    let invalid = || EngineError::InvalidInput("Illegal runner-play transition".into());
    let mut retired = 0;
    let mut last = 0;
    let mut occupied = 0_u8;
    for (i, (&d, &kind)) in t.destinations.iter().zip(&play.out_kinds).enumerate() {
        let out_base = play.out_bases[i];
        if (kind == NoOut && out_base != 0)
            || (kind != NoOut && !(1..=4).contains(&out_base))
            || (kind == Tag && out_base <= i as u8)
            || (kind == Force && out_base != i as u8 + 1)
        {
            return Err(invalid());
        }
        let present = i == 0 || mask & (1 << (i - 1)) != 0;
        if !present {
            if d != 5 || kind != NoOut || t.rbi[i] {
                return Err(invalid());
            }
            continue;
        }
        if d > 4 || (d == 0) != (kind != NoOut) || (t.rbi[i] && d != 4) {
            return Err(invalid());
        }
        if kind == BatterBeforeFirst && i != 0 {
            return Err(invalid());
        }
        if kind == Force && (i == 0 || mask & ((1 << i) - 1) != (1 << i) - 1) {
            return Err(invalid());
        }
        if d == 0 {
            retired += 1;
            continue;
        }
        if (i > 0 && d < i as u8) || d < last {
            return Err(invalid());
        }
        last = d;
        if d < 4 {
            if occupied & (1 << d) != 0 {
                return Err(invalid());
            }
            occupied |= 1 << d;
        }
    }
    // Promoted source cases contain at most one retirement. Multiple-out v1 GDP
    // choices retain their original representation and interpretation.
    if retired > 1 || retired + outs > 3 {
        return Err(invalid());
    }
    match event {
        ContextEvent::Single | ContextEvent::Double => {
            let hit = if event == ContextEvent::Single { 1 } else { 2 };
            if t.reach.is_some()
                || (t.destinations[0] != 0 && t.destinations[0] < hit)
                || play
                    .out_kinds
                    .iter()
                    .any(|k| matches!(k, Force | BatterBeforeFirst))
            {
                return Err(invalid());
            }
            if play.out_kinds[0] == Tag && play.out_bases[0] <= hit {
                return Err(invalid());
            }
        }
        ContextEvent::OtherContact => {
            if t.reach != Some(ContactReach::FieldersChoice)
                || t.destinations[0] != 1
                || retired != 1
                || !play.out_kinds.contains(&Force)
            {
                return Err(invalid());
            }
        }
    }
    if t.destinations.contains(&4) && retired > 0 {
        let suppress = outs + retired == 3
            && play
                .out_kinds
                .iter()
                .any(|k| matches!(k, Force | BatterBeforeFirst));
        if !(suppress
            || play.runs_before_outs && outs + retired == 3 && play.out_kinds.contains(&Tag))
        {
            return Err(invalid());
        }
        if suppress && play.runs_before_outs {
            return Err(invalid());
        }
    } else if play.runs_before_outs {
        return Err(invalid());
    }
    if play.runs_before_outs {
        let retired_origin = play
            .out_kinds
            .iter()
            .position(|&kind| kind == Tag)
            .ok_or_else(invalid)?;
        // A trailing runner cannot score before a still-live lead runner's tag
        // retirement without passing that runner. The source-supported timing
        // runs must all belong to runners ahead of the later retirement.
        if t.destinations[..=retired_origin].contains(&4) {
            return Err(invalid());
        }
    }
    Ok(())
}

pub fn resolve_transition(
    bases: &Bases,
    outs: u8,
    batter: Runner,
    event: PlateAppearance,
    t: &RunnerTransition,
) -> Result<BasePlay, EngineError> {
    let kind = ContextEvent::from_event(event)
        .ok_or_else(|| EngineError::InvalidInput("Event has no contextual transitions".into()))?;
    validate_transition(kind, outs, base_mask(bases), t)?;
    // Reuse the existing identity validation before constructing any transition.
    crate::resolve_bases(
        bases,
        outs,
        batter.clone(),
        if event == PlateAppearance::OtherContact {
            PlateAppearance::BattedBallOut
        } else {
            event
        },
        crate::AdvancementPolicy::ConservativeOutsV1,
    )?;
    let mut play = BasePlay {
        bases: std::array::from_fn(|_| None),
        scorers: Vec::new(),
        outs_on_play: 0,
    };
    for i in (0..4).rev() {
        let runner = if i == 0 {
            Some(batter.clone())
        } else {
            bases[i - 1].clone()
        };
        if let Some(runner) = runner {
            match t.destinations[i] {
                0 => play.outs_on_play += 1,
                4 => play.scorers.push(ScoringRunner {
                    runner,
                    origin_base: i as u8,
                }),
                dest => play.bases[usize::from(dest - 1)] = Some(runner),
            }
        }
    }
    if let Some(metadata) = t.runner_play {
        if outs + play.outs_on_play == 3
            && metadata
                .out_kinds
                .iter()
                .any(|k| matches!(k, RunnerOutKind::Force | RunnerOutKind::BatterBeforeFirst))
        {
            play.scorers.clear();
        }
    }
    Ok(play)
}
