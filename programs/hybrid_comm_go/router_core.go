package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sync"
)

// BHL Go 路由核心
// 负责跨语言模块的消息分发与状态同步

type Message struct {
	Source      string `json:"source"`
	Target      string `json:"target"`
	Payload     string `json:"payload"`
	Priority    int    `json:"priority"`
}

type Router struct {
	mu       sync.RWMutex
	channels map[string]chan Message
}

func NewRouter() *Router {
	return &Router{
		channels: make(map[string]chan Message),
	}
}

func (r *Router) Register(name string) chan Message {
	r.mu.Lock()
	defer r.mu.Unlock()
	ch := make(chan Message, 100)
	r.channels[name] = ch
	return ch
}

func (r *Router) Route(msg Message) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if ch, ok := r.channels[msg.Target]; ok {
		ch <- msg
	}
}

func main() {
	router := NewRouter()

	// 注册示例目标
	router.Register("python")
	cppCh := router.Register("cpp")

	go func() {
		for msg := range cppCh {
			// 将发往 CPP 的消息转化为标准输出事件，由 C++ 进程捕获
			fmt.Printf("{\"jsonrpc\":\"2.0\",\"method\":\"on_msg\",\"params\":{\"from\":\"%s\",\"data\":\"%s\"}}\n", msg.Source, msg.Payload)
		}
	}()

	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		var req struct {
			Method string `json:"method"`
			Params struct {
				Target  string `json:"target"`
				Payload string `json:"payload"`
			} `json:"params"`
			Id string `json:"id"`
		}

		if err := json.Unmarshal([]byte(line), &req); err == nil {
			switch req.Method {
			case "send_msg":
				msg := Message{Source: "python", Target: req.Params.Target, Payload: req.Params.Payload}
				router.Route(msg)
				fmt.Printf("{\"jsonrpc\":\"2.0\",\"result\":{\"status\":\"sent\"},\"id\":\"%s\"}\n", req.Id)
			case "status":
				fmt.Printf("{\"jsonrpc\":\"2.0\",\"result\":{\"active_channels\":%d},\"id\":\"%s\"}\n", len(router.channels), req.Id)
			case "exit":
				os.Exit(0)
			}
		}
	}
}
