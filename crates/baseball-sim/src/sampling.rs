//! Integer-only outcome sampling, independent of base advancement and scoring.

use crate::{
    EngineError, Game, GameInput, GameResult, GameStatus, OutcomeWeights, PlateAppearance,
    SAMPLED_INPUT_SCHEMA_VERSION, WEIGHT_SCALE,
};

pub const RNG_VERSION: &str = "splitmix64-v1";
pub const OUTCOME_NAMES: [&str; 9] = [
    "single",
    "double",
    "triple",
    "homeRun",
    "walk",
    "hitByPitch",
    "strikeout",
    "battedBallOut",
    "otherContact",
];
const EVENTS: [PlateAppearance; 9] = [
    PlateAppearance::Single,
    PlateAppearance::Double,
    PlateAppearance::Triple,
    PlateAppearance::HomeRun,
    PlateAppearance::Walk { intentional: false },
    PlateAppearance::HitByPitch,
    PlateAppearance::Strikeout,
    PlateAppearance::BattedBallOut,
    PlateAppearance::OtherContact,
];

/// SplitMix64, wrapping u64 arithmetic. Every u64 seed (including zero) is valid.
/// Reference/public-domain attribution: https://prng.di.unimi.it/splitmix64.c
pub struct SplitMix64 {
    state: u64,
}

impl SplitMix64 {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    pub fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        z ^ (z >> 31)
    }

    pub(crate) fn ticket(&mut self) -> u32 {
        // Discard the incomplete residue interval rather than introducing modulo bias.
        let bound = u64::from(WEIGHT_SCALE);
        let threshold = bound.wrapping_neg() % bound;
        loop {
            let value = self.next_u64();
            if value >= threshold {
                return (value % bound) as u32;
            }
        }
    }
}

/// Validated once, then sampled without allocation, floats, parsing or I/O.
#[derive(Clone, Copy)]
pub struct OutcomeDistribution {
    cumulative: [u32; 9],
}

impl OutcomeDistribution {
    pub fn new(w: &OutcomeWeights) -> Result<Self, EngineError> {
        let values = [
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
        if values.iter().map(|&x| u64::from(x)).sum::<u64>() != u64::from(WEIGHT_SCALE) {
            return Err(EngineError::InvalidInput(
                "Weights must sum to 1000000".into(),
            ));
        }
        let mut cumulative = [0; 9];
        let mut sum = 0;
        for (i, value) in values.iter().enumerate() {
            sum += value;
            cumulative[i] = sum;
        }
        Ok(Self { cumulative })
    }

    pub fn sample_index(&self, rng: &mut SplitMix64) -> usize {
        let ticket = rng.ticket();
        self.cumulative
            .iter()
            .position(|&limit| ticket < limit)
            .expect("validated cumulative weights cover every ticket")
    }

    pub fn sample(&self, rng: &mut SplitMix64) -> PlateAppearance {
        EVENTS[self.sample_index(rng)]
    }
}

/// One complete game. Limits abort with an error, never a fabricated winner.
/// Scripted replay remains available for both versions and never consumes RNG.
pub fn simulate_game(input: GameInput) -> Result<GameResult, EngineError> {
    simulate_game_prepared(input, None, false)
}

pub(crate) fn simulate_game_prepared(
    input: GameInput,
    prepared: Option<&crate::ContextualModel>,
    season_validated: bool,
) -> Result<GameResult, EngineError> {
    if !season_validated {
        input.validate()?;
    }
    if ![
        SAMPLED_INPUT_SCHEMA_VERSION,
        crate::CONTEXT_INPUT_SCHEMA_VERSION,
        crate::DEFENSE_INPUT_VERSION,
    ]
    .contains(&input.schema_version.as_str())
    {
        return Err(EngineError::InvalidInput(
            "Sampling requires input v1.1".into(),
        ));
    }
    let distributions: Vec<_> = input
        .profiles
        .iter()
        .map(|p| OutcomeDistribution::new(&p.weights))
        .collect::<Result<_, _>>()?;
    let ordered: [[OutcomeDistribution; 9]; 2] =
        [&input.teams.away, &input.teams.home].map(|team| {
            std::array::from_fn(|i| {
                let index = input
                    .profiles
                    .iter()
                    .position(|p| p.id == team.lineup[i].profile_id)
                    .expect("validated profile reference");
                distributions[index]
            })
        });
    let mut rng = SplitMix64::new(input.seed.parse().expect("validated seed"));
    let context_model = input.config.contextual_model.clone();
    let defensive_side = input
        .config
        .defense
        .as_ref()
        .map(|d| usize::from(d.team_id == input.teams.away.id));
    let owned_defense = if prepared.is_none() {
        input
            .config
            .defense
            .as_ref()
            .map(|d| d.prepare(context_model.as_ref().expect("validated contextual model")))
    } else {
        None
    };
    let defensive_model = prepared.or(owned_defense.as_ref());
    let mut game = Game::from_validated(input);
    while game.snapshot().status == GameStatus::InProgress {
        let state = game.snapshot();
        let side = state.half.batting_side().index();
        let distribution = ordered[side][usize::from(state.next_batter[side])];
        let event = distribution.sample(&mut rng);
        let active_model = if defensive_side == Some(side) {
            defensive_model
        } else {
            None
        }
        .or(context_model.as_ref());
        if let (Some(model), Some(kind)) = (active_model, crate::ContextEvent::from_event(event)) {
            let cell = model.cell(kind, state.outs, crate::base_mask(&state.bases));
            let index = if cell.choices.len() == 1 {
                0
            } else {
                let ticket = rng.ticket();
                let mut cumulative = 0;
                cell.choices
                    .iter()
                    .position(|c| {
                        cumulative += c.weight;
                        ticket < cumulative
                    })
                    .expect("validated transition distribution")
            };
            game.apply_contextual_event(event, index)?;
        } else {
            game.apply_event(event)?;
        }
    }
    game.result()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_sequence_and_wrapping_seed_are_frozen() {
        let mut rng = SplitMix64::new(0);
        assert_eq!(
            [rng.next_u64(), rng.next_u64(), rng.next_u64()],
            [0xe220a8397b1dcdaf, 0x6e789e6aa1b965f4, 0x06c45d188009454f]
        );
        assert_eq!(SplitMix64::new(u64::MAX).next_u64(), 0xe4d971771b652c20);
    }

    #[test]
    fn zero_weights_are_never_selected_and_invalid_sums_fail() {
        let mut w = OutcomeWeights {
            single: 0,
            double: 0,
            triple: 0,
            home_run: 0,
            walk: 0,
            hit_by_pitch: 0,
            strikeout: WEIGHT_SCALE,
            batted_ball_out: 0,
            other_contact: None,
        };
        let d = OutcomeDistribution::new(&w).unwrap();
        let mut rng = SplitMix64::new(42);
        for _ in 0..10000 {
            assert_eq!(d.sample(&mut rng), PlateAppearance::Strikeout);
        }
        w.single = u32::MAX;
        assert!(OutcomeDistribution::new(&w).is_err());
        w.single = 0;
        w.strikeout = 0;
        assert!(OutcomeDistribution::new(&w).is_err());
    }

    #[test]
    fn rejection_discards_the_incomplete_modulo_interval() {
        // The first increment wraps the state to zero, whose output is zero.
        let seed = 0_u64.wrapping_sub(0x9e3779b97f4a7c15);
        let mut reference = SplitMix64::new(seed);
        assert_eq!(reference.next_u64(), 0);
        let next = reference.next_u64();
        assert!(next >= u64::from(WEIGHT_SCALE).wrapping_neg() % u64::from(WEIGHT_SCALE));
        assert_eq!(
            SplitMix64::new(seed).ticket(),
            (next % u64::from(WEIGHT_SCALE)) as u32
        );
    }

    #[test]
    fn million_draws_converge_with_fixed_seed() {
        let w = OutcomeWeights {
            single: 150000,
            double: 50000,
            triple: 5000,
            home_run: 40000,
            walk: 100000,
            hit_by_pitch: 15000,
            strikeout: 240000,
            batted_ball_out: 400000,
            other_contact: None,
        };
        let distribution = OutcomeDistribution::new(&w).unwrap();
        let mut rng = SplitMix64::new(2025);
        let mut counts = [0_u32; 9];
        for _ in 0..1_000_000 {
            counts[distribution.sample_index(&mut rng)] += 1;
        }
        for (observed, expected) in counts
            .iter()
            .zip([150000, 50000, 5000, 40000, 100000, 15000, 240000, 400000])
        {
            let p = f64::from(expected) / 1_000_000.0;
            let tolerance = 6.0 * (1_000_000.0 * p * (1.0 - p)).sqrt() + 10.0;
            assert!(f64::from(observed.abs_diff(expected)) < tolerance);
        }
    }
}
