//! JSON and terminal I/O stay outside the portable simulation library.
use baseball_sim::{GameInput, simulate_game};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args()
        .nth(1)
        .ok_or("Usage: simulate INPUT.json")?;
    let input: GameInput = serde_json::from_slice(&std::fs::read(path)?)?;
    let result = simulate_game(input)?;
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
