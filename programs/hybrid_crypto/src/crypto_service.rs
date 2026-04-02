mod algorithms;

use algorithms::chacha20::ChaCha20;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Read, Write};
use anyhow::{Result, Context};
use rand::RngCore;

#[derive(Serialize, Deserialize)]
struct BhlRequest {
    jsonrpc: String,
    method: String,
    params: Value,
    id: Option<String>,
}

fn main() -> Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut stdout_lock = stdout.lock();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }

        let req: BhlRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Error parsing JSON: {}", e);
                continue;
            }
        };

        let req_id = req.id.clone().unwrap_or_else(|| "null".to_string());
        let result = handle_request(req);

        let response = match result {
            Ok(res) => json!({
                "jsonrpc": "2.0",
                "result": res,
                "id": req_id
            }),
            Err(e) => json!({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": e.to_string()
                },
                "id": req_id
            }),
        };

        writeln!(stdout_lock, "{}", response.to_string())?;
        stdout_lock.flush()?;
    }
    Ok(())
}

fn handle_request(req: BhlRequest) -> Result<Value> {
    match req.method.as_str() {
        "hash_sha256" => {
            let text = req.params["text"].as_str().unwrap_or("");
            let mut hasher = Sha256::new();
            hasher.update(text.as_bytes());
            let result = hasher.finalize();
            Ok(json!({ "hash": hex::encode(result) }))
        }
        "hash_file" => {
            let path = req.params["path"].as_str().context("Missing path")?;
            let file = File::open(path).context("Failed to open file")?;
            let mut reader = BufReader::new(file);
            let mut hasher = Sha256::new();
            let mut buffer = [0u8; 8192];
            loop {
                let count = reader.read(&mut buffer)?;
                if count == 0 { break; }
                hasher.update(&buffer[..count]);
            }
            Ok(json!({ "hash": hex::encode(hasher.finalize()) }))
        }
        "encrypt_file" | "decrypt_file" => {
            let input_path = req.params["input"].as_str().context("Missing input path")?;
            let output_path = req.params["output"].as_str().context("Missing output path")?;
            let key_hex = req.params["key"].as_str().context("Missing key")?;
            let nonce_hex = req.params["nonce"].as_str().context("Missing nonce")?;

            let mut key = [0u8; 32];
            hex::decode_to_slice(key_hex, &mut key).context("Invalid key hex")?;
            let mut nonce = [0u8; 12];
            hex::decode_to_slice(nonce_hex, &mut nonce).context("Invalid nonce hex")?;

            let input_file = File::open(input_path).context("Failed to open input file")?;
            let output_file = File::create(output_path).context("Failed to create output file")?;

            let mut reader = BufReader::new(input_file);
            let mut writer = BufWriter::new(output_file);

            let mut cipher = ChaCha20::new(&key, &nonce);
            let mut buffer = [0u8; 4096];

            loop {
                let count = reader.read(&mut buffer)?;
                if count == 0 { break; }
                cipher.apply_keystream(&mut buffer[..count]);
                writer.write_all(&buffer[..count])?;
            }
            writer.flush()?;

            Ok(json!({ "status": "success", "output": output_path }))
        }
        "generate_key" => {
            let mut key = [0u8; 32];
            rand::thread_rng().fill_bytes(&mut key);
            let mut nonce = [0u8; 12];
            rand::thread_rng().fill_bytes(&mut nonce);
            Ok(json!({
                "key": hex::encode(key),
                "nonce": hex::encode(nonce)
            }))
        }
        "exit" => {
            std::process::exit(0);
        }
        _ => Err(anyhow::anyhow!("Method not found")),
    }
}
