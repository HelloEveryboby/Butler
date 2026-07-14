package converter

import (
	"bytes"
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
)

type JSONToMarkdownTableConverter struct{}

func (c *JSONToMarkdownTableConverter) SupportedFormats() (DocType, DocType) {
	return TypeJSON, TypeMarkdown
}

func (c *JSONToMarkdownTableConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read json source: %w", err)
	}

	var rawData interface{}
	if err := json.Unmarshal(buf.Bytes(), &rawData); err != nil {
		return fmt.Errorf("failed to parse json: %w", err)
	}

	var items []interface{}
	switch val := rawData.(type) {
	case []interface{}:
		items = val
	case map[string]interface{}:
		items = []interface{}{val}
	default:
		return fmt.Errorf("unsupported json root type (expected array or object)")
	}

	if len(items) == 0 {
		_, _ = dst.Write([]byte("*No data available.*\n"))
		return nil
	}

	// Flatten all items
	flatItems := make([]map[string]string, len(items))
	allKeysMap := make(map[string]bool)

	for i, item := range items {
		flat := make(map[string]string)
		flatten(item, "", flat)
		flatItems[i] = flat
		for k := range flat {
			allKeysMap[k] = true
		}
	}

	// Get sorted keys for Markdown header
	var keys []string
	for k := range allKeysMap {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// Build markdown table
	return renderMarkdownTable(ctx, keys, flatItems, dst)
}

type CSVToMarkdownTableConverter struct{}

func (c *CSVToMarkdownTableConverter) SupportedFormats() (DocType, DocType) {
	return TypeCSV, TypeMarkdown
}

func (c *CSVToMarkdownTableConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	csvReader := csv.NewReader(src)

	// Read header first
	headers, err := csvReader.Read()
	if err == io.EOF {
		_, _ = dst.Write([]byte("*No data available.*\n"))
		return nil
	}
	if err != nil {
		return fmt.Errorf("failed to read csv header: %w", err)
	}

	var flatItems []map[string]string

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		record, err := csvReader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error reading CSV: %w", err)
		}

		flat := make(map[string]string)
		for idx, h := range headers {
			if idx < len(record) {
				flat[h] = record[idx]
			} else {
				flat[h] = ""
			}
		}
		flatItems = append(flatItems, flat)
	}

	return renderMarkdownTable(ctx, headers, flatItems, dst)
}

func renderMarkdownTable(ctx context.Context, headers []string, flatItems []map[string]string, dst io.Writer) error {
	if len(headers) == 0 {
		_, _ = dst.Write([]byte("*No data available.*\n"))
		return nil
	}

	// Write Headers
	var headerLine strings.Builder
	var separatorLine strings.Builder

	headerLine.WriteString("|")
	separatorLine.WriteString("|")

	for _, h := range headers {
		escapedH := escapeMarkdownTableCell(h)
		headerLine.WriteString(fmt.Sprintf(" %s |", escapedH))
		separatorLine.WriteString(" --- |")
	}

	headerLine.WriteString("\n")
	separatorLine.WriteString("\n")

	if _, err := dst.Write([]byte(headerLine.String())); err != nil {
		return err
	}
	if _, err := dst.Write([]byte(separatorLine.String())); err != nil {
		return err
	}

	// Write Rows
	for _, flat := range flatItems {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		var rowLine strings.Builder
		rowLine.WriteString("|")
		for _, h := range headers {
			val := flat[h]
			escapedVal := escapeMarkdownTableCell(val)
			rowLine.WriteString(fmt.Sprintf(" %s |", escapedVal))
		}
		rowLine.WriteString("\n")

		if _, err := dst.Write([]byte(rowLine.String())); err != nil {
			return err
		}
	}

	return nil
}

func escapeMarkdownTableCell(s string) string {
	// Escape vertical bars and replace newlines with HTML line breaks
	s = strings.ReplaceAll(s, "|", "\\|")
	s = strings.ReplaceAll(s, "\r\n", "<br />")
	s = strings.ReplaceAll(s, "\n", "<br />")
	return s
}
