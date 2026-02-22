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
	Method string        `json:"method"`
	Params []interface{} `json:"params"`
	ID     interface{}   `json:"id"`
}

type Response struct {
	JSONRPC string      `json:"jsonrpc"`
	Result  interface{} `json:"result"`
	ID      interface{} `json:"id"`
}

func checkURL(url string, wg *sync.WaitGroup, results chan<- map[string]interface{}) {
	defer wg.Done()
	client := http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		results <- map[string]interface{}{"url": url, "status": "error", "error": err.Error()}
		return
	}
	defer resp.Body.Close()
	results <- map[string]interface{}{"url": url, "status": resp.StatusCode}
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		var req Request
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			continue
		}

		if req.Method == "check_urls" {
			urls := req.Params[0].([]interface{})
			var wg sync.WaitGroup
			resultsChan := make(chan map[string]interface{}, len(urls))

			for _, u := range urls {
				wg.Add(1)
				go checkURL(u.(string), &wg, resultsChan)
			}

			wg.Wait()
			close(resultsChan)

			var results []map[string]interface{}
			for r := range resultsChan {
				results = append(results, r)
			}

			resp := Response{JSONRPC: "2.0", Result: results, ID: req.ID}
			respJSON, _ := json.Marshal(resp)
			fmt.Println(string(respJSON))
		} else if req.Method == "exit" {
			break
		}
	}
}
