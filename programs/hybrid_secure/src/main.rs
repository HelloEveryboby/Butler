use std::io::{self, BufRead};

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

        process_request(&line);
    }
}

fn process_request(line: &str) {
    // Very basic manual JSON parsing to avoid dependencies and be "MCU-ready"
    let method = get_json_value(line, "method");
    let id = get_json_value(line, "id");

    match method.as_str() {
        "hash_simple" => {
            let data = get_json_value(line, "data");
            // A simple high-performance "demonstration" hash (XOR-sum + bit rotation)
            // In a real system, one would use the 'sha2' crate.
            let mut hash: u64 = 0x12345678;
            for byte in data.as_bytes() {
                hash ^= *byte as u64;
                hash = hash.rotate_left(5);
            }
            let result_hash = format!("{:x}", hash);
            println!("{{\"jsonrpc\":\"2.0\",\"result\":{{\"hash\":\"{}\"}},\"id\":\"{}\"}}", result_hash, id);
        }
        "exit" => {
            std::process::exit(0);
        }
        _ => {
            println!("{{\"jsonrpc\":\"2.0\",\"error\":{{\"code\":-32601,\"message\":\"Method not found\"}},\"id\":\"{}\"}}", id);
        }
    }
}

fn get_json_value(json: &str, key: &str) -> String {
    let search_key = format!("\"{}\"", key);
    if let Some(pos) = json.find(&search_key) {
        let after_key = &json[pos + search_key.len()..];
        if let Some(colon_pos) = after_key.find(':') {
            let value_part = &after_key[colon_pos + 1..].trim();
            if value_part.starts_with('\"') {
                if let Some(end_quote) = value_part[1..].find('\"') {
                    return value_part[1..end_quote + 1].to_string();
                }
            } else {
                let end_pos = value_part.find(|c: char| c == ',' || c == '}' || c == ' ');
                return match end_pos {
                    Some(idx) => value_part[..idx].to_string(),
                    None => value_part.to_string(),
                };
            }
        }
    }
    String::new()
}
