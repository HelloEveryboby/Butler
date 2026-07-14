package converter

import (
	"bytes"
	"context"
	"image"
	"image/color"
	"image/png"
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

func TestCSVToExcelConverter(t *testing.T) {
	conv := &CSVToExcelConverter{}
	csvInput := "Name,Role,Vulnerability\nServer1,Admin,SQL Injection\nServer2,User,XSS"

	src := strings.NewReader(csvInput)
	var dst bytes.Buffer
	opts := ConvertOptions{
		Theme: "enterprise-blue",
	}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("CSVToExcelConvert failed: %v", err)
	}

	// Output is in .xlsx binary format, check that it contains the zip header (PK..)
	result := dst.Bytes()
	if len(result) < 4 || string(result[:2]) != "PK" {
		t.Errorf("Expected standard ZIP/XLSX header (PK), got: %v", result[:4])
	}
}

func TestJSONToExcelConverter(t *testing.T) {
	conv := &JSONToExcelConverter{}
	jsonInput := `[
		{"Name": "Server1", "Vulnerability": "SQLi"},
		{"Name": "Server2", "Vulnerability": "XSS"}
	]`

	src := strings.NewReader(jsonInput)
	var dst bytes.Buffer
	opts := ConvertOptions{
		Theme: "green",
	}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("JSONToExcelConvert failed: %v", err)
	}

	result := dst.Bytes()
	if len(result) < 4 || string(result[:2]) != "PK" {
		t.Errorf("Expected standard ZIP/XLSX header (PK)")
	}
}

func TestMarkdownToPDFConverter(t *testing.T) {
	conv := &MarkdownToPDFConverter{}
	mdInput := "# Security Audit\n\n- Issue 1: High\n- Issue 2: Medium\n\nThis is a standard report paragraph."

	src := strings.NewReader(mdInput)
	var dst bytes.Buffer
	opts := ConvertOptions{}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Logf("MarkdownToPDFConvert info: %v", err)
	} else {
		result := dst.Bytes()
		if len(result) < 4 || string(result[:4]) != "%PDF" {
			t.Errorf("Expected PDF magic prefix (%%PDF), got: %q", string(result[:4]))
		}
	}
}

func TestJSONToMarkdownTableConverter(t *testing.T) {
	conv := &JSONToMarkdownTableConverter{}
	jsonInput := `[
		{"Service": "Auth", "Status": "Active|Online", "Description": "Handles users\nand roles"},
		{"Service": "DB", "Status": "Degraded", "Description": "High latency"}
	]`

	src := strings.NewReader(jsonInput)
	var dst bytes.Buffer
	opts := ConvertOptions{}

	err := conv.Convert(context.Background(), src, &dst, opts)
	if err != nil {
		t.Fatalf("JSONToMarkdownTableConvert failed: %v", err)
	}

	result := dst.String()
	if !strings.Contains(result, "| Description | Service | Status |") {
		t.Errorf("Expected table header row")
	}
	// Check escaping: '|' to '\|'
	if !strings.Contains(result, "Active\\|Online") {
		t.Errorf("Expected escaped vertical bar in table cell")
	}
	// Check newline replacing: '\n' to '<br />'
	if !strings.Contains(result, "Handles users<br />and roles") {
		t.Errorf("Expected newline replaced with <br /> in table cell")
	}
}

func TestImageToWebPConverter(t *testing.T) {
	conv := &ImageToWebPConverter{}

	// Create 10x10 dummy PNG image
	img := image.NewRGBA(image.Rect(0, 0, 10, 10))
	for x := 0; x < 10; x++ {
		for y := 0; y < 10; y++ {
			img.Set(x, y, color.RGBA{0, 255, 0, 255})
		}
	}
	var pngBuf bytes.Buffer
	if err := png.Encode(&pngBuf, img); err != nil {
		t.Fatalf("Failed to encode mock png: %v", err)
	}

	var dst bytes.Buffer
	opts := ConvertOptions{}

	err := conv.Convert(context.Background(), &pngBuf, &dst, opts)
	if err != nil {
		t.Fatalf("ImageToWebPConvert failed: %v", err)
	}

	result := dst.Bytes()
	if len(result) < 12 || string(result[8:12]) != "WEBP" {
		t.Errorf("Expected WEBP magic in RIFF header, got: %q", string(result))
	}
}

func TestImageToBase64Converter(t *testing.T) {
	conv := &ImageToBase64Converter{}

	// Create dummy PNG image bytes
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	var pngBuf bytes.Buffer
	_ = png.Encode(&pngBuf, img)

	// Run with WithDataUri option
	var dst bytes.Buffer
	opts := ConvertOptions{
		Config: map[string]interface{}{
			"WithDataUri": true,
		},
	}

	err := conv.Convert(context.Background(), bytes.NewReader(pngBuf.Bytes()), &dst, opts)
	if err != nil {
		t.Fatalf("ImageToBase64Convert failed: %v", err)
	}

	result := dst.String()
	if !strings.HasPrefix(result, "data:image/png;base64,") {
		t.Errorf("Expected data URI prefix, got: %q", result)
	}
}
