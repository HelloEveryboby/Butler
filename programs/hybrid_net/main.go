package main

import (
	"bufio"
	"encoding/json"
	"fmt"
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
