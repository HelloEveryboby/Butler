package converter

import (
	"bytes"
	"context"
	"strings"
	"testing"
)

func TestMarkdownToHTMLConverter(t *testing.T) {
	conv := &MarkdownToHTMLConverter{}
	mdInput := "# Title\n\n- Bullet 1\n- Bullet 2\n\nThis is a paragraph with **bold** text."

	src := strings.NewReader(mdInput)
	var dst bytes.Buffer
	opts := ConvertOptions{
		Theme:     "dark",
		WithWater: true,
	}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("MarkdownToHTMLConvert failed: %v", err)
	}

	result := dst.String()

	// Verify theme attribute
	if !strings.Contains(result, `html data-theme="dark"`) {
		t.Errorf("Expected dark theme attribute in HTML header")
	}

	// Verify markdown parsing content
	if !strings.Contains(result, "Title</h1>") {
		t.Errorf("Expected parsed h1 header in HTML, got:\n%s", result)
	}
	if !strings.Contains(result, "<li>Bullet 1</li>") {
		t.Errorf("Expected parsed bullet points in HTML")
	}
	if !strings.Contains(result, "<strong>bold</strong>") {
		t.Errorf("Expected parsed bold text in HTML")
	}

	// Verify Butler footprint and watermark
	if !strings.Contains(result, "Secure Watermarked Document") {
		t.Errorf("Expected secure watermark in HTML footer")
	}
}

func TestJSONToCSVConverter_Flattening(t *testing.T) {
	conv := &JSONToCSVConverter{}
	jsonInput := `[
		{
			"id": 1,
			"name": "Service A",
			"details": {
				"status": "OK",
				"latency_ms": 12.5
			},
			"tags": ["web", "prod"]
		},
		{
			"id": 2,
			"name": "Service B",
			"details": {
				"status": "ERROR",
				"latency_ms": 500.0
			},
			"tags": ["db"]
		}
	]`

	src := strings.NewReader(jsonInput)
	var dst bytes.Buffer
	opts := ConvertOptions{}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("JSONToCSVConvert failed: %v", err)
	}

	result := dst.String()
	lines := strings.Split(strings.TrimSpace(result), "\n")

	if len(lines) != 3 {
		t.Fatalf("Expected 3 lines (header + 2 rows), got %d lines", len(lines))
	}

	// Verify header columns are sorted
	expectedHeader := "details.latency_ms,details.status,id,name,tags.0,tags.1"
	if lines[0] != expectedHeader {
		t.Errorf("Expected header: %q, got: %q", expectedHeader, lines[0])
	}

	// Verify first record row
	expectedRow1 := "12.5,OK,1,Service A,web,prod"
	if lines[1] != expectedRow1 {
		t.Errorf("Expected Row 1: %q, got: %q", expectedRow1, lines[1])
	}

	// Verify second record row (handling missing array index tag.1 cleanly)
	expectedRow2 := "500,ERROR,2,Service B,db,"
	if lines[2] != expectedRow2 {
		t.Errorf("Expected Row 2: %q, got: %q", expectedRow2, lines[2])
	}
}

func TestYAMLToCSVConverter_Flattening(t *testing.T) {
	conv := &YAMLToCSVConverter{}
	yamlInput := `
- id: 101
  config:
    debug: true
    port: 8080
- id: 102
  config:
    debug: false
    port: 9000
`

	src := strings.NewReader(yamlInput)
	var dst bytes.Buffer
	opts := ConvertOptions{}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("YAMLToCSVConvert failed: %v", err)
	}

	result := dst.String()
	lines := strings.Split(strings.TrimSpace(result), "\n")

	if len(lines) != 3 {
		t.Fatalf("Expected 3 lines (header + 2 rows), got %d lines", len(lines))
	}

	expectedHeader := "config.debug,config.port,id"
	if lines[0] != expectedHeader {
		t.Errorf("Expected header: %q, got: %q", expectedHeader, lines[0])
	}

	expectedRow1 := "true,8080,101"
	if lines[1] != expectedRow1 {
		t.Errorf("Expected Row 1: %q, got: %q", expectedRow1, lines[1])
	}
}
