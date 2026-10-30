use std::fmt;

use serde::{Deserialize, Serialize};

use crate::{
    Bases, Batter, BatterBoxScore, Detail, ENGINE_VERSION, GameInput, PlateAppearance, Runner,
    Side, StatLine, TeamBoxScore, resolve_bases,
};

pub const RESULT_SCHEMA_VERSION: &str = "1.0.0";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Half {
    Top,
    Bottom,
}

impl Half {
    pub fn batting_side(self) -> Side {
        match self {
            Self::Top => Side::Away,
            Self::Bottom => Side::Home,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum GameStatus {
    InProgress,
    Final,
    Aborted,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum LimitReached {
    MaxInnings,
    MaxPlateAppearances,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EngineError {
    InvalidInput(String),
    GameFinished,
    Aborted(LimitReached),
    IncompleteGame,
    ScriptExhausted { plate_appearances: u32 },
    TrailingEvents { remaining: usize },
}

impl fmt::Display for EngineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInput(message) => write!(f, "Invalid simulation input: {message}"),
            Self::GameFinished => write!(f, "Game is already final"),
            Self::Aborted(reason) => write!(f, "Game aborted at safety limit: {reason:?}"),
            Self::IncompleteGame => write!(f, "Game has not finished"),
            Self::ScriptExhausted { plate_appearances } => {
                write!(
                    f,
                    "Script exhausted after {plate_appearances} plate appearances"
                )
            }
            Self::TrailingEvents { remaining } => {
                write!(f, "{remaining} events follow the final play")
            }
        }
    }
}

impl std::error::Error for EngineError {}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GameSnapshot {
    pub inning: u16,
    pub half: Half,
    pub outs: u8,
    pub bases: Bases,
    /// Away, home. Batting cursors advance even on the inning-ending PA.
    pub next_batter: [u8; 2],
    pub score: [u32; 2],
    pub plate_appearances: u32,
    pub status: GameStatus,
    pub abort_reason: Option<LimitReached>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct InningScore {
    pub inning: u16,
    pub away: u32,
    /// None means home never began this half-inning, not zero runs in a played half.
    pub home: Option<u32>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PlayRecord {
    pub event_index: u32,
    pub inning: u16,
    pub half: Half,
    pub batter_id: String,
    pub supplied_event: PlateAppearance,
    /// May differ on a game-ending non-HR extra-base hit.
    pub credited_event: PlateAppearance,
    pub outs_on_play: u8,
    pub scored_batter_ids: Vec<String>,
    pub state_after: GameSnapshot,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transition_index: Option<usize>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GameResult {
    pub schema_version: String,
    pub engine_version: String,
    /// Retain the immutable rules, ordered lineups, profiles, context and seed for replay.
    pub input: GameInput,
    pub winner: Side,
    /// Away, home.
    pub score: [u32; 2],
    pub line_score: Vec<InningScore>,
    /// Away, home, with batters in lineup order.
    pub teams: [TeamBoxScore; 2],
    pub final_state: GameSnapshot,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_log: Option<Vec<PlayRecord>>,
}

/// State is observable but cannot be mutated or restored by callers.
pub struct Game {
    input: GameInput,
    state: GameSnapshot,
    stats: [[StatLine; 9]; 2],
    outs_recorded: [u32; 2],
    left_on_base: [u32; 2],
    line_score: Vec<InningScore>,
    event_log: Option<Vec<PlayRecord>>,
}

impl Game {
    pub fn new(input: GameInput) -> Result<Self, EngineError> {
        input.validate()?;
        Ok(Self::from_validated(input))
    }

    /// Internal only: caller has validated this game or every immutable season matchup.
    pub(crate) fn from_validated(input: GameInput) -> Self {
        let event_log = (input.detail == Detail::Events).then(Vec::new);
        Self {
            input,
            state: GameSnapshot {
                inning: 1,
                half: Half::Top,
                outs: 0,
                bases: std::array::from_fn(|_| None),
                next_batter: [0, 0],
                score: [0, 0],
                plate_appearances: 0,
                status: GameStatus::InProgress,
                abort_reason: None,
            },
            stats: [[StatLine::default(); 9]; 2],
            outs_recorded: [0, 0],
            left_on_base: [0, 0],
            line_score: vec![InningScore {
                inning: 1,
                away: 0,
                home: None,
            }],
            event_log,
        }
    }

    pub fn snapshot(&self) -> &GameSnapshot {
        &self.state
    }

    pub fn current_batter(&self) -> Option<&Batter> {
        (self.state.status == GameStatus::InProgress).then(|| {
            let side = self.state.half.batting_side();
            &self.input.team(side).lineup[usize::from(self.state.next_batter[side.index()])]
        })
    }

    pub fn box_score(&self, side: Side) -> TeamBoxScore {
        let index = side.index();
        let team = self.input.team(side);
        let mut totals = StatLine::default();
        for line in &self.stats[index] {
            totals.add(line);
        }
        TeamBoxScore {
            team_id: team.id.clone(),
            totals,
            outs_recorded: self.outs_recorded[index],
            left_on_base: self.left_on_base[index],
            batters: team
                .lineup
                .iter()
                .zip(&self.stats[index])
                .map(|(batter, stats)| BatterBoxScore {
                    batter_id: batter.id.clone(),
                    stats: *stats,
                })
                .collect(),
        }
    }

    pub fn apply_event(&mut self, event: PlateAppearance) -> Result<PlayRecord, EngineError> {
        self.apply_play(event, None)
    }

    /// Replay a contextual choice by its index in the current event/base/out cell.
    pub fn apply_contextual_event(
        &mut self,
        event: PlateAppearance,
        index: usize,
    ) -> Result<PlayRecord, EngineError> {
        self.apply_play(event, Some(index))
    }

    fn apply_play(
        &mut self,
        event: PlateAppearance,
        transition_index: Option<usize>,
    ) -> Result<PlayRecord, EngineError> {
        match self.state.status {
            GameStatus::Final => return Err(EngineError::GameFinished),
            GameStatus::Aborted => {
                return Err(EngineError::Aborted(
                    self.state.abort_reason.expect("aborted has reason"),
                ));
            }
            GameStatus::InProgress => {}
        }
        let inning = self.state.inning;
        let half = self.state.half;
        let side = half.batting_side();
        let team = side.index();
        let batter_index = usize::from(self.state.next_batter[team]);
        let batter_id = self.input.team(side).lineup[batter_index].id.clone();
        let occupied_before = self.state.bases.iter().flatten().count();
        let transition = if let Some(kind) = crate::ContextEvent::from_event(event) {
            if let Some(model) = &self.input.config.contextual_model {
                let index = transition_index.ok_or_else(|| {
                    EngineError::InvalidInput("Contextual event requires a transition index".into())
                })?;
                Some(
                    model
                        .cell(kind, self.state.outs, crate::base_mask(&self.state.bases))
                        .choices
                        .get(index)
                        .ok_or_else(|| {
                            EngineError::InvalidInput("Transition index outside cell".into())
                        })?
                        .clone(),
                )
            } else {
                None
            }
        } else {
            None
        };
        if transition_index.is_some() && transition.is_none() {
            return Err(EngineError::InvalidInput(
                "Unexpected contextual transition".into(),
            ));
        }
        let mut play = if let Some(t) = &transition {
            crate::resolve_transition(
                &self.state.bases,
                self.state.outs,
                Runner {
                    batter_id: batter_id.clone(),
                },
                event,
                t,
            )?
        } else {
            resolve_bases(
                &self.state.bases,
                self.state.outs,
                Runner {
                    batter_id: batter_id.clone(),
                },
                event,
                crate::AdvancementPolicy::ConservativeOutsV1,
            )?
        };
        let walk_off = inning >= 9
            && half == Half::Bottom
            && self.state.score[1] + play.scorers.len() as u32 > self.state.score[0];
        let runs = if walk_off && event != PlateAppearance::HomeRun {
            self.state.score[0] - self.state.score[1] + 1
        } else {
            play.scorers.len() as u32
        };
        // A proven timing run preceded the sole tag out. On a walk-off the game
        // ended at that run, so the later retirement cannot count.
        if walk_off
            && transition
                .as_ref()
                .and_then(|t| t.runner_play)
                .is_some_and(|p| p.runs_before_outs)
        {
            play.outs_on_play = 0;
        }
        let mut credited_event = event;
        if walk_off && event != PlateAppearance::HomeRun {
            if let Some(bases) = event.hit_bases() {
                let winning_runner = &play.scorers[runs as usize - 1];
                credited_event = match bases.min(4 - winning_runner.origin_base) {
                    1 => PlateAppearance::Single,
                    2 => PlateAppearance::Double,
                    3 => PlateAppearance::Triple,
                    _ => unreachable!("non-HR walk-off hit has 1..3 credited bases"),
                };
            }
        }
        self.stats[team][batter_index].record(credited_event);
        let rbi = if let Some(t) = &transition {
            play.scorers
                .iter()
                .take(runs as usize)
                .filter(|s| t.rbi[usize::from(s.origin_base)])
                .count() as u32
        } else {
            runs
        };
        self.stats[team][batter_index].runs_batted_in += rbi;
        if play.outs_on_play == 2 {
            self.stats[team][batter_index].grounded_into_double_plays += 1;
        }
        if let Some(t) = &transition {
            match t.reach {
                Some(crate::ContactReach::Error) => {
                    self.stats[team][batter_index].reached_on_error += 1
                }
                Some(crate::ContactReach::FieldersChoice) => {
                    self.stats[team][batter_index].fielders_choices += 1
                }
                None => {}
            }
        }
        let scored_batter_ids: Vec<String> = play
            .scorers
            .iter()
            .take(runs as usize)
            .map(|scorer| scorer.runner.batter_id.clone())
            .collect();
        for id in &scored_batter_ids {
            let index = self
                .input
                .team(side)
                .lineup
                .iter()
                .position(|b| &b.id == id)
                .expect("every runner originated in this lineup");
            self.stats[team][index].runs += 1;
        }
        self.state.score[team] += runs;
        self.state.bases = play.bases;
        self.state.outs += play.outs_on_play;
        self.outs_recorded[team] += u32::from(play.outs_on_play);
        self.state.plate_appearances += 1;
        self.state.next_batter[team] = ((batter_index + 1) % 9) as u8;
        let line = self.line_score.last_mut().expect("current inning exists");
        match side {
            Side::Away => line.away += runs,
            Side::Home => *line.home.as_mut().expect("home half has begun") += runs,
        }
        if walk_off {
            // Includes uncredited would-be scorers; game ended before they could score.
            self.left_on_base[team] +=
                occupied_before as u32 + 1 - runs - u32::from(play.outs_on_play);
            self.clear_bases();
            self.state.status = GameStatus::Final;
        } else if self.state.outs == 3 {
            self.left_on_base[team] += if self.input.schema_version == crate::RUNNER_INPUT_VERSION {
                occupied_before as u32 + 1 - runs - u32::from(play.outs_on_play)
            } else {
                self.state.bases.iter().flatten().count() as u32
            };
            self.clear_bases();
            self.end_half();
        }
        if self.state.status == GameStatus::InProgress
            && self.state.plate_appearances >= self.input.config.max_plate_appearances
        {
            self.abort(LimitReached::MaxPlateAppearances);
        }
        let record = PlayRecord {
            event_index: self.state.plate_appearances,
            inning,
            half,
            batter_id,
            supplied_event: event,
            credited_event,
            outs_on_play: play.outs_on_play,
            scored_batter_ids,
            state_after: self.state.clone(),
            transition_index,
        };
        if let Some(log) = &mut self.event_log {
            log.push(record.clone());
        }
        Ok(record)
    }

    fn clear_bases(&mut self) {
        self.state.bases = std::array::from_fn(|_| None);
    }

    fn abort(&mut self, reason: LimitReached) {
        self.state.status = GameStatus::Aborted;
        self.state.abort_reason = Some(reason);
    }

    fn end_half(&mut self) {
        match self.state.half {
            Half::Top => {
                if self.state.inning >= 9 && self.state.score[1] > self.state.score[0] {
                    self.state.status = GameStatus::Final;
                } else {
                    self.state.half = Half::Bottom;
                    self.state.outs = 0;
                    self.line_score
                        .last_mut()
                        .expect("current inning exists")
                        .home = Some(0);
                }
            }
            Half::Bottom => {
                if self.state.inning >= 9 && self.state.score[0] != self.state.score[1] {
                    self.state.status = GameStatus::Final;
                } else if self.state.inning >= self.input.config.max_innings {
                    self.abort(LimitReached::MaxInnings);
                } else {
                    self.state.inning += 1;
                    self.state.half = Half::Top;
                    self.state.outs = 0;
                    self.line_score.push(InningScore {
                        inning: self.state.inning,
                        away: 0,
                        home: None,
                    });
                }
            }
        }
    }

    pub fn result(&self) -> Result<GameResult, EngineError> {
        match self.state.status {
            GameStatus::InProgress => return Err(EngineError::IncompleteGame),
            GameStatus::Aborted => {
                return Err(EngineError::Aborted(
                    self.state.abort_reason.expect("aborted has reason"),
                ));
            }
            GameStatus::Final => {}
        }
        Ok(GameResult {
            schema_version: if self.input.schema_version == crate::RUNNER_INPUT_VERSION {
                "1.2.0"
            } else if self.input.config.defense.is_some() {
                "1.1.0"
            } else {
                RESULT_SCHEMA_VERSION
            }
            .into(),
            engine_version: ENGINE_VERSION.into(),
            input: self.input.clone(),
            winner: if self.state.score[0] > self.state.score[1] {
                Side::Away
            } else {
                Side::Home
            },
            score: self.state.score,
            line_score: self.line_score.clone(),
            teams: [self.box_score(Side::Away), self.box_score(Side::Home)],
            final_state: self.state.clone(),
            event_log: self.event_log.clone(),
        })
    }
}

/// Replay exactly the supplied script. Exhausted/extra events and safety aborts are errors.
pub fn replay_game(
    input: GameInput,
    events: &[PlateAppearance],
) -> Result<GameResult, EngineError> {
    let mut game = Game::new(input)?;
    for (index, event) in events.iter().enumerate() {
        if game.snapshot().status == GameStatus::Final {
            return Err(EngineError::TrailingEvents {
                remaining: events.len() - index,
            });
        }
        game.apply_event(*event)?;
    }
    if game.snapshot().status == GameStatus::InProgress {
        return Err(EngineError::ScriptExhausted {
            plate_appearances: game.snapshot().plate_appearances,
        });
    }
    game.result()
}
