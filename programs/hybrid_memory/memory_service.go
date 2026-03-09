package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
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

type SearchResult struct {
	Path      string  `json:"path"`
	LineStart int     `json:"line_start"`
	LineEnd   int     `json:"line_end"`
	Content   string  `json:"content"`
	Score     float64 `json:"score"`
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
			continue
		}

		switch req.Method {
		case "search":
			query, _ := req.Params["query"].(string)
			root, _ := req.Params["root"].(string)
			maxResults, _ := req.Params["max_results"].(float64)
			if maxResults == 0 {
				maxResults = 5
			}
			results := searchMemory(root, query, int(maxResults))
			sendResult(req.Id, results)
		case "get_stats":
			root, _ := req.Params["root"].(string)
			stats := getStats(root)
			sendResult(req.Id, stats)
		case "exit":
			os.Exit(0)
		default:
			sendError(req.Id, -32601, "Method not found")
		}
	}
}

func searchMemory(root, query string, maxResults int) []SearchResult {
	var results []SearchResult
	queryWords := strings.Fields(strings.ToLower(query))
	if len(queryWords) == 0 {
		return results
	}

	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(info.Name(), ".md") {
			return nil
		}

		file, err := os.Open(path)
		if err != nil {
			return nil
		}
		defer file.Close()

		relPath, _ := filepath.Rel(root, path)
		scanner := bufio.NewScanner(file)
		lineNumber := 0

		// Simple chunking: process file in blocks of lines or by sections
		var currentChunk []string
		chunkStartLine := 1

		for scanner.Scan() {
			lineNumber++
			line := scanner.Text()

			// If we hit a header or a blank line after some content, we might consider it a chunk boundary
			if (strings.HasPrefix(line, "#") || line == "") && len(currentChunk) > 0 {
				score := scoreChunk(currentChunk, queryWords)
				if score > 0 {
					results = append(results, SearchResult{
						Path:      relPath,
						LineStart: chunkStartLine,
						LineEnd:   lineNumber - 1,
						Content:   strings.Join(currentChunk, "\n"),
						Score:     score,
					})
				}
				currentChunk = nil
				chunkStartLine = lineNumber
			}

			if line != "" {
				currentChunk = append(currentChunk, line)
			}

			// Limit chunk size
			if len(currentChunk) > 20 {
				score := scoreChunk(currentChunk, queryWords)
				if score > 0 {
					results = append(results, SearchResult{
						Path:      relPath,
						LineStart: chunkStartLine,
						LineEnd:   lineNumber,
						Content:   strings.Join(currentChunk, "\n"),
						Score:     score,
					})
				}
				currentChunk = nil
				chunkStartLine = lineNumber + 1
			}
		}

		// Last chunk
		if len(currentChunk) > 0 {
			score := scoreChunk(currentChunk, queryWords)
			if score > 0 {
				results = append(results, SearchResult{
					Path:      relPath,
					LineStart: chunkStartLine,
					LineEnd:   lineNumber,
					Content:   strings.Join(currentChunk, "\n"),
					Score:     score,
				})
			}
		}

		return nil
	})

	// Sort results by score descending
	sort.Slice(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})

	if len(results) > maxResults {
		results = results[:maxResults]
	}

	return results
}

func scoreChunk(chunk []string, queryWords []string) float64 {
	content := strings.ToLower(strings.Join(chunk, " "))
	score := 0.0
	for _, word := range queryWords {
		if strings.Contains(content, word) {
			// Basic frequency-based scoring
			score += float64(strings.Count(content, word))
		}
	}
	// Normalize by chunk length to avoid favoring long chunks too much
	if len(content) > 0 {
		score = score / float64(len(content)) * 100.0
	}
	return score
}

func getStats(root string) map[string]interface{} {
	fileCount := 0
	totalSize := int64(0)
	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() && strings.HasSuffix(info.Name(), ".md") {
			fileCount++
			totalSize += info.Size()
		}
		return nil
	})
	return map[string]interface{}{
		"file_count": fileCount,
		"total_size": totalSize,
		"root":       root,
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
