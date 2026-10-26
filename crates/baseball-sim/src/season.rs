//! Bounded single-user seasons; schedules are reconstructed without host randomness.
use crate::{
    Detail, ENGINE_VERSION, EngineError, GameConfig, GameInput, InningScore, PitchingEnvironment,
    PlayRecord, PreparedBatterProfile, SamplingConfig, Side, SplitMix64, StatLine, Team,
    TeamBoxScore, Teams, simulate_game,
};
use serde::{Deserialize, Serialize};
use std::{collections::BTreeSet, fmt};

pub const SEASON_MODEL_VERSION: &str = "round-robin-season-v1";
pub const SEED_DERIVATION_VERSION: &str = "splitmix64-index-v1";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum LineupSourceKind {
    ObservedFixedLineups,
    ReconstructedFixedLineups,
    Synthetic,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SeasonInput {
    pub schema_version: String,
    pub model_version: String,
    pub seed_derivation_version: String,
    pub seed: String,
    #[serde(default = "default_games")]
    pub games: u16,
    pub detail: Detail,
    pub game_schema_version: String,
    pub rules_version: String,
    pub config: GameConfig,
    pub pitching_environment: PitchingEnvironment,
    pub sampling: SamplingConfig,
    pub user_team: Team,
    pub user_lineup_kind: LineupSourceKind,
    pub opponent_set_kind: LineupSourceKind,
    pub opponents: Vec<Team>,
    pub profiles: Vec<PreparedBatterProfile>,
}
fn default_games() -> u16 {
    162
}

#[derive(Debug, PartialEq, Eq)]
pub enum SeasonError {
    InvalidInput(String),
    GameFailed {
        game_number: u16,
        source: EngineError,
    },
}
impl fmt::Display for SeasonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInput(s) => write!(f, "Invalid season input: {s}"),
            Self::GameFailed {
                game_number,
                source,
            } => write!(f, "Season game {game_number} failed: {source}"),
        }
    }
}
impl std::error::Error for SeasonError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::GameFailed { source, .. } => Some(source),
            _ => None,
        }
    }
}

/// Direct indexed derivation. This does not consume a preceding game's RNG state.
pub fn season_game_seed(seed: u64, index: u16) -> u64 {
    SplitMix64::new(seed.wrapping_add(u64::from(index).wrapping_mul(0x9e3779b97f4a7c15))).next_u64()
}

impl SeasonInput {
    /// Stable opponent order by ID; paired away/home games against each opponent.
    pub fn game_input(&self, index: u16) -> Result<GameInput, SeasonError> {
        if index >= self.games || self.opponents.is_empty() {
            return Err(SeasonError::InvalidInput(
                "Game index outside schedule".into(),
            ));
        }
        let seed = self
            .seed
            .parse::<u64>()
            .map_err(|_| SeasonError::InvalidInput("Seed must be a decimal u64".into()))?;
        let mut opponents: Vec<_> = self.opponents.iter().collect();
        opponents.sort_by(|a, b| a.id.cmp(&b.id));
        let opponent = opponents[(usize::from(index) / 2) % opponents.len()];
        let teams = if index % 2 == 0 {
            Teams {
                away: self.user_team.clone(),
                home: opponent.clone(),
            }
        } else {
            Teams {
                away: opponent.clone(),
                home: self.user_team.clone(),
            }
        };
        let ids: BTreeSet<_> = teams
            .away
            .lineup
            .iter()
            .chain(&teams.home.lineup)
            .map(|b| b.profile_id.as_str())
            .collect();
        let mut profiles: Vec<_> = self
            .profiles
            .iter()
            .filter(|p| ids.contains(p.id.as_str()))
            .cloned()
            .collect();
        profiles.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(GameInput {
            schema_version: self.game_schema_version.clone(),
            rules_version: self.rules_version.clone(),
            seed: season_game_seed(seed, index).to_string(),
            config: self.config.clone(),
            detail: self.detail,
            pitching_environment: self.pitching_environment.clone(),
            teams,
            profiles,
            sampling: Some(self.sampling.clone()),
        })
    }

    pub fn validate(&self) -> Result<(), SeasonError> {
        let invalid = |s: &str| SeasonError::InvalidInput(s.into());
        if self.schema_version != "1.0.0"
            || self.model_version != SEASON_MODEL_VERSION
            || self.seed_derivation_version != SEED_DERIVATION_VERSION
            || self.games == 0
            || self.games > 1000
            || self.opponents.is_empty()
            || self.opponents.len() > 30
            || self.profiles.is_empty()
            || self.profiles.len() > 279
        {
            return Err(invalid("Unsupported version or season bounds"));
        }
        if self.seed.parse::<u64>().is_err()
            || self.seed.starts_with('+')
            || (self.seed.len() > 1 && self.seed.starts_with('0'))
        {
            return Err(invalid("Seed must be a canonical decimal u64"));
        }
        let mut teams = BTreeSet::new();
        teams.insert(self.user_team.id.as_str());
        if self.opponents.iter().any(|t| !teams.insert(t.id.as_str())) {
            return Err(invalid(
                "Team IDs must be unique; user cannot oppose itself",
            ));
        }
        let mut profiles = BTreeSet::new();
        if self
            .profiles
            .iter()
            .any(|p| !profiles.insert(p.id.as_str()))
        {
            return Err(invalid("Duplicate profile ID"));
        }
        // Validate every opponent, including ones a shortened season does not reach.
        let mut probe = self.clone();
        probe.games = 60;
        for index in 0..self.opponents.len() {
            let game = probe.game_input((index * 2) as u16)?;
            game.validate().map_err(|e| invalid(&e.to_string()))?;
            let mut identities = BTreeSet::new();
            for (team, kind) in [
                (&game.teams.away, self.user_lineup_kind),
                (&game.teams.home, self.opponent_set_kind),
            ] {
                if kind == LineupSourceKind::Synthetic {
                    continue;
                }
                for batter in &team.lineup {
                    let player = game
                        .profiles
                        .iter()
                        .find(|p| p.id == batter.profile_id)
                        .and_then(|p| p.provenance.as_ref())
                        .expect("validated sampled provenance");
                    if !identities.insert(player.player_id.as_str()) {
                        return Err(invalid("Duplicate player identity in a matchup"));
                    }
                }
            }
        }
        if self.game_schema_version == "1.0.0" {
            return Err(invalid("Seasons require sampled games"));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SeasonGame {
    pub game_number: u16,
    pub opponent_id: String,
    pub user_home: bool,
    pub seed: String,
    /// User, opponent (independent of home/away).
    pub score: [u32; 2],
    pub won: bool,
    pub innings: u16,
    pub plate_appearances: u32,
    /// Lines retain away/home labels; boxes are ordered user/opponent.
    pub line_score: Vec<InningScore>,
    pub teams: [TeamBoxScore; 2],
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_log: Option<Vec<PlayRecord>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SeasonResult {
    pub schema_version: String,
    pub engine_version: String,
    pub input: SeasonInput,
    pub wins: u16,
    pub losses: u16,
    pub runs_scored: u32,
    pub runs_allowed: u32,
    pub run_differential: i64,
    pub team: TeamBoxScore,
    pub opponent_totals: StatLine,
    pub games: Vec<SeasonGame>,
}

pub fn simulate_season(input: SeasonInput) -> Result<SeasonResult, SeasonError> {
    input.validate()?;
    let mut games = Vec::with_capacity(usize::from(input.games));
    let mut wins = 0;
    let mut runs_scored = 0;
    let mut runs_allowed = 0;
    let mut aggregate: Option<TeamBoxScore> = None;
    let mut opponent_totals = StatLine::default();
    for index in 0..input.games {
        let game_input = input.game_input(index)?;
        let result = simulate_game(game_input).map_err(|source| SeasonError::GameFailed {
            game_number: index + 1,
            source,
        })?;
        let user_home = index % 2 == 1;
        let user = usize::from(user_home);
        let opponent = 1 - user;
        let won = result.winner == if user_home { Side::Home } else { Side::Away };
        wins += u16::from(won);
        runs_scored += result.score[user];
        runs_allowed += result.score[opponent];
        let boxes = [result.teams[user].clone(), result.teams[opponent].clone()];
        if let Some(total) = &mut aggregate {
            total.totals.add(&boxes[0].totals);
            total.outs_recorded += boxes[0].outs_recorded;
            total.left_on_base += boxes[0].left_on_base;
            for (b, game) in total.batters.iter_mut().zip(&boxes[0].batters) {
                b.stats.add(&game.stats);
            }
        } else {
            aggregate = Some(boxes[0].clone());
        }
        opponent_totals.add(&boxes[1].totals);
        games.push(SeasonGame {
            game_number: index + 1,
            opponent_id: boxes[1].team_id.clone(),
            user_home,
            seed: result.input.seed,
            score: [result.score[user], result.score[opponent]],
            won,
            innings: result.final_state.inning,
            plate_appearances: result.final_state.plate_appearances,
            line_score: result.line_score,
            teams: boxes,
            event_log: result.event_log,
        });
    }
    Ok(SeasonResult {
        schema_version: "1.0.0".into(),
        engine_version: ENGINE_VERSION.into(),
        wins,
        losses: input.games - wins,
        runs_scored,
        runs_allowed,
        run_differential: i64::from(runs_scored) - i64::from(runs_allowed),
        team: aggregate.expect("validated positive season length"),
        opponent_totals,
        games,
        input,
    })
}
