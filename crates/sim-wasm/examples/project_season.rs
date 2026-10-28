//! Native equivalent of the browser's versioned dashboard projection.
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).ok_or("Provide season input JSON")?;
    let input = std::fs::read_to_string(path)?;
    let run = sim_wasm::project_measured(&input, sim_wasm::Projection::Dashboard, || 0.0)?;
    println!("{}", run.result_json);
    Ok(())
}
