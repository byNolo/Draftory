//! Native comparison with the same parse/simulate/serialize boundary as WASM.
use std::{hint::black_box, time::Instant};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let input = std::fs::read_to_string(args.get(1).ok_or("Provide input JSON path")?)?;
    let repetitions: u32 = args.get(2).ok_or("Provide repetitions")?.parse()?;
    if !(1..=1000).contains(&repetitions) {
        return Err("Repetitions must be 1..1000".into());
    }
    let mut samples = Vec::new();
    let mut bytes = 0;
    for _ in 0..repetitions {
        let start = Instant::now();
        let result = sim_wasm::simulate_json(black_box(&input))?;
        samples.push(start.elapsed().as_secs_f64() * 1000.0);
        bytes = black_box(result.len());
    }
    println!(
        "{}",
        serde_json::json!({"engineVersion":baseball_sim::ENGINE_VERSION,
        "repetitions":repetitions,"boundaryMs":samples,"resultJsonBytes":bytes})
    );
    Ok(())
}
