package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
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

				// Small delay to avoid hitting OS limits on open files if range is too large
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
