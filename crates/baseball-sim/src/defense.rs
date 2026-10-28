//! Opt-in, position-specific error avoidance. No hit conversion or GDP skill.
use crate::{ContactReach, ContextEvent, ContextualModel, EngineError, GameInput, WEIGHT_SCALE};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const DEFENSE_INPUT_VERSION: &str = "1.3.0";
pub const DEFENSE_RULES_VERSION: &str = "error-avoidance-nine-inning-v1";
pub const FIELDING_POSITIONS: [&str; 8] = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DefenseProfile {
    pub id: String,
    pub schema_version: String,
    pub model_id: String,
    pub source_id: String,
    pub player_id: String,
    pub batting_profile_id: String,
    pub year: u16,
    pub position: String,
    pub status: String,
    pub error_ratio: u32,
    pub games: Option<u32>,
    pub inn_outs: Option<u32>,
    pub chances: Option<u32>,
    pub errors: Option<u32>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ErrorComponent {
    pub choice_index: usize,
    pub position: u8,
    pub weight: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DefenseCell {
    pub outs: u8,
    pub base_mask: u8,
    pub ordinary_index: Option<usize>,
    pub components: Vec<ErrorComponent>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DefenseModel {
    pub id: String,
    pub schema_version: String,
    pub model_version: String,
    pub year: u16,
    pub source_id: String,
    pub transition_model_id: String,
    pub retrosheet_lock_sha256: String,
    pub supported_positions: Vec<String>,
    pub minimum_attributed_events: u32,
    pub cells: Vec<DefenseCell>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DefenseConfig {
    pub schema_version: String,
    pub supplement_id: String,
    pub dataset_id: String,
    pub team_id: String,
    pub model: DefenseModel,
    /// Ordered by FIELDING_POSITIONS, independent of batting order. No DH/pitcher.
    pub assignments: [DefenseProfile; 8],
}

fn invalid() -> EngineError {
    EngineError::InvalidInput("Invalid or incompatible error-avoidance input".into())
}

impl DefenseConfig {
    pub(crate) fn validate(&self, input: &GameInput) -> Result<(), EngineError> {
        let model = input.config.contextual_model.as_ref().ok_or_else(invalid)?;
        let d = &self.model;
        if self.schema_version != "1.0.0"
            || d.schema_version != "1.0.0"
            || d.model_version != "error-avoidance-v1"
            || d.year != 2024
            || d.transition_model_id != model.id
            || d.cells.len() != 24
            || d.minimum_attributed_events != 50
            || d.supported_positions != ["1B", "2B", "3B", "SS"]
            || !crate::contract::valid_id(&d.id)
            || !crate::contract::valid_id(&d.source_id)
            || !crate::contract::valid_id(&self.supplement_id)
            || !crate::contract::valid_id(&self.dataset_id)
        {
            return Err(invalid());
        }
        let team = [&input.teams.away, &input.teams.home]
            .into_iter()
            .find(|t| t.id == self.team_id)
            .ok_or_else(invalid)?;
        let mut identities = BTreeSet::new();
        for (index, p) in self.assignments.iter().enumerate() {
            let batting = input
                .profiles
                .iter()
                .find(|b| b.id == p.batting_profile_id)
                .ok_or_else(invalid)?;
            let provenance = batting.provenance.as_ref().ok_or_else(invalid)?;
            if p.schema_version != "1.0.0"
                || p.year != d.year
                || p.model_id != d.id
                || p.source_id != d.source_id
                || provenance.source_id != d.source_id
                || provenance.player_id != p.player_id
                || p.position != FIELDING_POSITIONS[index]
                || !crate::contract::valid_id(&p.id)
                || !identities.insert(&p.player_id)
                || !team
                    .lineup
                    .iter()
                    .any(|b| b.profile_id == p.batting_profile_id)
                || !["observed", "insufficient", "unknown", "modelNeutral"]
                    .contains(&p.status.as_str())
                || (p.status != "observed" && p.error_ratio != WEIGHT_SCALE)
                || p.error_ratio > 1_000_000_000
                || p.games.is_some_and(|g| g < 10)
            {
                return Err(invalid());
            }
            if p.status == "observed"
                && (p.games.is_none()
                    || p.inn_outs.is_none_or(|n| n < 300)
                    || p.chances.is_none_or(|n| n == 0)
                    || p.errors.is_none()
                    || p.errors > p.chances)
            {
                return Err(invalid());
            }
        }
        for (i, cell) in d.cells.iter().enumerate() {
            if usize::from(cell.outs) != i / 8
                || usize::from(cell.base_mask) != i % 8
                || cell.components.len() > 128 * 8
            {
                return Err(invalid());
            }
            let original = model.cell(ContextEvent::OtherContact, cell.outs, cell.base_mask);
            if let Some(index) = cell.ordinary_index {
                let t = original.choices.get(index).ok_or_else(invalid)?;
                // Only ordinary batter-out, runners-hold may exchange mass with ROE.
                if t.reach.is_some()
                    || t.destinations[0] != 0
                    || t.rbi.iter().any(|&r| r)
                    || (1..4).any(|b| {
                        t.destinations[b]
                            != if cell.base_mask & (1 << (b - 1)) != 0 {
                                b as u8
                            } else {
                                5
                            }
                    })
                {
                    return Err(invalid());
                }
            } else if !cell.components.is_empty() {
                return Err(invalid());
            }
            let mut sums = vec![0_u64; original.choices.len()];
            let mut unique = BTreeSet::new();
            for part in &cell.components {
                let t = original
                    .choices
                    .get(part.choice_index)
                    .ok_or_else(invalid)?;
                if !(2..=9).contains(&part.position)
                    || !d
                        .supported_positions
                        .iter()
                        .any(|p| p == FIELDING_POSITIONS[usize::from(part.position - 2)])
                    || part.weight == 0
                    || t.reach != Some(ContactReach::Error)
                    || !unique.insert((part.choice_index, part.position))
                {
                    return Err(invalid());
                }
                sums[part.choice_index] += u64::from(part.weight);
            }
            if sums
                .iter()
                .zip(&original.choices)
                .any(|(s, t)| *s > u64::from(t.weight))
            {
                return Err(invalid());
            }
        }
        Ok(())
    }

    /// One bounded setup pass. Geometry/choice order/support remain unchanged.
    pub fn prepare(&self, base: &ContextualModel) -> ContextualModel {
        let mut model = base.clone();
        for cell in &self.model.cells {
            let Some(out) = cell.ordinary_index else {
                continue;
            };
            let target =
                &mut model.cells[48 + usize::from(cell.outs) * 8 + usize::from(cell.base_mask)];
            let mut deltas = vec![0_i64; target.choices.len()];
            for part in &cell.components {
                let ratio = self.assignments[usize::from(part.position - 2)].error_ratio;
                let adjusted = u64::from(part.weight) * u64::from(ratio) / u64::from(WEIGHT_SCALE);
                deltas[part.choice_index] += adjusted as i64 - i64::from(part.weight);
            }
            // Decreases first, then increases; retain >=1 ticket in every existing choice.
            for negative in [true, false] {
                for (i, &delta) in deltas.iter().enumerate() {
                    if (delta < 0) != negative || delta == 0 {
                        continue;
                    }
                    if delta < 0 {
                        let moved =
                            (-delta as u64).min(u64::from(target.choices[i].weight - 1)) as u32;
                        target.choices[i].weight -= moved;
                        target.choices[out].weight += moved;
                    } else {
                        let moved =
                            (delta as u64).min(u64::from(target.choices[out].weight - 1)) as u32;
                        target.choices[i].weight += moved;
                        target.choices[out].weight -= moved;
                    }
                }
            }
        }
        model
    }
}
