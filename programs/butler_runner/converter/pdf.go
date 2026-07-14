package converter

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/signintech/gopdf"
)

type MarkdownToPDFConverter struct{}

func (c *MarkdownToPDFConverter) SupportedFormats() (DocType, DocType) {
	return TypeMarkdown, TypePDF
}

func (c *MarkdownToPDFConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read source: %w", err)
	}

	return renderPDF(ctx, buf.String(), dst, opts, false)
}

type HTMLToPDFConverter struct{}

func (c *HTMLToPDFConverter) SupportedFormats() (DocType, DocType) {
	return TypeHTML, TypePDF
}

func (c *HTMLToPDFConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read source: %w", err)
	}

	return renderPDF(ctx, buf.String(), dst, opts, true)
}

func drawHeaderAndFooter(pdf *gopdf.GoPdf, fontName string, pageNum int) {
	// Header
	_ = pdf.SetFont(fontName, "", 9)
	pdf.SetTextColor(128, 128, 128)
	pdf.SetXY(40, 25)
	_ = pdf.Cell(nil, "Butler Automation System - Report")
	pdf.SetLineWidth(0.5)
	pdf.SetStrokeColor(200, 200, 200)
	pdf.Line(40, 35, 555, 35)

	// Footer
	pdf.SetXY(40, 810)
	_ = pdf.Cell(nil, fmt.Sprintf("Page %d", pageNum))
}

func renderPDF(ctx context.Context, content string, dst io.Writer, opts ConvertOptions, isHTML bool) error {
	pdf := gopdf.GoPdf{}
	pdf.Start(gopdf.Config{PageSize: *gopdf.PageSizeA4})
	pageNum := 1
	pdf.AddPage()

	// 1. Font detection and loading
	fontPath := ""
	if configuredPath, ok := opts.Config["FontPath"].(string); ok && configuredPath != "" {
		fontPath = configuredPath
	}
	resolvedFont := findFont(fontPath)

	fontName := "default-font"
	fontLoaded := false
	if resolvedFont != "" {
		err := pdf.AddTTFFont(fontName, resolvedFont)
		if err == nil {
			fontLoaded = true
		} else {
			fmt.Printf("⚠️ Failed to load font %s: %v. Fallback to default rendering.\n", resolvedFont, err)
		}
	}

	if !fontLoaded {
		// If absolutely no TTF font is found, gopdf cannot render text.
		// However, to prevent panics, we try to see if we can find any fallback.
		return fmt.Errorf("no suitable TrueType Font found on the system. Please specify options.Config[\"FontPath\"]")
	}

	// Draw header and footer on the first page
	drawHeaderAndFooter(&pdf, fontName, pageNum)

	// 2. Document Parser & Layouting
	var paragraphs []struct {
		isHeader bool
		hLevel   int
		isList   bool
		text     string
	}

	if isHTML {
		// Simple HTML parser: strip tags but keep line breaks, headers and lists
		// Let's replace some tags with markers, then strip tags
		text := content
		text = regexp.MustCompile(`(?i)<h1>`).ReplaceAllString(text, "\n[H1]")
		text = regexp.MustCompile(`(?i)<h2>`).ReplaceAllString(text, "\n[H2]")
		text = regexp.MustCompile(`(?i)<h3>`).ReplaceAllString(text, "\n[H3]")
		text = regexp.MustCompile(`(?i)<li>`).ReplaceAllString(text, "\n[LI]")
		text = regexp.MustCompile(`(?i)<p>`).ReplaceAllString(text, "\n")
		text = regexp.MustCompile(`(?i)<br\s*/?>`).ReplaceAllString(text, "\n")

		// Strip all other HTML tags
		tagRegex := regexp.MustCompile(`<[^>]+>`)
		stripped := tagRegex.ReplaceAllString(text, "")

		// Split into lines
		lines := strings.Split(stripped, "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			if strings.HasPrefix(line, "[H1]") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 1, text: strings.TrimPrefix(line, "[H1]")})
			} else if strings.HasPrefix(line, "[H2]") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 2, text: strings.TrimPrefix(line, "[H2]")})
			} else if strings.HasPrefix(line, "[H3]") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 3, text: strings.TrimPrefix(line, "[H3]")})
			} else if strings.HasPrefix(line, "[LI]") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isList: true, text: strings.TrimPrefix(line, "[LI]")})
			} else {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{text: line})
			}
		}
	} else {
		// Markdown parser
		lines := strings.Split(content, "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			if strings.HasPrefix(line, "# ") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 1, text: strings.TrimPrefix(line, "# ")})
			} else if strings.HasPrefix(line, "## ") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 2, text: strings.TrimPrefix(line, "## ")})
			} else if strings.HasPrefix(line, "### ") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isHeader: true, hLevel: 3, text: strings.TrimPrefix(line, "### ")})
			} else if strings.HasPrefix(line, "- ") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isList: true, text: strings.TrimPrefix(line, "- ")})
			} else if strings.HasPrefix(line, "* ") {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{isList: true, text: strings.TrimPrefix(line, "* ")})
			} else {
				paragraphs = append(paragraphs, struct {
					isHeader bool
					hLevel   int
					isList   bool
					text     string
				}{text: line})
			}
		}
	}

	// 3. Render Layout
	yPos := 60.0
	margin := 40.0
	pageWidth := 515.28 // 595.28 - 2 * 40

	for _, p := range paragraphs {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		fontSize := 11.0
		lineHeight := 16.0
		indent := 0.0

		if p.isHeader {
			if p.hLevel == 1 {
				fontSize = 20.0
				lineHeight = 26.0
				_ = pdf.SetFont(fontName, "", fontSize)
				pdf.SetTextColor(0, 0, 0)
			} else if p.hLevel == 2 {
				fontSize = 16.0
				lineHeight = 22.0
				_ = pdf.SetFont(fontName, "", fontSize)
				pdf.SetTextColor(30, 30, 30)
			} else {
				fontSize = 14.0
				lineHeight = 18.0
				_ = pdf.SetFont(fontName, "", fontSize)
				pdf.SetTextColor(50, 50, 50)
			}
			yPos += 10.0 // Add top margin for headers
		} else if p.isList {
			fontSize = 11.0
			lineHeight = 16.0
			_ = pdf.SetFont(fontName, "", fontSize)
			pdf.SetTextColor(51, 51, 51)
			indent = 15.0
		} else {
			fontSize = 11.0
			lineHeight = 16.0
			_ = pdf.SetFont(fontName, "", fontSize)
			pdf.SetTextColor(51, 51, 51)
		}

		// Calculate text wrapping
		textWidth := pageWidth - indent
		wrapped, err := pdf.SplitTextWithWordWrap(p.text, textWidth)
		if err != nil {
			wrapped = []string{p.text}
		}

		for idx, line := range wrapped {
			if yPos+lineHeight > 780.0 {
				pdf.AddPage()
				pageNum++
				drawHeaderAndFooter(&pdf, fontName, pageNum)
				yPos = 60.0
				// Need to re-set font settings because AddPage might reset state
				_ = pdf.SetFont(fontName, "", fontSize)
				if p.isHeader {
					if p.hLevel == 1 {
						pdf.SetTextColor(0, 0, 0)
					} else if p.hLevel == 2 {
						pdf.SetTextColor(30, 30, 30)
					} else {
						pdf.SetTextColor(50, 50, 50)
					}
				} else {
					pdf.SetTextColor(51, 51, 51)
				}
			}

			if p.isList && idx == 0 {
				// Render Bullet Point
				pdf.SetXY(margin, yPos)
				_ = pdf.Cell(nil, "•")
			}

			pdf.SetXY(margin+indent, yPos)
			_ = pdf.Cell(nil, line)
			yPos += lineHeight
		}

		yPos += 6.0 // Paragraph spacing
	}

	// Write out the PDF stream
	if err := pdf.Write(dst); err != nil {
		return fmt.Errorf("failed to compile and write PDF stream: %w", err)
	}

	return nil
}

func findFont(configuredPath string) string {
	if configuredPath != "" {
		if _, err := os.Stat(configuredPath); err == nil {
			return configuredPath
		}
	}

	// 2. Check ~/.butler/fonts/noto-sans-sc.ttf
	if home, err := os.UserHomeDir(); err == nil {
		p := filepath.Join(home, ".butler", "fonts", "noto-sans-sc.ttf")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	// 3. Fallback system fonts
	fallbacks := []string{
		"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
		"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
		"/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
		"C:\\Windows\\Fonts\\msyh.ttc",
		"C:\\Windows\\Fonts\\msyh.ttf",
		"C:\\Windows\\Fonts\\Arial.ttf",
		"/System/Library/Fonts/PingFang.ttc",
		"/Library/Fonts/Arial.ttf",
		"/System/Library/Fonts/Helvetica.ttc",
	}

	for _, p := range fallbacks {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	return ""
}
