use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Sha256, Digest};
use std::io::{self, BufRead};

#[derive(Serialize, Deserialize)]
struct BhlRequest {
    jsonrpc: String,
    method: String,
    params: Value,
    id: Option<String>,
}

fn main() {
    let stdin = io::stdin();
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

        let req_id = req.id.clone().unwrap_or_default();

        match req.method.as_str() {
            "hash_sha256" => {
                let text = req.params["text"].as_str().unwrap_or("");
                let mut hasher = Sha256::new();
                hasher.update(text.as_bytes());
                let result = hasher.finalize();
                let hash_hex = hex::encode(result);

                let response = json!({
                    "jsonrpc": "2.0",
                    "result": {
                        "hash": hash_hex
                    },
                    "id": req_id
                });
                println!("{}", response.to_string());
            }
            "exit" => {
                std::process::exit(0);
            }
            _ => {
                let response = json!({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found"
                    },
                    "id": req_id
                });
                println!("{}", response.to_string());
            }
        }
    }
}
