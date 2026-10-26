use baseball_sim::{SeasonInput, simulate_season};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).ok_or("Usage: season INPUT.json")?;
    let input: SeasonInput = serde_json::from_slice(&std::fs::read(path)?)?;
    println!("{}", serde_json::to_string(&simulate_season(input)?)?);
    Ok(())
}
