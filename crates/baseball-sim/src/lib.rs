//! Portable baseball simulation core.
//!
//! Deterministic single-game state transitions driven by explicitly supplied events.
//! No sampling, network, storage, browser calls or system randomness. See the
//! versioned language-neutral contracts and `docs/SIMULATION_FOUNDATION.md`.

mod bases;
mod contract;
mod game;
mod stats;

pub use bases::{BasePlay, Bases, Runner, ScoringRunner, resolve_bases};
pub use contract::*;
pub use game::*;
pub use stats::*;

/// Engine package version recorded in every completed result.
pub const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");
