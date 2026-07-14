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

	"github.com/xuri/excelize/v2"
)

type CSVToExcelConverter struct{}

func (c *CSVToExcelConverter) SupportedFormats() (DocType, DocType) {
	return TypeCSV, TypeExcel
}

func (c *CSVToExcelConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	f := excelize.NewFile()
	defer f.Close()

	// Ensure the active sheet is Sheet1
	sheetName := "Sheet1"
	index, _ := f.GetSheetIndex(sheetName)
	f.SetActiveSheet(index)

	// Set gridlines
	showGrid := true
	_ = f.SetSheetView(sheetName, -1, &excelize.ViewOptions{
		ShowGridLines: &showGrid,
	})

	streamWriter, err := f.NewStreamWriter(sheetName)
	if err != nil {
		return fmt.Errorf("failed to create excel stream writer: %w", err)
	}

	csvReader := csv.NewReader(src)
	rowIdx := 1

	// Setup theme and styles
	var headerStyleID int
	var altStyleID int
	hasAltStyle := false

	theme := strings.ToLower(opts.Theme)
	if theme == "enterprise-blue" {
		headerStyleID, _ = f.NewStyle(&excelize.Style{
			Font: &excelize.Font{Bold: true, Color: "FFFFFF"},
			Fill: excelize.Fill{Type: "pattern", Color: []string{"1E3A8A"}, Pattern: 1},
		})
		altStyleID, _ = f.NewStyle(&excelize.Style{
			Fill: excelize.Fill{Type: "pattern", Color: []string{"F3F4F6"}, Pattern: 1},
		})
		hasAltStyle = true
	} else if theme == "运维绿" || theme == "green" {
		headerStyleID, _ = f.NewStyle(&excelize.Style{
			Font: &excelize.Font{Bold: true, Color: "FFFFFF"},
			Fill: excelize.Fill{Type: "pattern", Color: []string{"065F46"}, Pattern: 1},
		})
		altStyleID, _ = f.NewStyle(&excelize.Style{
			Fill: excelize.Fill{Type: "pattern", Color: []string{"ECFDF5"}, Pattern: 1},
		})
		hasAltStyle = true
	} else {
		// default / black-white
		headerStyleID, _ = f.NewStyle(&excelize.Style{
			Font: &excelize.Font{Bold: true},
			Fill: excelize.Fill{Type: "pattern", Color: []string{"E0E0E0"}, Pattern: 1},
		})
	}

	// Keep track of max string lengths for each column
	maxColWidths := make(map[int]int)

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
			return fmt.Errorf("error reading CSV stream: %w", err)
		}

		// Convert []string to []interface{}
		row := make([]interface{}, len(record))
		for i, v := range record {
			row[i] = v
			// Track length for auto column width
			l := len(v)
			if l > maxColWidths[i] {
				maxColWidths[i] = l
			}
		}

		cell, _ := excelize.CoordinatesToCellName(1, rowIdx)
		if rowIdx == 1 {
			err = streamWriter.SetRow(cell, row, excelize.RowOpts{StyleID: headerStyleID})
		} else if hasAltStyle && rowIdx%2 == 0 {
			err = streamWriter.SetRow(cell, row, excelize.RowOpts{StyleID: altStyleID})
		} else {
			err = streamWriter.SetRow(cell, row)
		}

		if err != nil {
			return fmt.Errorf("failed to write row %d to excel: %w", rowIdx, err)
		}
		rowIdx++
	}

	if err := streamWriter.Flush(); err != nil {
		return fmt.Errorf("failed to flush excel stream: %w", err)
	}

	// Post-processing column widths based on maximum string length
	for colIdx, maxLen := range maxColWidths {
		colName, err := excelize.ColumnNumberToName(colIdx + 1)
		if err == nil {
			// standard formula for width estimation: min 10, max 50
			width := float64(maxLen) + 3
			if width < 10 {
				width = 10
			} else if width > 50 {
				width = 50
			}
			_ = f.SetColWidth(sheetName, colName, colName, width)
		}
	}

	if err := f.Write(dst); err != nil {
		return fmt.Errorf("failed to write excel to destination stream: %w", err)
	}

	return nil
}

type JSONToExcelConverter struct{}

func (c *JSONToExcelConverter) SupportedFormats() (DocType, DocType) {
	return TypeJSON, TypeExcel
}

func (c *JSONToExcelConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
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
		return fmt.Errorf("empty json dataset")
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

	// Get sorted keys for CSV header
	var keys []string
	for k := range allKeysMap {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// Stream to CSV in-memory buffer, then pass to CSVToExcelConverter
	var csvBuf bytes.Buffer
	writer := csv.NewWriter(&csvBuf)
	if err := writer.Write(keys); err != nil {
		return err
	}
	for _, flat := range flatItems {
		row := make([]string, len(keys))
		for j, key := range keys {
			row[j] = flat[key]
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}
	writer.Flush()

	csvConverter := &CSVToExcelConverter{}
	return csvConverter.Convert(ctx, &csvBuf, dst, opts)
}
