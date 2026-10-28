//! Portable baseball simulation core.
//!
//! Deterministic single-game state transitions with scripted or seeded sampled events.
//! No network, storage, browser calls or system randomness. See the
//! versioned language-neutral contracts and `docs/SIMULATION_FOUNDATION.md`.

mod bases;
mod contextual;
mod contract;
mod defense;
mod game;
mod sampling;
mod season;
mod stats;

pub use bases::{BasePlay, Bases, Runner, ScoringRunner, resolve_bases};
pub use contextual::*;
pub use contract::*;
pub use defense::*;
pub use game::*;
pub use sampling::*;
pub use season::*;
pub use stats::*;

/// Engine package version recorded in every completed result.
pub const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");
