package storage_hub

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

type StorageManager struct {
	mu sync.Mutex
}

func NewStorageManager() *StorageManager {
	return &StorageManager{}
}

// TransferStream performs zero-disk IO transfer between two URLs
func (sm *StorageManager) TransferStream(ctx context.Context, srcURL string, srcHeaders map[string]string, dstURL string, method string, dstHeaders map[string]string) error {
	// 1. Get Source Stream
	reqSrc, err := http.NewRequestWithContext(ctx, "GET", srcURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create source request: %v", err)
	}
	for k, v := range srcHeaders {
		reqSrc.Header.Set(k, v)
	}

	client := &http.Client{}
	resp, err := client.Do(reqSrc)
	if err != nil {
		return fmt.Errorf("failed to get source: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("source returned status: %s", resp.Status)
	}

	// 2. Setup Destination Request
	pr, pw := io.Pipe()
	req, err := http.NewRequestWithContext(ctx, method, dstURL, pr)
	if err != nil {
		return fmt.Errorf("failed to create destination request: %v", err)
	}

	// Set headers (e.g., Authorization, Content-Type)
	for k, v := range dstHeaders {
		req.Header.Set(k, v)
	}
	// Important: OneDrive/Baidu might need Content-Length
	if resp.ContentLength > 0 {
		req.ContentLength = resp.ContentLength
	}

	// 3. Execute Transfer
	errChan := make(chan error, 1)
	go func() {
		defer pw.Close()
		_, err := io.Copy(pw, resp.Body)
		if err != nil {
			errChan <- fmt.Errorf("copy failed: %v", err)
		}
		close(errChan)
	}()

	dstResp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("destination request failed: %v", err)
	}
	defer dstResp.Body.Close()

	if dstResp.StatusCode >= 400 {
		body, _ := io.ReadAll(dstResp.Body)
		return fmt.Errorf("destination returned error %s: %s", dstResp.Status, string(body))
	}

	// Check if any error occurred in the copy goroutine
	if copyErr := <-errChan; copyErr != nil {
		return copyErr
	}

	return nil
}

// StartOAuthListener starts a temporary server to catch OAuth callback
func (sm *StorageManager) StartOAuthListener(port int) (string, error) {
	mux := http.NewServeMux()
	codeChan := make(chan string, 1)

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: mux,
	}

	mux.HandleFunc("/oauth/callback", func(w http.ResponseWriter, r *http.Request) {
		code := r.URL.Query().Get("code")
		if code != "" {
			fmt.Fprintf(w, "<html><body><h1>Authorization Successful</h1><p>You can close this window now.</p></body></html>")
			codeChan <- code
		} else {
			fmt.Fprintf(w, "Error: No code found")
		}
	})

	go func() {
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			fmt.Printf("OAuth Listener failed: %v\n", err)
		}
	}()

	// Wait for code or timeout (e.g., 2 minutes)
	select {
	case code := <-codeChan:
		server.Shutdown(context.Background())
		return code, nil
	case <-time.After(2 * time.Minute):
		server.Shutdown(context.Background())
		return "", fmt.Errorf("timeout waiting for code")
	}
}
