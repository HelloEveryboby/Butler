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
	r.Register(&MarkdownToHTMLConverter{})
	r.Register(&JSONToCSVConverter{})
	r.Register(&YAMLToCSVConverter{})
	return r
}

func (r *ConverterRegistry) Register(c FormatConverter) {
	from, to := c.SupportedFormats()
	key := string(from) + "->" + string(to)
	r.converters[key] = c
}

func (r *ConverterRegistry) GetConverter(from, to DocType) (FormatConverter, bool) {
	key := strings.ToUpper(string(from)) + "->" + strings.ToUpper(string(to))
	c, exists := r.converters[key]
	return c, exists
}
