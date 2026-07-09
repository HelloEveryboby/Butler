package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"sync"
)

/**
 * Butler Vault Engine: Industrial-grade memory-pinned AES encryption.
 * Implements mlock/VirtualLock to prevent sensitive keys from swapping to disk.
 */

type VaultEngine struct {
	mu        sync.Mutex
	masterKey []byte // This slice's underlying array is pinned
	pinned    bool
}

func NewVaultEngine() *VaultEngine {
	return &VaultEngine{}
}


func (v *VaultEngine) SetMasterKey(key []byte) error {
	v.mu.Lock()
	defer v.mu.Unlock()

	// Clear old key if exists
	if v.masterKey != nil {
		v.Clear()
	}

	// 32 bytes for AES-256
	if len(key) != 32 {
		return fmt.Errorf("invalid key length: expected 32 bytes, got %d", len(key))
	}

	v.masterKey = make([]byte, 32)
	copy(v.masterKey, key)

	return v.pinMemory(v.masterKey)
}

func (v *VaultEngine) Encrypt(plaintext []byte) (string, error) {
	v.mu.Lock()
	defer v.mu.Unlock()

	if v.masterKey == nil {
		return "", fmt.Errorf("vault not initialized")
	}

	block, err := aes.NewCipher(v.masterKey)
	if err != nil {
		return "", err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}

	ciphertext := gcm.Seal(nonce, nonce, plaintext, nil)
	return hex.EncodeToString(ciphertext), nil
}

func (v *VaultEngine) Decrypt(hexCiphertext string) ([]byte, error) {
	v.mu.Lock()
	defer v.mu.Unlock()

	if v.masterKey == nil {
		return nil, fmt.Errorf("vault not initialized")
	}

	data, err := hex.DecodeString(hexCiphertext)
	if err != nil {
		return nil, err
	}

	block, err := aes.NewCipher(v.masterKey)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}

	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	return gcm.Open(nil, nonce, ciphertext, nil)
}

func (v *VaultEngine) Clear() {
	if v.masterKey == nil {
		return
	}

	// Zero out memory before unpinning/releasing
	for i := range v.masterKey {
		v.masterKey[i] = 0
	}

	v.unpinMemory(v.masterKey)
	v.masterKey = nil
}

// Global engine for the runner
var vaultEngine = NewVaultEngine()
