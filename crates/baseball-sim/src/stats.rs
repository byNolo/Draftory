use serde::{Deserialize, Serialize};

use crate::PlateAppearance;

fn is_zero(value: &u32) -> bool {
    *value == 0
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct StatLine {
    #[serde(default, skip_serializing_if = "is_zero")]
    pub reached_on_error: u32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub fielders_choices: u32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub grounded_into_double_plays: u32,
    pub plate_appearances: u32,
    pub at_bats: u32,
    pub hits: u32,
    pub singles: u32,
    pub doubles: u32,
    pub triples: u32,
    pub home_runs: u32,
    pub walks: u32,
    pub intentional_walks: u32,
    pub hit_by_pitch: u32,
    pub strikeouts: u32,
    pub runs: u32,
    pub runs_batted_in: u32,
}

impl StatLine {
    pub(crate) fn record(&mut self, event: PlateAppearance) {
        self.plate_appearances += 1;
        match event {
            PlateAppearance::Walk { intentional } => {
                self.walks += 1;
                self.intentional_walks += u32::from(intentional);
            }
            PlateAppearance::HitByPitch => self.hit_by_pitch += 1,
            PlateAppearance::Single
            | PlateAppearance::Double
            | PlateAppearance::Triple
            | PlateAppearance::HomeRun
            | PlateAppearance::Strikeout
            | PlateAppearance::BattedBallOut
            | PlateAppearance::OtherContact => self.at_bats += 1,
        }
        match event {
            PlateAppearance::Single => self.singles += 1,
            PlateAppearance::Double => self.doubles += 1,
            PlateAppearance::Triple => self.triples += 1,
            PlateAppearance::HomeRun => self.home_runs += 1,
            PlateAppearance::Strikeout => self.strikeouts += 1,
            PlateAppearance::Walk { .. }
            | PlateAppearance::HitByPitch
            | PlateAppearance::BattedBallOut
            | PlateAppearance::OtherContact => {}
        }
        self.hits = self.singles + self.doubles + self.triples + self.home_runs;
    }

    pub(crate) fn add(&mut self, other: &Self) {
        self.grounded_into_double_plays += other.grounded_into_double_plays;
        self.reached_on_error += other.reached_on_error;
        self.fielders_choices += other.fielders_choices;
        self.plate_appearances += other.plate_appearances;
        self.at_bats += other.at_bats;
        self.hits += other.hits;
        self.singles += other.singles;
        self.doubles += other.doubles;
        self.triples += other.triples;
        self.home_runs += other.home_runs;
        self.walks += other.walks;
        self.intentional_walks += other.intentional_walks;
        self.hit_by_pitch += other.hit_by_pitch;
        self.strikeouts += other.strikeouts;
        self.runs += other.runs;
        self.runs_batted_in += other.runs_batted_in;
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct BatterBoxScore {
    pub batter_id: String,
    pub stats: StatLine,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TeamBoxScore {
    pub team_id: String,
    pub totals: StatLine,
    pub outs_recorded: u32,
    pub left_on_base: u32,
    pub batters: Vec<BatterBoxScore>,
}
