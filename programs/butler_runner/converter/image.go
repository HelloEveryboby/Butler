package converter

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"strings"

	"github.com/deepteams/webp"
)

type ImageToWebPConverter struct{}

func (c *ImageToWebPConverter) SupportedFormats() (DocType, DocType) {
	return TypePNG, TypeWebP // Let's also register JPG->WebP if needed, we'll see registry below
}

func (c *ImageToWebPConverter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	// Decode incoming image (supports PNG, JPG, GIF)
	img, _, err := image.Decode(src)
	if err != nil {
		return fmt.Errorf("failed to decode source image: %w", err)
	}

	quality := float32(80)
	if q, ok := opts.Config["quality"].(float64); ok {
		quality = float32(q)
	}

	// Use pure Go webp encoder
	err = webp.Encode(dst, img, &webp.EncoderOptions{
		Quality: quality,
		Method:  4,
	})
	if err != nil {
		return fmt.Errorf("webp encoding failed: %w", err)
	}

	return nil
}

type ImageToBase64Converter struct{}

func (c *ImageToBase64Converter) SupportedFormats() (DocType, DocType) {
	return TypePNG, TypeBase64
}

func (c *ImageToBase64Converter) Convert(ctx context.Context, src io.Reader, dst io.Writer, opts ConvertOptions) error {
	var buf bytes.Buffer
	if _, err := io.Copy(&buf, src); err != nil {
		return fmt.Errorf("failed to read source image: %w", err)
	}

	// Decode image metadata/header to find format if WithDataUri is requested
	format := "png"
	withDataURI := false
	if val, ok := opts.Config["WithDataUri"].(bool); ok && val {
		withDataURI = true
	}

	if withDataURI {
		_, f, err := image.DecodeConfig(bytes.NewReader(buf.Bytes()))
		if err == nil {
			format = strings.ToLower(f)
			if format == "jpeg" {
				format = "jpg"
			}
		}
	}

	encoded := base64.StdEncoding.EncodeToString(buf.Bytes())

	if withDataURI {
		prefix := fmt.Sprintf("data:image/%s;base64,", format)
		if _, err := dst.Write([]byte(prefix)); err != nil {
			return err
		}
	}

	if _, err := dst.Write([]byte(encoded)); err != nil {
		return err
	}

	return nil
}
