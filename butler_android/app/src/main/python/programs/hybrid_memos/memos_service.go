package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// Memo 结构体定义
type Memo struct {
	ID        int      `json:"id"`
	Content   string   `json:"content"`
	Tags      []string `json:"tags"`
	Resources []string `json:"resources"` // 附件路径列表
	CreatedAt int64    `json:"created_at"`
	UpdatedAt int64    `json:"updated_at"`
}

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

var db *sql.DB

func initDB(dbPath string) {
	var err error
	db, err = sql.Open("sqlite3", dbPath)
	if err != nil {
		log.Fatal(err)
	}

	sqlStmt := `
	CREATE TABLE IF NOT EXISTS memos (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		content TEXT,
		tags TEXT,
		resources TEXT,
		created_at INTEGER,
		updated_at INTEGER
	);
	`
	_, err = db.Exec(sqlStmt)
	if err != nil {
		log.Fatalf("%q: %s\n", err, sqlStmt)
	}
}

func main() {
	// 获取数据库路径，优先从环境变量获取，默认为当前目录下的 memos.db
	dbPath := os.Getenv("BUTLER_MEMO_DB")
	if dbPath == "" {
		dbPath = "memos.db"
	}
	if len(os.Args) > 1 {
		dbPath = os.Args[1]
	}

	// 确保目录存在
	os.MkdirAll(filepath.Dir(dbPath), 0755)

	initDB(dbPath)
	defer db.Close()

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

		handleRequest(req)
	}
}

func handleRequest(req Request) {
	switch req.Method {
	case "add_memo":
		content, _ := req.Params["content"].(string)
		tagsRaw, _ := req.Params["tags"].([]interface{})
		resourcesRaw, _ := req.Params["resources"].([]interface{})

		tags := make([]string, 0)
		for _, t := range tagsRaw {
			tags = append(tags, t.(string))
		}
		resources := make([]string, 0)
		for _, r := range resourcesRaw {
			resources = append(resources, r.(string))
		}

		id, err := addMemo(content, tags, resources)
		if err != nil {
			sendError(req.Id, -32000, err.Error())
		} else {
			sendResult(req.Id, map[string]interface{}{"id": id})
		}

	case "list_memos":
		limit, _ := req.Params["limit"].(float64)
		offset, _ := req.Params["offset"].(float64)
		if limit == 0 {
			limit = 20
		}
		memos, err := listMemos(int(limit), int(offset))
		if err != nil {
			sendError(req.Id, -32000, err.Error())
		} else {
			sendResult(req.Id, memos)
		}

	case "search_memos":
		query, _ := req.Params["query"].(string)
		memos, err := searchMemos(query)
		if err != nil {
			sendError(req.Id, -32000, err.Error())
		} else {
			sendResult(req.Id, memos)
		}

	case "delete_memo":
		id, _ := req.Params["id"].(float64)
		err := deleteMemo(int(id))
		if err != nil {
			sendError(req.Id, -32000, err.Error())
		} else {
			sendResult(req.Id, "success")
		}

	case "exit":
		os.Exit(0)
	default:
		sendError(req.Id, -32601, "Method not found")
	}
}

func addMemo(content string, tags []string, resources []string) (int64, error) {
	tagsJSON, _ := json.Marshal(tags)
	resourcesJSON, _ := json.Marshal(resources)
	now := time.Now().Unix()

	res, err := db.Exec("INSERT INTO memos (content, tags, resources, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
		content, string(tagsJSON), string(resourcesJSON), now, now)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func listMemos(limit, offset int) ([]Memo, error) {
	rows, err := db.Query("SELECT id, content, tags, resources, created_at, updated_at FROM memos ORDER BY created_at DESC LIMIT ? OFFSET ?", limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var memos []Memo
	for rows.Next() {
		var m Memo
		var tagsStr, resourcesStr string
		err = rows.Scan(&m.ID, &m.Content, &tagsStr, &resourcesStr, &m.CreatedAt, &m.UpdatedAt)
		if err != nil {
			return nil, err
		}
		json.Unmarshal([]byte(tagsStr), &m.Tags)
		json.Unmarshal([]byte(resourcesStr), &m.Resources)
		memos = append(memos, m)
	}
	return memos, nil
}

func searchMemos(query string) ([]Memo, error) {
	rows, err := db.Query("SELECT id, content, tags, resources, created_at, updated_at FROM memos WHERE content LIKE ? OR tags LIKE ? ORDER BY created_at DESC", "%"+query+"%", "%"+query+"%")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var memos []Memo
	for rows.Next() {
		var m Memo
		var tagsStr, resourcesStr string
		err = rows.Scan(&m.ID, &m.Content, &tagsStr, &resourcesStr, &m.CreatedAt, &m.UpdatedAt)
		if err != nil {
			return nil, err
		}
		json.Unmarshal([]byte(tagsStr), &m.Tags)
		json.Unmarshal([]byte(resourcesStr), &m.Resources)
		memos = append(memos, m)
	}
	return memos, nil
}

func deleteMemo(id int) error {
	_, err := db.Exec("DELETE FROM memos WHERE id = ?", id)
	return err
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
