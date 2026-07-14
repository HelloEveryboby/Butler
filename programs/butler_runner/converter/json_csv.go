package converter

import (
	"bytes"
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strconv"

	"gopkg.in/yaml.v3"
)

type JSONToCSVConverter struct{}

func (c *JSONToCSVConverter) SupportedFormats() (DocType, DocType) {
	return TypeJSON, TypeCSV
}

func (c *JSONToCSVConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read json source: %w", err)
	}
	return convertJSONBytesToCSV(buf.Bytes(), dst)
}

type YAMLToCSVConverter struct{}

func (c *YAMLToCSVConverter) SupportedFormats() (DocType, DocType) {
	return TypeYAML, TypeCSV
}

func (c *YAMLToCSVConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read yaml source: %w", err)
	}

	// Unmarshal YAML
	var yamlData interface{}
	if err := yaml.Unmarshal(buf.Bytes(), &yamlData); err != nil {
		return fmt.Errorf("failed to parse yaml: %w", err)
	}

	// Marshal YAML structure to JSON bytes to leverage JSON conversion
	jsonBytes, err := json.Marshal(yamlData)
	if err != nil {
		return fmt.Errorf("failed to internalize yaml as json: %w", err)
	}

	return convertJSONBytesToCSV(jsonBytes, dst)
}

func convertJSONBytesToCSV(jsonBytes []byte, dst io.Writer) error {
	var rawData interface{}
	if err := json.Unmarshal(jsonBytes, &rawData); err != nil {
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

	writer := csv.NewWriter(dst)
	defer writer.Flush()

	// Write Header
	if err := writer.Write(keys); err != nil {
		return err
	}

	// Write Rows
	for _, flat := range flatItems {
		row := make([]string, len(keys))
		for j, key := range keys {
			row[j] = flat[key]
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}

	return nil
}

func flatten(val interface{}, prefix string, current map[string]string) {
	if val == nil {
		current[prefix] = ""
		return
	}

	switch v := val.(type) {
	case map[string]interface{}:
		for k, subVal := range v {
			nextPrefix := k
			if prefix != "" {
				nextPrefix = prefix + "." + k
			}
			flatten(subVal, nextPrefix, current)
		}
	case []interface{}:
		for i, subVal := range v {
			nextPrefix := prefix + "." + strconv.Itoa(i)
			flatten(subVal, nextPrefix, current)
		}
	case string:
		current[prefix] = v
	case float64:
		current[prefix] = strconv.FormatFloat(v, 'f', -1, 64)
	case int:
		current[prefix] = strconv.Itoa(v)
	case bool:
		current[prefix] = strconv.FormatBool(v)
	default:
		current[prefix] = fmt.Sprintf("%v", v)
	}
}
