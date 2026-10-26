//! Portable baseball simulation core.
//!
//! Future simulation functions consume resolved inputs and return results without
//! network, database, UI, or host-clock dependencies. A separate adapter will own
//! browser bindings when needed. No simulation model is implemented yet.

/// Crate version for future engine metadata; no replay compatibility is promised yet.
pub const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");
