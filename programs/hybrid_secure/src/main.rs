use std::io::{self, BufRead};

fn main() {
    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = line.unwrap();
        if line.contains("\"method\":\"hash\"") {
            // Simplified hash for demo
            let hash = format!("integrity-{:x}", line.len());
            println!("{{\"jsonrpc\":\"2.0\",\"result\":\"{}\",\"id\":null}}", hash);
        } else if line.contains("\"method\":\"exit\"") {
            break;
        }
    }
}
