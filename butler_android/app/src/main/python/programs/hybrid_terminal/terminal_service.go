package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"runtime"

	"github.com/creack/pty"
)

type Request struct {
	ID     json.RawMessage `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

type Response struct {
	ID     json.RawMessage `json:"id"`
	Result interface{}     `json:"result,omitempty"`
	Error  interface{}     `json:"error,omitempty"`
}

type Event struct {
	Method string      `json:"method"`
	Params interface{} `json:"params"`
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Bytes()
		var req Request
		if err := json.Unmarshal(line, &req); err != nil {
			continue
		}
		handleRequest(req)
	}
}

var shellProcess *os.File

func handleRequest(req Request) {
	switch req.Method {
	case "start_terminal":
		err := startTerminal()
		sendResponse(req.ID, "Terminal started", err)
	case "write_input":
		var input string
		json.Unmarshal(req.Params, &input)
		if shellProcess != nil {
			shellProcess.WriteString(input)
		}
		sendResponse(req.ID, "OK", nil)
	default:
		sendResponse(req.ID, nil, "Unknown method")
	}
}

func startTerminal() error {
	var shell string
	if runtime.GOOS == "windows" {
		shell = "cmd.exe"
	} else {
		shell = "bash"
	}

	c := exec.Command(shell)
	f, err := pty.Start(c)
	if err != nil {
		return err
	}
	shellProcess = f

	go func() {
		buf := make([]byte, 1024)
		for {
			n, err := f.Read(buf)
			if err != nil {
				break
			}
			sendEvent("terminal_output", string(buf[:n]))
		}
	}()

	return nil
}

func sendResponse(id json.RawMessage, result interface{}, err interface{}) {
	resp := Response{ID: id, Result: result, Error: err}
	data, _ := json.Marshal(resp)
	fmt.Println(string(data))
}

func sendEvent(method string, params interface{}) {
	event := Event{Method: method, Params: params}
	data, _ := json.Marshal(event)
	fmt.Println(string(data))
}
