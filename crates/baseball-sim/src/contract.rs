use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use crate::EngineError;

pub const INPUT_SCHEMA_VERSION: &str = "1.0.0";
pub const SAMPLED_INPUT_SCHEMA_VERSION: &str = "1.1.0";
pub const RULES_VERSION: &str = "foundation-nine-inning-v1";
pub const WEIGHT_SCALE: u32 = 1_000_000;
pub const MAX_PLATE_APPEARANCES: u32 = 1_000_000;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GameInput {
    pub schema_version: String,
    pub rules_version: String,
    pub seed: String,
    pub config: GameConfig,
    pub detail: Detail,
    pub pitching_environment: PitchingEnvironment,
    pub teams: Teams,
    pub profiles: Vec<PreparedBatterProfile>,
    #[serde(
        default,
        deserialize_with = "present",
        skip_serializing_if = "Option::is_none"
    )]
    pub sampling: Option<SamplingConfig>,
}

// Optional means absent; explicit null must not bypass the strict JSON contract.
pub(crate) fn present<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    T::deserialize(deserializer).map(Some)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SamplingConfig {
    pub rng_version: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GameConfig {
    pub advancement_policy: AdvancementPolicy,
    pub max_innings: u16,
    pub max_plate_appearances: u32,
    #[serde(
        default,
        deserialize_with = "present",
        skip_serializing_if = "Option::is_none"
    )]
    pub contextual_model: Option<crate::ContextualModel>,
    #[serde(
        default,
        deserialize_with = "present",
        skip_serializing_if = "Option::is_none"
    )]
    pub defense: Option<std::sync::Arc<crate::DefenseConfig>>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum AdvancementPolicy {
    #[serde(rename = "conservative-outs-v1")]
    ConservativeOutsV1,
    #[serde(rename = "retrosheet-contextual-v1")]
    RetrosheetContextualV1,
    #[serde(rename = "retrosheet-runner-outs-v1")]
    RetrosheetRunnerOutsV1,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Detail {
    Summary,
    Events,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PitchingEnvironment {
    pub context_id: String,
    pub mode: PitchingMode,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum PitchingMode {
    ScriptedNeutral,
    LeagueAverage,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Teams {
    pub away: Team,
    pub home: Team,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Team {
    pub id: String,
    pub lineup: [Batter; 9],
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Batter {
    pub id: String,
    pub profile_id: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PreparedBatterProfile {
    pub id: String,
    pub model_version: String,
    pub sample_opportunities: u32,
    pub weights: OutcomeWeights,
    pub quality_flags: Vec<String>,
    #[serde(
        default,
        deserialize_with = "present",
        skip_serializing_if = "Option::is_none"
    )]
    pub provenance: Option<ProfileProvenance>,
}

/// Opaque producer metadata. Statistical preparation remains outside this crate.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProfileProvenance {
    pub player_id: String,
    pub source_profile_id: String,
    pub source_id: String,
    pub transformation_version: String,
    pub policy_id: String,
    pub context_id: String,
}

/// Prepared, resolved categories only. Never reinterpret historical otherAtBat as an out.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OutcomeWeights {
    pub single: u32,
    pub double: u32,
    pub triple: u32,
    pub home_run: u32,
    pub walk: u32,
    pub hit_by_pitch: u32,
    pub strikeout: u32,
    pub batted_ball_out: u32,
    #[serde(
        default,
        deserialize_with = "present",
        skip_serializing_if = "Option::is_none"
    )]
    pub other_contact: Option<u32>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "camelCase", from = "StrictPlateAppearance")]
pub enum PlateAppearance {
    Single,
    Double,
    Triple,
    HomeRun,
    Walk { intentional: bool },
    HitByPitch,
    Strikeout,
    BattedBallOut,
    OtherContact,
}

// Serde unit variants ignore residual fields even with deny_unknown_fields.
// Empty struct variants make every event obey the strict shared JSON contract.
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "camelCase", deny_unknown_fields)]
enum StrictPlateAppearance {
    Single {},
    Double {},
    Triple {},
    HomeRun {},
    Walk { intentional: bool },
    HitByPitch {},
    Strikeout {},
    BattedBallOut {},
    OtherContact {},
}

impl From<StrictPlateAppearance> for PlateAppearance {
    fn from(value: StrictPlateAppearance) -> Self {
        match value {
            StrictPlateAppearance::Single {} => Self::Single,
            StrictPlateAppearance::Double {} => Self::Double,
            StrictPlateAppearance::Triple {} => Self::Triple,
            StrictPlateAppearance::HomeRun {} => Self::HomeRun,
            StrictPlateAppearance::Walk { intentional } => Self::Walk { intentional },
            StrictPlateAppearance::HitByPitch {} => Self::HitByPitch,
            StrictPlateAppearance::Strikeout {} => Self::Strikeout,
            StrictPlateAppearance::BattedBallOut {} => Self::BattedBallOut,
            StrictPlateAppearance::OtherContact {} => Self::OtherContact,
        }
    }
}

impl PlateAppearance {
    pub fn hit_bases(self) -> Option<u8> {
        match self {
            Self::Single => Some(1),
            Self::Double => Some(2),
            Self::Triple => Some(3),
            Self::HomeRun => Some(4),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Side {
    Away,
    Home,
}

impl Side {
    pub fn index(self) -> usize {
        match self {
            Self::Away => 0,
            Self::Home => 1,
        }
    }
}

impl GameInput {
    pub fn team(&self, side: Side) -> &Team {
        match side {
            Side::Away => &self.teams.away,
            Side::Home => &self.teams.home,
        }
    }

    pub fn validate(&self) -> Result<(), EngineError> {
        let invalid = |message: &str| EngineError::InvalidInput(message.to_owned());
        if ![
            INPUT_SCHEMA_VERSION,
            SAMPLED_INPUT_SCHEMA_VERSION,
            crate::CONTEXT_INPUT_SCHEMA_VERSION,
            crate::DEFENSE_INPUT_VERSION,
            crate::RUNNER_INPUT_VERSION,
        ]
        .contains(&self.schema_version.as_str())
        {
            return Err(invalid("Unsupported input schema or rules version"));
        }
        let defensive = self.schema_version == crate::DEFENSE_INPUT_VERSION;
        let runner = self.schema_version == crate::RUNNER_INPUT_VERSION;
        let contextual =
            runner || defensive || self.schema_version == crate::CONTEXT_INPUT_SCHEMA_VERSION;
        if !defensive && self.config.defense.is_some() {
            return Err(invalid("Legacy input cannot enable defense"));
        }
        if contextual {
            if self.rules_version
                != if defensive {
                    crate::DEFENSE_RULES_VERSION
                } else if runner {
                    crate::RUNNER_RULES_VERSION
                } else {
                    crate::CONTEXT_RULES_VERSION
                }
                || self.config.advancement_policy
                    != if runner {
                        AdvancementPolicy::RetrosheetRunnerOutsV1
                    } else {
                        AdvancementPolicy::RetrosheetContextualV1
                    }
            {
                return Err(invalid(
                    "Contextual inputs require contextual rules and advancement policy",
                ));
            }
            self.config
                .contextual_model
                .as_ref()
                .ok_or_else(|| invalid("Missing contextual model"))?
                .validate()?;
            let version = &self
                .config
                .contextual_model
                .as_ref()
                .expect("checked model")
                .model_version;
            if version
                != if runner {
                    crate::RUNNER_MODEL_VERSION
                } else {
                    "retrosheet-contact-transitions-v1"
                }
            {
                return Err(invalid(
                    "Transition model and rules version are incompatible",
                ));
            }
            if defensive {
                self.config
                    .defense
                    .as_ref()
                    .ok_or_else(|| invalid("Missing defense configuration"))?
                    .validate(self)?;
            }
        } else if self.rules_version != RULES_VERSION
            || self.config.contextual_model.is_some()
            || self.config.advancement_policy != AdvancementPolicy::ConservativeOutsV1
        {
            return Err(invalid(
                "Legacy inputs require their original rules and policy",
            ));
        }
        let sampled = self.schema_version != INPUT_SCHEMA_VERSION;
        if sampled {
            if self.sampling.as_ref().map(|s| s.rng_version.as_str()) != Some(crate::RNG_VERSION)
                || self.pitching_environment.mode != PitchingMode::LeagueAverage
            {
                return Err(invalid(
                    "Sampled v1.1 input requires supported RNG and league-average context",
                ));
            }
        } else if self.sampling.is_some()
            || self.pitching_environment.mode != PitchingMode::ScriptedNeutral
            || self.profiles.iter().any(|p| p.provenance.is_some())
        {
            return Err(invalid("v1.0 accepts scripted inputs only"));
        }
        if self.seed.is_empty()
            || (self.seed.len() > 1 && self.seed.starts_with('0'))
            || !self.seed.bytes().all(|c| c.is_ascii_digit())
            || self.seed.parse::<u64>().is_err()
        {
            return Err(invalid("Seed must be a canonical decimal u64 string"));
        }
        if self.config.max_innings < 9
            || self.config.max_plate_appearances == 0
            || self.config.max_plate_appearances > MAX_PLATE_APPEARANCES
        {
            return Err(invalid("Invalid game safety limits"));
        }
        if !valid_id(&self.pitching_environment.context_id) {
            return Err(invalid("Invalid pitching context ID"));
        }
        if self.profiles.is_empty() || self.profiles.len() > 18 {
            return Err(invalid("Provide 1..18 prepared profiles"));
        }
        let mut profile_ids = BTreeSet::new();
        for profile in &self.profiles {
            if contextual {
                if profile.weights.other_contact.is_none() || profile.weights.batted_ball_out != 0 {
                    return Err(invalid(
                        "Contextual profiles require otherContact and zero legacy out mass",
                    ));
                }
            } else if profile.weights.other_contact.is_some() {
                return Err(invalid(
                    "Legacy profiles cannot contain unresolved contact mass",
                ));
            }
            if sampled {
                let Some(p) = &profile.provenance else {
                    return Err(invalid("Sampled profiles require provenance"));
                };
                if [
                    &p.player_id,
                    &p.source_profile_id,
                    &p.source_id,
                    &p.transformation_version,
                    &p.policy_id,
                    &p.context_id,
                ]
                .iter()
                .any(|id| !valid_id(id))
                    || p.context_id != self.pitching_environment.context_id
                {
                    return Err(invalid("Invalid or mismatched profile provenance"));
                }
            }
            if !valid_id(&profile.id)
                || !valid_id(&profile.model_version)
                || !profile_ids.insert(profile.id.as_str())
                || profile.sample_opportunities == 0
                || profile.quality_flags.len() > 32
                || profile
                    .quality_flags
                    .iter()
                    .any(|s| s.is_empty() || s.chars().count() > 128)
            {
                return Err(invalid("Invalid prepared profile metadata or duplicate ID"));
            }
            let w = &profile.weights;
            let weights = [
                w.single,
                w.double,
                w.triple,
                w.home_run,
                w.walk,
                w.hit_by_pitch,
                w.strikeout,
                w.batted_ball_out,
                w.other_contact.unwrap_or(0),
            ];
            if weights.iter().map(|&v| u64::from(v)).sum::<u64>() != u64::from(WEIGHT_SCALE) {
                return Err(invalid("Prepared outcome weights must sum to 1000000"));
            }
        }
        if !valid_id(&self.teams.away.id)
            || !valid_id(&self.teams.home.id)
            || self.teams.away.id == self.teams.home.id
        {
            return Err(invalid("Team IDs must be valid and distinct"));
        }
        let mut batter_ids = BTreeSet::new();
        for team in [&self.teams.away, &self.teams.home] {
            for batter in &team.lineup {
                if !valid_id(&batter.id)
                    || !batter_ids.insert(batter.id.as_str())
                    || !profile_ids.contains(batter.profile_id.as_str())
                {
                    return Err(invalid(
                        "Batter IDs must be globally unique with known profiles",
                    ));
                }
            }
        }
        Ok(())
    }
}

pub(crate) fn valid_id(id: &str) -> bool {
    let valid_first = id.as_bytes().first().is_some_and(u8::is_ascii_alphanumeric);
    valid_first
        && id.len() <= 128
        && id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"._:-".contains(&c))
}
