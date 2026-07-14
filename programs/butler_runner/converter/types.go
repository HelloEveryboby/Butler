package converter

import (
	"context"
	"io"
)

// DocType defines the supported document formats
type DocType string

const (
	TypeJSON     DocType = "JSON"
	TypeYAML     DocType = "YAML"
	TypeMarkdown DocType = "MD"
	TypeHTML     DocType = "HTML"
	TypeCSV      DocType = "CSV"
	TypeExcel    DocType = "XLSX"
	TypePDF      DocType = "PDF"
	TypePNG      DocType = "PNG"
	TypeJPG      DocType = "JPG"
	TypeJPEG     DocType = "JPEG"
	TypeWebP     DocType = "WEBP"
	TypeBase64   DocType = "BASE64"
)

// ConvertOptions contains extra conversion parameters
type ConvertOptions struct {
	Theme     string                 `json:"theme"`
	WithWater bool                   `json:"with_water"`
	Config    map[string]interface{} `json:"config"`
}

// FormatConverter is the core interface for conversion plugins
type FormatConverter interface {
	// Convert executes the core conversion using io.Reader and io.Writer for streaming
	Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error
	// SupportedFormats returns the supported source and destination formats of the plugin
	SupportedFormats() (from DocType, to DocType)
}
