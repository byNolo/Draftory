//! Native file/terminal I/O stays outside the simulation library.
use std::{env, fs, io};

use baseball_sim::{GameInput, PlateAppearance, replay_game};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        return Err(
            "Usage: cargo run -p baseball-sim --example replay -- INPUT.json SCRIPT.json".into(),
        );
    }
    let input: GameInput = serde_json::from_str(&fs::read_to_string(&args[1])?)?;
    let events: Vec<PlateAppearance> = serde_json::from_str(&fs::read_to_string(&args[2])?)?;
    let result = replay_game(input, &events)?;
    serde_json::to_writer_pretty(io::stdout().lock(), &result)?;
    Ok(())
}
