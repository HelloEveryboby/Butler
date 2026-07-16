use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Read, Write};
use anyhow::{Result, Context};
use rand::RngCore;

// Pure Rust implementation of ChaCha20 stream cipher for high-performance cryptography
pub struct ChaCha20 {
    state: [u32; 16],
    keystream: [u8; 64],
    index: usize, // current index in the keystream
    counter: u32,
}

impl ChaCha20 {
    pub fn new(key: &[u8; 32], nonce: &[u8; 12]) -> Self {
        let mut state = [0u32; 16];
        state[0] = 0x61707865;
        state[1] = 0x3320646e;
        state[2] = 0x79622d32;
        state[3] = 0x6b206574;

        for i in 0..8 {
            state[4 + i] = u32::from_le_bytes([key[i*4], key[i*4+1], key[i*4+2], key[i*4+3]]);
        }

        state[12] = 0; // initial counter
        for i in 0..3 {
            state[13 + i] = u32::from_le_bytes([nonce[i*4], nonce[i*4+1], nonce[i*4+2], nonce[i*4+3]]);
        }

        ChaCha20 {
            state,
            keystream: [0u8; 64],
            index: 64, // Start by needing a new block
            counter: 0,
        }
    }

    fn quarter_round(state: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize) {
        state[a] = state[a].wrapping_add(state[b]); state[d] ^= state[a]; state[d] = state[d].rotate_left(16);
        state[c] = state[c].wrapping_add(state[d]); state[b] ^= state[c]; state[b] = state[b].rotate_left(12);
        state[a] = state[a].wrapping_add(state[b]); state[d] ^= state[a]; state[d] = state[d].rotate_left(8);
        state[c] = state[c].wrapping_add(state[d]); state[b] ^= state[c]; state[b] = state[b].rotate_left(7);
    }

    fn generate_block(&mut self) {
        let mut mix = self.state;
        mix[12] = self.counter;

        for _ in 0..10 {
            // Column rounds
            Self::quarter_round(&mut mix, 0, 4, 8, 12);
            Self::quarter_round(&mut mix, 1, 5, 9, 13);
            Self::quarter_round(&mut mix, 2, 6, 10, 14);
            Self::quarter_round(&mut mix, 3, 7, 11, 15);
            // Diagonal rounds
            Self::quarter_round(&mut mix, 0, 5, 10, 15);
            Self::quarter_round(&mut mix, 1, 6, 11, 12);
            Self::quarter_round(&mut mix, 2, 7, 8, 13);
            Self::quarter_round(&mut mix, 3, 4, 9, 14);
        }

        for i in 0..16 {
            let res = mix[i].wrapping_add(self.state[if i == 12 { 12 } else { i }]);
            self.keystream[i*4..i*4+4].copy_from_slice(&res.to_le_bytes());
        }
        self.counter += 1;
        self.index = 0;
    }

    /// Process data in-place by XORing with the key stream
    pub fn apply_keystream(&mut self, data: &mut [u8]) {
        for byte in data.iter_mut() {
            if self.index >= 64 {
                self.generate_block();
            }
            *byte ^= self.keystream[self.index];
            self.index += 1;
        }
    }
}

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

        let req_id = req.id.clone().unwrap_or_default();
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
