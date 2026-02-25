package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"
)

type Request struct {
	Jsonrpc string                 `json:"jsonrpc"`
	Method  string                 `json:"method"`
	Params  map[string]interface{} `json:"params"`
	Id      string                 `json:"id"`
}

type Response struct {
	Jsonrpc string      `json:"jsonrpc"`
	Result  interface{} `json:"result,omitempty"`
	Error   interface{} `json:"error,omitempty"`
	Id      string      `json:"id"`
}

type Event struct {
	Jsonrpc string      `json:"jsonrpc"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params"`
}

func checkURL(url string, wg *sync.WaitGroup, results chan<- map[string]interface{}) {
	defer wg.Done()

	client := http.Client{
		Timeout: 5 * time.Second,
	}

	start := time.Now()
	resp, err := client.Get(url)
	duration := time.Since(start).Milliseconds()

	if err != nil {
		results <- map[string]interface{}{
			"url":     url,
			"status":  "error",
			"message": err.Error(),
		}
		return
	}
	defer resp.Body.Close()

	results <- map[string]interface{}{
		"url":      url,
		"status":   "ok",
		"code":     resp.StatusCode,
		"duration": duration,
	}
}

func scanPort(host string, port int, timeout time.Duration, results chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	address := fmt.Sprintf("%s:%d", host, port)
	conn, err := net.DialTimeout("tcp", address, timeout)
	if err == nil {
		results <- port
		conn.Close()
	}
}

// --- New Feature: HTTP Benchmark ---
func benchmark(url string, count int, concurrency int, id string) {
	sendEvent("benchmark_started", map[string]interface{}{
		"url": url, "count": count, "concurrency": concurrency,
	})

	resultsChan := make(chan int64, count)
	jobs := make(chan bool, count)
	var wg sync.WaitGroup

	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			MaxIdleConnsPerHost: concurrency,
		},
	}

	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range jobs {
				start := time.Now()
				resp, err := client.Get(url)
				if err == nil {
					io.Copy(io.Discard, resp.Body)
					resp.Body.Close()
					resultsChan <- time.Since(start).Milliseconds()
				} else {
					resultsChan <- -1
				}
			}
		}()
	}

	for i := 0; i < count; i++ {
		jobs <- true
	}
	close(jobs)
	wg.Wait()
	close(resultsChan)

	var latencies []int64
	var successCount int
	var totalLatency int64
	for l := range resultsChan {
		if l != -1 {
			latencies = append(latencies, l)
			successCount++
			totalLatency += l
		}
	}

	if successCount == 0 {
		sendError(id, -1, "All benchmark requests failed")
		return
	}

	sort.Slice(latencies, func(i, j int) bool { return latencies[i] < latencies[j] })

	sendResult(id, map[string]interface{}{
		"total_requests": count,
		"success":        successCount,
		"min_ms":         latencies[0],
		"max_ms":         latencies[len(latencies)-1],
		"avg_ms":         totalLatency / int64(successCount),
		"p95_ms":         latencies[int(float64(successCount)*0.95)],
	})
}

// --- New Feature: Concurrent Download ---
func concurrentDownload(url string, filepath string, concurrency int, id string) {
	resp, err := http.Head(url)
	if err != nil {
		sendError(id, -1, "Failed to get file info: "+err.Error())
		return
	}

	contentLength, err := strconv.Atoi(resp.Header.Get("Content-Length"))
	if err != nil || contentLength <= 0 {
		sendError(id, -1, "Server does not support Content-Length or file is empty")
		return
	}

	if resp.Header.Get("Accept-Ranges") != "bytes" {
		concurrency = 1
	}

	out, err := os.Create(filepath)
	if err != nil {
		sendError(id, -1, "Failed to create file: "+err.Error())
		return
	}
	defer out.Close()

	if err := out.Truncate(int64(contentLength)); err != nil {
		sendError(id, -1, "Failed to truncate file: "+err.Error())
		return
	}

	chunkSize := contentLength / concurrency
	var wg sync.WaitGroup
	errChan := make(chan error, concurrency)

	sendEvent("download_started", map[string]interface{}{
		"size": contentLength, "chunks": concurrency,
	})

	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		start := i * chunkSize
		end := (i + 1) * chunkSize - 1
		if i == concurrency-1 {
			end = contentLength - 1
		}

		go func(s, e, index int) {
			defer wg.Done()
			req, _ := http.NewRequest("GET", url, nil)
			req.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", s, e))

			client := &http.Client{Timeout: 30 * time.Second}
			resp, err := client.Do(req)
			if err != nil {
				errChan <- fmt.Errorf("chunk %d failed: %v", index, err)
				return
			}
			defer resp.Body.Close()

			f, err := os.OpenFile(filepath, os.O_WRONLY, 0644)
			if err != nil {
				errChan <- fmt.Errorf("chunk %d file open error: %v", index, err)
				return
			}
			defer f.Close()
			f.Seek(int64(s), 0)
			_, err = io.Copy(f, resp.Body)
			if err != nil {
				errChan <- fmt.Errorf("chunk %d copy error: %v", index, err)
				return
			}

			sendEvent("download_progress", map[string]interface{}{
				"chunk": index, "status": "done",
			})
		}(start, end, i)
	}

	wg.Wait()
	close(errChan)

	if len(errChan) > 0 {
		var firstErr error
		for e := range errChan {
			firstErr = e
			break
		}
		sendError(id, -1, "Download failed: "+firstErr.Error())
		os.Remove(filepath) // Cleanup partial file on error
		return
	}

	sendResult(id, map[string]interface{}{"status": "completed", "path": filepath})
}

// --- New Feature: Batch Ping ---
func batchPing(hosts []string, id string) {
	var wg sync.WaitGroup
	resultsChan := make(chan map[string]interface{}, len(hosts))

	for _, host := range hosts {
		wg.Add(1)
		go func(h string) {
			defer wg.Done()
			start := time.Now()
			conn, err := net.DialTimeout("tcp", h+":80", 2*time.Second)
			if err != nil {
				conn, err = net.DialTimeout("tcp", h+":443", 2*time.Second)
			}

			duration := time.Since(start).Milliseconds()
			if err == nil {
				conn.Close()
				resultsChan <- map[string]interface{}{"host": h, "alive": true, "latency_ms": duration}
			} else {
				resultsChan <- map[string]interface{}{"host": h, "alive": false}
			}
		}(host)
	}

	wg.Wait()
	close(resultsChan)

	var results []map[string]interface{}
	for r := range resultsChan {
		results = append(results, r)
	}
	sendResult(id, results)
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var req Request
		err := json.Unmarshal([]byte(line), &req)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing JSON: %v\n", err)
			continue
		}

		switch req.Method {
		case "check_network":
			urls, ok := req.Params["urls"].([]interface{})
			if !ok {
				sendError(req.Id, -1, "Invalid or missing 'urls' parameter")
				continue
			}

			resultsChan := make(chan map[string]interface{}, len(urls))
			var wg sync.WaitGroup

			for _, u := range urls {
				urlStr, ok := u.(string)
				if ok {
					wg.Add(1)
					go checkURL(urlStr, &wg, resultsChan)
				}
			}

			wg.Wait()
			close(resultsChan)

			results := []map[string]interface{}{}
			for r := range resultsChan {
				results = append(results, r)
			}

			sendResult(req.Id, map[string]interface{}{
				"results": results,
			})

		case "scan_ports":
			host, _ := req.Params["host"].(string)
			if host == "" {
				host = "127.0.0.1"
			}
			startPort := int(req.Params["start"].(float64))
			endPort := int(req.Params["end"].(float64))

			if startPort == 0 { startPort = 1 }
			if endPort == 0 { endPort = 1024 }

			resultsChan := make(chan int, endPort-startPort+1)
			var wg sync.WaitGroup

			sendEvent("scan_started", map[string]interface{}{
				"host": host,
				"range": fmt.Sprintf("%d-%d", startPort, endPort),
			})

			for port := startPort; port <= endPort; port++ {
				wg.Add(1)
				go scanPort(host, port, 500*time.Millisecond, resultsChan, &wg)

				if port % 100 == 0 {
					time.Sleep(10 * time.Millisecond)
				}
			}

			wg.Wait()
			close(resultsChan)

			openPorts := []int{}
			for p := range resultsChan {
				openPorts = append(openPorts, p)
			}

			sendResult(req.Id, map[string]interface{}{
				"host":       host,
				"open_ports": openPorts,
			})

		case "benchmark":
			url, _ := req.Params["url"].(string)
			count, _ := req.Params["count"].(float64)
			concurrency, _ := req.Params["concurrency"].(float64)
			if count == 0 { count = 100 }
			if concurrency == 0 { concurrency = 10 }
			benchmark(url, int(count), int(concurrency), req.Id)

		case "concurrent_download":
			url, _ := req.Params["url"].(string)
			path, _ := req.Params["path"].(string)
			concurrency, _ := req.Params["concurrency"].(float64)
			if concurrency == 0 { concurrency = 4 }
			concurrentDownload(url, path, int(concurrency), req.Id)

		case "batch_ping":
			hosts_raw, _ := req.Params["hosts"].([]interface{})
			hosts := make([]string, len(hosts_raw))
			for i, v := range hosts_raw {
				hosts[i], _ = v.(string)
			}
			batchPing(hosts, req.Id)

		case "exit":
			os.Exit(0)

		default:
			sendError(req.Id, -32601, "Method not found")
		}
	}
}

func sendResult(id string, result interface{}) {
	resp := Response{
		Jsonrpc: "2.0",
		Result:  result,
		Id:      id,
	}
	b, _ := json.Marshal(resp)
	fmt.Println(string(b))
}

func sendError(id string, code int, message string) {
	resp := Response{
		Jsonrpc: "2.0",
		Error: map[string]interface{}{
			"code":    code,
			"message": message,
		},
		Id: id,
	}
	b, _ := json.Marshal(resp)
	fmt.Println(string(b))
}

func sendEvent(method string, params interface{}) {
	event := Event{
		Jsonrpc: "2.0",
		Method:  method,
		Params:  params,
	}
	b, _ := json.Marshal(event)
	fmt.Println(string(b))
}
