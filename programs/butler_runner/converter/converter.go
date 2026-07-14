package converter

import (
	"strings"
)

type ConverterRegistry struct {
	converters map[string]FormatConverter
}

func NewConverterRegistry() *ConverterRegistry {
	r := &ConverterRegistry{
		converters: make(map[string]FormatConverter),
	}
	// Existing standard converters
	r.Register(&MarkdownToHTMLConverter{})
	r.Register(&JSONToCSVConverter{})
	r.Register(&YAMLToCSVConverter{})

	// Advanced converters
	r.Register(&CSVToExcelConverter{})
	r.Register(&JSONToExcelConverter{})
	r.Register(&MarkdownToPDFConverter{})
	r.Register(&HTMLToPDFConverter{})
	r.Register(&JSONToMarkdownTableConverter{})
	r.Register(&CSVToMarkdownTableConverter{})

	// Image converters registered with different source extensions
	r.RegisterCustom(TypePNG, TypeWebP, &ImageToWebPConverter{})
	r.RegisterCustom(TypeJPG, TypeWebP, &ImageToWebPConverter{})
	r.RegisterCustom(TypeJPEG, TypeWebP, &ImageToWebPConverter{})

	r.RegisterCustom(TypePNG, TypeBase64, &ImageToBase64Converter{})
	r.RegisterCustom(TypeJPG, TypeBase64, &ImageToBase64Converter{})
	r.RegisterCustom(TypeJPEG, TypeBase64, &ImageToBase64Converter{})

	return r
}

func (r *ConverterRegistry) Register(c FormatConverter) {
	from, to := c.SupportedFormats()
	r.RegisterCustom(from, to, c)
}

func (r *ConverterRegistry) RegisterCustom(from, to DocType, c FormatConverter) {
	key := strings.ToUpper(string(from)) + "->" + strings.ToUpper(string(to))
	r.converters[key] = c
}

func (r *ConverterRegistry) GetConverter(from, to DocType) (FormatConverter, bool) {
	key := strings.ToUpper(string(from)) + "->" + strings.ToUpper(string(to))
	c, exists := r.converters[key]
	return c, exists
}
