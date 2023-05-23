use itertools::Itertools;
use serde::Deserialize;
use serde_json::{from_reader, json, to_writer};
use std::fs::File;
use std::io::{BufReader, BufWriter, Write};

#[derive(Deserialize)] // (1)!
struct Instance {
    numbers: Vec<u64>,
}

fn main() -> Result<(), std::io::Error> {
    let file = File::open("input/instance.json")?; // (2)!
    let parsed: Instance = from_reader(BufReader::new(file))?;
    let numbers = parsed.numbers;

    for indices in (0..numbers.len()).combinations(4) { // (3)!
        let first = numbers[indices[0]] + numbers[indices[1]];
        let second = numbers[indices[2]] + numbers[indices[3]];

        if first == second { // (4)!
            let solution = json!({ "indices": indices });
            let file = File::create("output/solution.json")?;
            let mut writer = BufWriter::new(file);
            to_writer(&mut writer, &solution)?;
            writer.flush()?;
            return Ok(());
        }
    }
    Ok(())
}
