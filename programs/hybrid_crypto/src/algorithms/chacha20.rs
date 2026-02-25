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
